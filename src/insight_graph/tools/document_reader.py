import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

from insight_graph.state import Evidence

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm"}
HTML_SUFFIXES = {".html", ".htm"}
MAX_SNIPPET_CHARS = 500


def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]:
    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    snippet = _normalize_snippet(_extract_text(text, path.suffix.lower()))
    if not snippet:
        return []

    return [
        Evidence(
            id=_evidence_id(root, path),
            subtask_id=subtask_id,
            title=path.name,
            source_url=path.as_uri(),
            snippet=snippet,
            source_type="docs",
            verified=True,
        )
    ]


def _extract_text(text: str, suffix: str) -> str:
    if suffix not in HTML_SUFFIXES:
        return text
    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup.get_text(" ")


def _resolve_inside_root(root: Path, query: str) -> Path | None:
    try:
        candidate = Path(query)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
    except OSError:
        return None

    if not candidate.is_relative_to(root):
        return None
    return candidate


def _normalize_snippet(text: str) -> str:
    return " ".join(text.split())[:MAX_SNIPPET_CHARS]


def _evidence_id(root: Path, path: Path) -> str:
    relative_path = path.relative_to(root)
    relative_path_text = relative_path.as_posix()
    digest = hashlib.sha1(relative_path_text.encode("utf-8")).hexdigest()[:8]
    return f"document-{_slugify(relative_path_text)}-{digest}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"
