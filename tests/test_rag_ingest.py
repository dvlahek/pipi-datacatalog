from app.rag.ingest import chunk_text, extract_chunks, extract_text
from app.resources.fetcher import ResourceProbe


def _csv_probe() -> ResourceProbe:
    return ResourceProbe(
        final_url="https://example.com/data.csv",
        media_type="text/csv",
        detected_type="csv",
        content_sha256="a" * 64,
        byte_size=54,
        etag=None,
        last_modified=None,
        title_hint="data.csv",
        content=b"site,metric,value\nA,temperature,20.1\nA,humidity,55\nB,temperature,18.7\n",
    )


def test_csv_is_extracted_into_row_aware_text() -> None:
    text = extract_text(_csv_probe())

    assert "Row 1." in text
    assert "site: A" in text
    assert "metric: temperature" in text
    assert "value: 20.1" in text
    assert "Row 2." in text
    assert "Row 3." in text


def test_csv_creates_one_rag_chunk_per_row() -> None:
    text, chunks = extract_chunks(_csv_probe(), chunk_size=1200, overlap=200)

    assert len(chunks) == 3
    assert chunks[0].metadata["structure"] == "csv-row"
    assert chunks[0].metadata["row_number"] == 1
    assert "site: A" in chunks[0].text
    assert "humidity" in chunks[1].text
    assert "site: B" in chunks[2].text
    assert "temperature" in chunks[2].text
    assert "18.7" in chunks[2].text
    assert text == "\n".join(chunk.text for chunk in chunks)
    assert chunks[1].char_start == chunks[0].char_end + 1


def test_chunking_is_deterministic_and_overlapping() -> None:
    text = " ".join(f"token-{index}" for index in range(500))
    first = chunk_text(text, chunk_size=300, overlap=50)
    second = chunk_text(text, chunk_size=300, overlap=50)

    assert len(first) > 1
    assert [(c.text, c.char_start, c.char_end) for c in first] == [
        (c.text, c.char_start, c.char_end) for c in second
    ]
    assert first[1].char_start < first[0].char_end
    assert all(chunk.text for chunk in first)
