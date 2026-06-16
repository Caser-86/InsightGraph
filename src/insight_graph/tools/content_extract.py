from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel

NON_CONTENT_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "svg")


class ExtractedContent(BaseModel):
    title: str
    text: str
    snippet: str


def extract_page_content(html: str, url: str, snippet_chars: int = 300) -> ExtractedContent:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(NON_CONTENT_TAGS):
        tag.decompose()

    title = _extract_title(soup, url)
    content_root = soup.body or soup
    text = _normalize_whitespace(content_root.get_text(" "))
    snippet = text[:snippet_chars].strip()
    return ExtractedContent(title=title, text=text, snippet=snippet)


def _extract_title(soup: BeautifulSoup, url: str) -> str:
    if soup.title is not None and soup.title.string is not None:
        title = _normalize_whitespace(soup.title.string)
        if title:
            return title
    domain = urlparse(url).netloc.lower()
    return domain or url


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
