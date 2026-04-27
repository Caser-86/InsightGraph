# Research Job Database Storage Design

## Goal

Define a future SQLite-first storage backend for research jobs while preserving the current repository contract and API behavior. This is a design-only step; it does not implement database storage.

## Scope

- SQLite is the first target backend.
- Postgres compatibility is kept as a design constraint, not a first implementation target.
- Existing `research_jobs.py` service behavior remains stable.
- Existing in-memory backend remains the default until a later implementation issue replaces or configures storage.

## Non-goals

- No database implementation in this issue.
- No retry or resume semantics.
- No multi-process worker leasing.
- No distributed locks.
- No auth-aware quotas or per-user limits.
- No public API response changes.

## Current Boundary

- `research_jobs.py` is the service layer. It validates requests, shapes responses, schedules workers, applies safe error policy, and orchestrates persistence behavior.
- `research_jobs_backend.py` owns the current in-memory backend. It owns low-level job state, lock-protected access, copy-on-read helpers, explicit updates, active counting, terminal pruning, snapshots, restore, and sequence tracking.
- Future database storage should fit below the same service layer boundary.

## Recommended Approach

Use a SQLite-first phased backend.

- Phase 1: define schema, transactions, and repository semantics.
- Phase 2: implement `SQLiteResearchJobsBackend` behind the internal backend seam.
- Phase 3: add optional migration/import from JSON metadata storage.
- Phase 4: evaluate Postgres adapter only after SQLite semantics are stable.

This keeps the MVP small while avoiding SQLite-specific behavior that would block a later Postgres backend.

## Schema

Create one jobs table:

```sql
CREATE TABLE research_jobs (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    preset TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    created_order INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT
);
```

Create one metadata table:

```sql
CREATE TABLE research_job_meta (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
```

Required metadata row:

- `key = 'next_sequence'`
- `value = current highest allocated created_order`

Indexes:

```sql
CREATE INDEX idx_research_jobs_status_order
ON research_jobs (status, created_order);

CREATE INDEX idx_research_jobs_created_order
ON research_jobs (created_order);
```

## Stored Fields

- `result_json` stores the succeeded result payload as JSON text.
- `error` stores only safe failed-job error text exposed by the API.
- `queue_position` is not stored. It is derived at read time.
- `preset` is stored as the enum value string.
- Timestamps remain ISO-8601 strings to match current API and JSON store behavior.

## Transaction Boundaries

SQLite writes should use `BEGIN IMMEDIATE` to take the write lock before reading state used for decisions.

### Create Job

In one transaction:

1. Count active jobs with status `queued` or `running`.
2. Reject create if active count is at or above `active_limit`.
3. Increment `research_job_meta.next_sequence`.
4. Insert the new `queued` job with `created_order = next_sequence`.
5. Prune oldest terminal jobs if retained terminal count exceeds `retained_limit`.
6. Commit.

If any step fails before commit, no job is visible and no worker should be scheduled.

### Cancel Job

In one transaction:

1. Select the job by `id`.
2. Return not found if absent.
3. Reject cancel unless status is `queued`.
4. Set status to `cancelled` and set `finished_at`.
5. Prune oldest terminal jobs if needed.
6. Commit.

If commit fails, job remains queued from API perspective.

### Running Transition

In one transaction:

1. Select the job by `id`.
2. Return not found if absent.
3. If status is `cancelled`, do not start work.
4. Update only from `queued` to `running` and set `started_at`.
5. Commit.

If persistence fails while marking running, preserve current service semantics: mark the job `failed` with safe error `Research job store failed.` where possible, and never expose provider details.

### Terminal Update

Terminal updates set one of `succeeded`, `failed`, or `cancelled`, plus `finished_at`, `result_json`, or safe `error`.

Default policy remains best-effort after workflow completion. A terminal write failure must not leak provider exceptions through API responses. The system does not auto-retry, resume, or lease jobs in this design.

## Queue Position Semantics

Queue position is dynamic and 1-based for queued jobs only.

For one queued job:

```sql
SELECT COUNT(*) + 1
FROM research_jobs
WHERE status = 'queued'
  AND created_order < :created_order;
```

For list responses, compute positions by sorting queued jobs by `created_order ASC` in memory after fetching, or use a window function where available:

```sql
ROW_NUMBER() OVER (ORDER BY created_order ASC)
```

Non-queued jobs return no queue position.

## Ordering and Limits

- List responses keep current newest-first behavior by `created_order DESC`.
- Queue position uses oldest-first queued order by `created_order ASC`.
- Terminal pruning deletes only terminal jobs and never deletes `queued` or `running` jobs.
- Active cap counts only `queued` and `running` jobs.

## JSON Store Migration Risks

JSON metadata storage users need an explicit import step before switching to SQLite.

Risks:

- JSON store may contain a `next_job_sequence` higher than any current job. Import must preserve it.
- JSON `result` payloads must serialize cleanly to `result_json`.
- Unknown or future fields in JSON metadata must fail import until explicitly supported.
- Existing terminal retention means old terminal history may already be pruned; SQLite import cannot recover it.
- SQLite file locking is not worker leasing. Multiple app processes can coordinate writes, but this design does not make abandoned running jobs resumable.

Import policy for a later implementation:

- Validate all jobs before writing any rows.
- Import in one transaction.
- Preserve job IDs and `created_order`.
- Store `next_sequence` exactly from JSON metadata.
- Fail closed on invalid statuses, invalid timestamps, or unserializable payloads.

## Postgres Compatibility Notes

- Use SQL concepts portable to Postgres: explicit transactions, status checks, unique `created_order`, and derived queue position.
- SQLite `BEGIN IMMEDIATE` maps conceptually to a transaction with row/table locks in Postgres.
- Postgres may replace the metadata-row sequence with a database sequence later, but import must still preserve existing `created_order` values.
- Do not depend on SQLite-only conflict handling in service semantics.

## Testing Requirements for Future Implementation

- Contract tests through public repository functions must pass unchanged for in-memory and SQLite backends.
- Create must be atomic under active-cap pressure.
- Cancel must be queued-only and rollback on failed commit.
- Running transition must not start cancelled jobs.
- Terminal pruning must delete only oldest terminal jobs.
- Queue position must be dynamic and absent for non-queued jobs.
- JSON import must preserve `created_order`, statuses, timestamps, result/error payloads, and `next_sequence`.

## Open Decisions Deferred

- Configuration flag or environment variable name for selecting SQLite backend.
- SQLite database file default path.
- Whether terminal update best-effort failures should be persisted to an operational log.
- Whether JSON metadata storage remains supported after SQLite ships.
