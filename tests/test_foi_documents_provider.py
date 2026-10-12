import pytest

from app.providers.foi_documents import (
    FoiDocumentDetail,
    FoiDocumentResolutionError,
    FoiDocumentsProvider,
    enrich_foi_document_dataset,
    preserve_foi_document_enrichment,
)
from app.resources.fetcher import ResourceProbe


HTML = """
<html><body>
  <a href="/document/?type=odluka">Odluka (59)</a>
  <section>
    <a href="/document/Odluka_o_testu">Odluka o testu</a>
    <p>Sažetak prvog dokumenta</p>
  </section>
  <section>
    <a href="https://dokumenti.foi.hr/document/Pravilnik_o_testu?x=1">Pravilnik o testu</a>
  </section>
  <a href="/document/Odluka_o_testu">Odluka o testu</a>
  <a href="/document/download/567">Preuzmi</a>
  <a href="https://example.org/document/External">External</a>
</body></html>
"""

DETAIL_HTML = """
<html>
  <head><title>Odluka o testu - FOI Dokumenti</title></head>
  <body>
    <h1>Odluka o testu</h1>
    <a href="/document/download/567">Preuzmi dokument</a>
    <a href="/document/download/567?tracking=1">Preuzmi ponovno</a>
  </body>
</html>
"""


def test_listing_discovers_unique_foi_document_detail_pages() -> None:
    datasets = FoiDocumentsProvider.parse_listing(
        HTML,
        "https://dokumenti.foi.hr/document/",
    )

    assert len(datasets) == 2
    by_id = {dataset.external_id: dataset for dataset in datasets}

    decision = by_id["Odluka_o_testu"]
    assert decision.catalog_id == "foi-document:Odluka_o_testu"
    assert decision.identifier == "urn:pipi:dataset:foi-document:Odluka_o_testu"
    assert decision.title == "Odluka o testu"
    assert decision.dataset_type == "document"
    assert decision.source_system == "foi-documents"
    assert decision.provenance is not None
    assert decision.provenance.source_url == (
        "https://dokumenti.foi.hr/document/Odluka_o_testu"
    )
    assert decision.distributions[0].kind == "metadata-page"
    assert decision.extensions["foi_documents"]["download_resolved"] is False

    rulebook = by_id["Pravilnik_o_testu"]
    assert rulebook.distributions[0].access_url == (
        "https://dokumenti.foi.hr/document/Pravilnik_o_testu"
    )


def test_detail_page_resolves_download_without_downloading_source_file() -> None:
    detail = FoiDocumentsProvider.parse_detail(
        DETAIL_HTML,
        "https://dokumenti.foi.hr/document/Odluka_o_testu",
        "https://dokumenti.foi.hr/document/",
    )

    assert detail.detail_url == "https://dokumenti.foi.hr/document/Odluka_o_testu"
    assert detail.download_id == "567"
    assert detail.download_url == "https://dokumenti.foi.hr/document/download/567"
    assert detail.page_title == "Odluka o testu"


def test_detail_page_without_download_link_is_rejected() -> None:
    with pytest.raises(FoiDocumentResolutionError, match="download"):
        FoiDocumentsProvider.parse_detail(
            "<html><body><h1>Metadata only</h1></body></html>",
            "https://dokumenti.foi.hr/document/Test",
            "https://dokumenti.foi.hr/document/",
        )


def test_source_enrichment_is_preserved_across_lightweight_listing_sync() -> None:
    dataset = FoiDocumentsProvider.parse_listing(
        HTML,
        "https://dokumenti.foi.hr/document/",
    )[0]
    detail = FoiDocumentDetail(
        detail_url=str(dataset.distributions[0].access_url),
        download_url="https://dokumenti.foi.hr/document/download/567",
        download_id="567",
        page_title=dataset.title,
    )
    probe = ResourceProbe(
        final_url=detail.download_url,
        media_type="application/pdf",
        detected_type="document",
        content_sha256="a" * 64,
        byte_size=1234,
        etag='"abc"',
        last_modified="Mon, 12 Oct 2026 07:00:00 GMT",
        title_hint="567",
        content=b"%PDF synthetic",
    )

    enriched = enrich_foi_document_dataset(dataset, detail, probe)
    assert enriched.provenance is not None
    assert enriched.provenance.content_sha256 == "a" * 64
    assert enriched.extensions["foi_documents"]["download_resolved"] is True
    source = [item for item in enriched.distributions if item.kind == "source-document"]
    assert len(source) == 1
    assert source[0].format == "PDF"
    assert source[0].download_url == detail.download_url

    rediscovered = dataset.model_copy(deep=True)
    rediscovered.title = "Odluka o testu - updated title"
    preserved = preserve_foi_document_enrichment(rediscovered, enriched)

    assert preserved.title == "Odluka o testu - updated title"
    assert preserved.extensions["foi_documents"]["download_resolved"] is True
    assert preserved.provenance is not None
    assert preserved.provenance.content_sha256 == "a" * 64
    assert any(item.kind == "source-document" for item in preserved.distributions)
