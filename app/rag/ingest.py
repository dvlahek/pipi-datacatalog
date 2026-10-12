from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from pypdf import PdfReader

from app.resources.fetcher import ResourceProbe


class RagExtractionError(RuntimeError):
    pass


@dataclass(slots=True)
class TextChunk:
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    metadata: dict[str, Any]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        elif tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _extract_csv(content: bytes) -> str:
    text = _decode_text(content)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ""

    header = rows[0]
    lines: list[str] = []
    for row_number, row in enumerate(rows[1:], start=1):
        pairs = []
        for index, value in enumerate(row):
            key = header[index] if index < len(header) and header[index] else f"column_{index + 1}"
            pairs.append(f"{key}: {value}")
        lines.append(f"Row {row_number}. " + " | ".join(pairs))
    return "\n".join(lines)


def _extract_json(content: bytes) -> str:
    try:
        payload = json.loads(_decode_text(content))
    except json.JSONDecodeError as exc:
        raise RagExtractionError(f"Invalid JSON resource: {exc}") from exc

    if isinstance(payload, list):
        return "\n".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in payload
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise RagExtractionError(f"PDF could not be opened: {exc}") from exc

    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise RagExtractionError(f"PDF page {index} could not be extracted: {exc}") from exc
        if text.strip():
            pages.append(f"[Page {index}]\n{text}")
    return "\n\n".join(pages)


def _extract_html(content: bytes) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(_decode_text(content))
    return parser.text()


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def extract_text(probe: ResourceProbe) -> str:
    if not probe.content:
        raise RagExtractionError("The resource fetch did not provide content bytes.")

    detected = probe.detected_type
    media_type = probe.media_type.lower()

    if detected == "csv":
        text = _extract_csv(probe.content)
    elif detected == "json":
        text = _extract_json(probe.content)
    elif detected == "document" and media_type == "application/pdf":
        text = _extract_pdf(probe.content)
    elif detected == "text":
        if media_type in {"text/html", "application/xhtml+xml"}:
            text = _extract_html(probe.content)
        else:
            text = _decode_text(probe.content)
    else:
        raise RagExtractionError(
            f"Resource type '{detected}' with media type '{probe.media_type}' is not text-indexable yet."
        )

    normalized = _normalize_text(text)
    if not normalized:
        raise RagExtractionError("No indexable text could be extracted from the resource.")
    return normalized


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[TextChunk]:
    if chunk_size < 200:
        raise ValueError("chunk_size must be at least 200 characters")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    length = len(text)

    while start < length:
        hard_end = min(start + chunk_size, length)
        end = hard_end
        if hard_end < length:
            window = text[start:hard_end]
            candidates = [window.rfind("\n\n"), window.rfind("\n"), window.rfind(". ")]
            boundary = max(candidates)
            if boundary >= chunk_size // 2:
                end = start + boundary + (2 if window[boundary:boundary + 2] in {"\n\n", ". "} else 1)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(
                TextChunk(
                    chunk_index=index,
                    text=chunk,
                    char_start=start,
                    char_end=end,
                    metadata={"character_count": len(chunk)},
                )
            )
            index += 1

        if end >= length:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
