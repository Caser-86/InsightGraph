# Persisted Document Vector Index Design

## Goal

Add an offline persisted document index for local document retrieval. The index stores chunk metadata and deterministic embeddings in a local JSON file, so repeated document queries can reuse chunking and embedding work without requiring a database, cloud service, or external embedding provider.

## User-Facing Behavior

Default behavior is unchanged. `document_reader` continues to read, chunk, and rank documents in memory when no index path is configured.

Users opt in with `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH=<path>`. When enabled, `document_reader` stores per-document entries keyed by the resolved path. Each entry includes file metadata (`mtime_ns`, `size`), chunk text, chunk index, page, section heading, and deterministic embeddings. If the file metadata changes, the entry is rebuilt automatically.

`INSIGHT_GRAPH_DOCUMENT_RETRIEVAL=vector` continues to control whether retrieval uses vector ranking. Persisting the index does not enable vector retrieval by itself.

## Architecture

`src/insight_graph/report_quality/document_index.py` gains a small `DocumentVectorIndex` class responsible for loading/saving JSON, validating file freshness, and returning indexed chunks. The class stores only local document content already readable by the user; it does not fetch network resources.

`document_reader` keeps the existing parsing, file safety, text extraction, section heading, and evidence-building logic. A narrow integration point asks the persisted index for chunks when `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` is set. If indexing fails due to JSON corruption or I/O errors, `document_reader` falls back to existing in-memory chunking instead of failing the workflow.

## Data Format

The JSON file contains:

```json
{
  "version": 1,
  "documents": {
    "C:/path/to/doc.md": {
      "mtime_ns": 123,
      "size": 456,
      "chunks": [
        {
          "text": "...",
          "index": 0,
          "page": null,
          "section_heading": "Overview",
          "embedding": [0.1, 0.2]
        }
      ]
    }
  }
}
```

Embeddings use the existing deterministic embedding function. No API keys or external services are involved.

## Testing

Tests cover JSON save/load, stale-file rebuild, corrupted-index fallback, default behavior unchanged, and vector retrieval using persisted chunks. All tests use temporary files and deterministic embeddings.
