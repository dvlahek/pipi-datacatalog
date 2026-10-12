from __future__ import annotations

from urllib.parse import unquote, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.models.catalog import (
    CatalogDistribution,
    CatalogProvenance,
    CatalogSource,
    CanonicalDataset,
)


class FoiDocumentsProvider:
    """Discover public FOI documents without downloading every source file.

    Phase 1 intentionally reads only the public document listing. Each document is
    registered as a stable catalog dataset that points to its public detail page.
    Download-file discovery and content hashing are resolved later, on demand, so a
    normal catalog sync does not fetch hundreds of PDFs/XLS files.
    """

    name = "foi-documents"

    def __init__(
        self,
        base_url: str = "https://dokumenti.foi.hr/document/",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds

    async def datasets(self) -> list[CanonicalDataset]:
        timeout = httpx.Timeout(self.timeout_seconds)
        headers = {
            "User-Agent": "PiPi-Data-Catalog/0.1 foi-documents-provider",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(self.base_url, headers=headers)
            response.raise_for_status()
        return self.parse_listing(response.text, self.base_url)

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
            # Remove query/fragment so provider fingerprints stay stable.
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
