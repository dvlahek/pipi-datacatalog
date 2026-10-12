from app.providers.foi_documents import FoiDocumentsProvider


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
