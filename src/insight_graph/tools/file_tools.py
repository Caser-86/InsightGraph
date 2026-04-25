import hashlib
import re
from pathlib import Path

from insight_graph.state import Evidence

SUPPORTED_READ_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}
MAX_FILE_BYTES = 64 * 1024
MAX_SNIPPET_CHARS = 500
MAX_DIRECTORY_ENTRIES = 50


def read_file(query: str, subtask_id: str = "collect") -> list[Evidence]:
    query_text = _coerce_query(query)
    if query_text is None:
        return []

    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query_text)
    if path is None or not path.is_file():
        return []
    if path.suffix.lower() not in SUPPORTED_READ_SUFFIXES:
        return []

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    snippet = _normalize_snippet(text)
    if not snippet:
        return []

    return [
        Evidence(
            id=_evidence_id("read-file", root, path),
            subtask_id=subtask_id,
            title=path.name,
            source_url=path.as_uri(),
            snippet=snippet,
            source_type="docs",
            verified=True,
        )
    ]


def list_directory(query: str, subtask_id: str = "collect") -> list[Evidence]:
    query_text = _coerce_query(query, empty_as_root=True)
    if query_text is None:
        return []

    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query_text)
    if path is None or not path.is_dir():
        return []

    try:
        entries = sorted(path.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []

    entry_names = [
        f"{entry.name}/" if entry.is_dir() else entry.name
        for entry in entries[:MAX_DIRECTORY_ENTRIES]
    ]
    snippet = "\n".join(entry_names)[:MAX_SNIPPET_CHARS]
    relative_title = _relative_path_text(root, path, root_text=".")

    return [
        Evidence(
            id=_evidence_id(
                "list-directory",
                root,
                path,
                root_slug="root",
                root_text=".",
            ),
            subtask_id=subtask_id,
            title=f"Directory listing: {relative_title}",
            source_url=path.as_uri(),
            snippet=snippet or "(empty directory)",
            source_type="docs",
            verified=True,
        )
    ]


def _resolve_inside_root(root: Path, query: str) -> Path | None:
    try:
        candidate = Path(query)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
    except (OSError, TypeError, ValueError):
        return None

    if not candidate.is_relative_to(root):
        return None
    return candidate


def _coerce_query(query: str, *, empty_as_root: bool = False) -> str | None:
    if not isinstance(query, str):
        return None
    if empty_as_root and query == "":
        return "."
    return query


def _evidence_id(
    prefix: str,
    root: Path,
    path: Path,
    root_slug: str | None = None,
    root_text: str | None = None,
) -> str:
    relative_path_text = _relative_path_text(root, path, root_text=root_text)
    digest = hashlib.sha1(relative_path_text.encode("utf-8")).hexdigest()[:8]
    slug_input = relative_path_text
    if root_slug is not None and relative_path_text == root_text:
        slug_input = root_slug
    return f"{prefix}-{_slugify(slug_input)}-{digest}"


def _relative_path_text(root: Path, path: Path, root_text: str | None = None) -> str:
    relative_path_text = path.relative_to(root).as_posix()
    if relative_path_text == "." and root_text is not None:
        return root_text
    return relative_path_text


def _normalize_snippet(text: str) -> str:
    return " ".join(text.split())[:MAX_SNIPPET_CHARS]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "root"
