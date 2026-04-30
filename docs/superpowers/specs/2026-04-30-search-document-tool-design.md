# search_document Tool Design

## Goal

Add a built-in `search_document` tool that exposes local document RAG retrieval through the same tool/evidence boundary as the reference project. This phase creates the stable agent-facing interface and reuses existing offline document parsing, chunk metadata, ranking, and persisted local index. It does not claim full production parity with pgvector-backed SEC/HKEX-scale RAG.

## Reference Alignment

The reference README positions `search_document` as a first-class tool for large-document RAG: TOC/page-aware retrieval, vector search, and precise long-PDF evidence snippets. InsightGraph already has local TXT/Markdown/HTML/PDF parsing, chunk/page/section metadata, deterministic/vector ranking, persisted JSON document index, and embedding provider boundaries. This tool connects those pieces under the reference-compatible tool name.

## User-Facing Behavior

`search_document(query, subtask_id)` accepts:

- Plain path: `report.pdf`
- JSON object: `{"path":"report.pdf","query":"enterprise pricing"}`
- Optional JSON fields: `limit`, `mode`, `page`, `section`

The tool only reads files inside the current working directory and only supports the same local suffixes as `document_reader`. It never reads URLs, never scans arbitrary directories, and never calls LLMs. It returns verified `Evidence` with `source_type="docs"`, preserving `chunk_index`, `document_page`, and `section_heading`.

## Retrieval Semantics

`search_document` uses existing document chunking and ranking behavior:

- `mode="deterministic"`: lexical ranking with section-heading boosts.
- `mode="vector"`: deterministic vector ranking via `rank_document_chunks()`.
- No `mode`: use `INSIGHT_GRAPH_DOCUMENT_RETRIEVAL`.
- `page`: filter results to chunks with matching `document_page`.
- `section`: filter results to chunks whose `section_heading` contains the requested section text, case-insensitive.
- `limit`: cap returned evidence; default to existing document evidence limit.

When `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` is set, the tool reuses the persisted local JSON index and rebuilds stale entries through existing document-reader/index helpers. When unset, it remains in-memory and offline.

## Planner/Tool Registry

The tool is registered in `ToolRegistry` under `search_document`. Planner exposure is opt-in: when `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT=1`, document-oriented collection may suggest `search_document`. Existing `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` behavior remains unchanged.

## Out Of Scope

- pgvector-backed document chunk storage.
- True PDF outline/TOC extraction.
- Cross-document global search without explicit path.
- OCR, remote PDF fetching, or network document stores.
- External embeddings in the document index.

These are required for full reference-quality RAG parity and should follow after the stable tool boundary lands.

## Testing

Tests cover JSON/plain query parsing, path containment, tool registry registration, deterministic ranking, vector mode override, page/section filters, limit handling, persisted-index reuse, planner opt-in, and unchanged defaults.
