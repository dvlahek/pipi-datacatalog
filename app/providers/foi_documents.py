from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.models.catalog import (
    CatalogDistribution,
    CatalogProvenance,
    CatalogSource,
    CanonicalDataset,
)
from app.resources.fetcher import ResourceProbe


class FoiDocumentResolutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FoiDocumentDetail:
    detail_url: str
    download_url: str
    download_id: str
    page_title: str | None = None


def _source_format(dataset: CanonicalDataset, probe: ResourceProbe) -> str | None:
    media_type = probe.media_type.lower()
    media_formats = {
        "application/pdf": "PDF",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
        "application/vnd.ms-excel": "XLS",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
        "application/msword": "DOC",
        "text/csv": "CSV",
        "text/plain": "TXT",
    }
    if media_type in media_formats:
        return media_formats[media_type]

    suffix = PurePosixPath(urlparse(probe.final_url).path).suffix.lstrip(".")
    if suffix:
        return suffix.upper()

    external_id = (dataset.external_id or "").lower()
    for candidate in ("xlsx", "xls", "docx", "doc", "pdf", "csv", "txt"):
        if external_id.endswith(f"_{candidate}") or external_id.endswith(f".{candidate}"):
            return candidate.upper()
    return None


def enrich_foi_document_dataset(
    dataset: CanonicalDataset,
    detail: FoiDocumentDetail,
    probe: ResourceProbe,
) -> CanonicalDataset:
    """Attach one resolved source file and its provenance to a FOI catalog dataset.

    The source bytes remain at FOI. PiPi persists only normalized metadata, HTTP
    provenance and the content SHA-256 that was computed during the bounded fetch.
    """

    if dataset.source_system != "foi-documents":
        raise ValueError("FOI document enrichment requires a foi-documents dataset.")

    enriched = dataset.model_copy(deep=True)
    source_distribution = CatalogDistribution(
        identifier=f"{dataset.identifier}:distribution:source-document",
        title="FOI Dokumenti source document",
        access_url=probe.final_url,
        download_url=probe.final_url,
        media_type=probe.media_type,
        format=_source_format(dataset, probe),
        kind="source-document",
        is_live=False,
    )
    enriched.distributions = [
        distribution
        for distribution in enriched.distributions
        if distribution.kind != "source-document"
    ] + [source_distribution]
    enriched.provenance = CatalogProvenance(
        source_url=probe.final_url,
        etag=probe.etag,
        last_modified=probe.last_modified,
        content_sha256=probe.content_sha256,
    )

    extensions = dict(enriched.extensions)
    foi = dict(extensions.get("foi_documents") or {})
    foi.update(
        {
            "detail_url": detail.detail_url,
            "download_resolved": True,
            "download_id": detail.download_id,
            "download_url": probe.final_url,
            "media_type": probe.media_type,
            "format": source_distribution.format,
            "byte_size": probe.byte_size,
            "content_sha256": probe.content_sha256,
        }
    )
    extensions["foi_documents"] = foi
    enriched.extensions = extensions
    return enriched


def preserve_foi_document_enrichment(
    discovered: CanonicalDataset,
    current: CanonicalDataset | None,
) -> CanonicalDataset:
    """Keep on-demand source resolution when a lightweight listing sync runs again.

    Listing discovery intentionally does not fetch source files. Once a dataset has
    been resolved on demand, later provider syncs may update listing metadata such as
    the title without reverting the dataset to its earlier listing-only state.
    """

    if current is None or discovered.source_system != "foi-documents":
        return discovered

    current_foi = dict(current.extensions.get("foi_documents") or {})
    if not current_foi.get("download_resolved"):
        return discovered

    source_distributions = [
        distribution.model_copy(deep=True)
        for distribution in current.distributions
        if distribution.kind == "source-document"
    ]
    if not source_distributions:
        return discovered

    merged = discovered.model_copy(deep=True)
    merged.distributions = [
        distribution
        for distribution in merged.distributions
        if distribution.kind != "source-document"
    ] + source_distributions
    merged.provenance = current.provenance.model_copy(deep=True) if current.provenance else None

    extensions = dict(merged.extensions)
    merged_foi = dict(extensions.get("foi_documents") or {})
    merged_foi.update(current_foi)
    extensions["foi_documents"] = merged_foi
    merged.extensions = extensions
    return merged


class FoiDocumentsProvider:
    """Discover public FOI documents without downloading every source file.

    Normal provider discovery reads only the public listing and creates one stable
    catalog dataset per public document. A document detail page is resolved only on
    demand. This avoids fetching hundreds of detail pages or source PDFs/XLS files on
    every catalog sync while still giving the RAG/indexing layer a way to resolve the
    actual source file when needed.
    """

    name = "foi-documents"

    def __init__(
        self,
        base_url: str = "https://dokumenti.foi.hr/document/",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "PiPi-Data-Catalog/0.1 foi-documents-provider",
            "Accept": "text/html,application/xhtml+xml",
        }

    async def datasets(self) -> list[CanonicalDataset]:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(self.base_url, headers=self._headers)
            response.raise_for_status()
        return self.parse_listing(response.text, self.base_url)

    async def resolve_detail(self, detail_url: str) -> FoiDocumentDetail:
        """Resolve one public detail page to its source-download URL.

        This call fetches only the selected detail page. It does not download the
        source document body. The caller can decide whether/when the actual PDF/XLS
        file should be fetched and hashed.
        """

        self._validate_detail_url(detail_url)
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(detail_url, headers=self._headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FoiDocumentResolutionError(
                f"FOI document detail request failed: {exc}"
            ) from exc

        return self.parse_detail(response.text, detail_url, self.base_url)

    def _validate_detail_url(self, detail_url: str) -> None:
        base = urlparse(self.base_url)
        parsed = urlparse(detail_url)
        if parsed.scheme not in {"http", "https"}:
            raise FoiDocumentResolutionError("FOI detail URL must use HTTP or HTTPS.")
        if parsed.netloc.lower() != base.netloc.lower():
            raise FoiDocumentResolutionError("FOI detail URL points outside the configured host.")
        segments = [part for part in parsed.path.split("/") if part]
        if len(segments) != 2 or segments[0] != "document":
            raise FoiDocumentResolutionError("FOI detail URL has an unexpected path.")

    @staticmethod
    def parse_detail(
        html: str,
        detail_url: str,
        base_url: str,
    ) -> FoiDocumentDetail:
        """Parse the canonical download link from one FOI document detail page."""

        soup = BeautifulSoup(html, "html.parser")
        base = urlparse(base_url)

        page_title: str | None = None
        heading = soup.find(["h1", "h2"])
        if heading is not None:
            value = " ".join(heading.stripped_strings).strip()
            page_title = value or None
        if page_title is None and soup.title is not None:
            value = " ".join(soup.title.stripped_strings).strip()
            page_title = value or None

        candidates: list[tuple[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(detail_url, href)
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != base.netloc.lower():
                continue
            segments = [part for part in parsed.path.split("/") if part]
            if len(segments) != 3 or segments[0] != "document" or segments[1] != "download":
                continue
            download_id = unquote(segments[2]).strip()
            if not download_id:
                continue
            download_url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
            )
            candidates.append((download_id, download_url))

        if not candidates:
            raise FoiDocumentResolutionError(
                "FOI document detail page does not expose a /document/download/{id} link."
            )

        download_id, download_url = candidates[0]
        return FoiDocumentDetail(
            detail_url=detail_url,
            download_url=download_url,
            download_id=download_id,
            page_title=page_title,
        )

    @staticmethod
    def parse_listing(html: str, base_url: str) -> list[CanonicalDataset]:
        """Parse stable document detail links from the server-rendered listing."""

        soup = BeautifulSoup(html, "html.parser")
        base = urlparse(base_url)
        discovered: dict[str, CanonicalDataset] = {}

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href:
                continue

            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != base.netloc.lower():
                continue

            segments = [part for part in parsed.path.split("/") if part]
            if len(segments) != 2 or segments[0] != "document":
                continue
            if segments[1].lower() == "download":
                continue

            title = " ".join(anchor.stripped_strings).strip()
            if not title:
                continue

            external_id = unquote(segments[1])
            detail_url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
            )
            identifier = f"urn:pipi:dataset:foi-document:{external_id}"

            discovered.setdefault(
                identifier,
                CanonicalDataset(
                    catalog_id=f"foi-document:{external_id}",
                    identifier=identifier,
                    title=title,
                    description=(
                        "Public institutional document listed in the FOI Dokumenti "
                        "repository. The PiPi catalog stores discovery metadata and "
                        "the stable source link; the source document remains at FOI."
                    ),
                    publisher="Fakultet organizacije i informatike",
                    license="unknown",
                    dataset_type="document",
                    source_system="foi-documents",
                    external_id=external_id,
                    keywords=["FOI", "document"],
                    provenance=CatalogProvenance(source_url=detail_url),
                    source=CatalogSource(
                        id=external_id,
                        code=external_id,
                        name=title,
                        provider="FOI Dokumenti",
                    ),
                    distributions=[
                        CatalogDistribution(
                            identifier=f"{identifier}:distribution:detail-page",
                            title="FOI Dokumenti detail page",
                            access_url=detail_url,
                            media_type="text/html",
                            format="HTML",
                            kind="metadata-page",
                            is_live=False,
                        )
                    ],
                    extensions={
                        "foi_documents": {
                            "detail_url": detail_url,
                            "discovery_url": base_url,
                            "discovery_mode": "listing-only",
                            "download_resolved": False,
                        }
                    },
                ),
            )

        return list(discovered.values())
