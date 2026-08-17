"""Small, dependency-free helpers for normalising user-facing text."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


_BLOCK_TAGS = {
    "article",
    "body",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "section",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str | None) -> str:
    """Return readable text while preserving paragraph breaks from HTML."""
    if not value:
        return ""

    source = str(value).replace("\\n", "\n")
    if not re.search(r"<\s*(?:body|html|article|p|div|br|li|h[1-6])\b", source, re.IGNORECASE):
        return unescape(source).strip()

    parser = _TextExtractor()
    try:
        parser.feed(source)
        parser.close()
        extracted = "".join(parser.parts)
    except Exception:
        # Malformed provider markup should never prevent an evidence event from
        # being saved. The frontend has the same defensive cleanup path.
        extracted = source

    lines = [" ".join(line.split()) for line in unescape(extracted).splitlines()]
    return "\n\n".join(line for line in lines if line).strip()
