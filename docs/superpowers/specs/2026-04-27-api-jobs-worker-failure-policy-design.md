# API Jobs Worker Failure Policy Design

## Goal

Make `_run_research_job` state transitions explicit and predictable when workflow execution or JSON persistence fails.

## Scope

This is a backend cleanup for the existing in-process research job worker. It does not change public endpoint paths, response models, response bodies, job statuses, JSON store schema, retry behavior, worker pool size, or restart recovery behavior.

## Current Problem

`_run_research_job` currently handles worker state in three inline blocks:

- mark queued job as `running`
- mark workflow exception as `failed`
- mark workflow success as `succeeded`

The running transition already prevents a persistence failure from leaving a job active. The terminal transitions still call `_persist_research_jobs_locked()` directly, so a JSON store write failure can escape the worker future after the job has become `failed` or `succeeded`. The in-memory state is usually correct, but the policy is implicit and inconsistent.

## Desired Policy

Worker state transitions should be centralized in small helpers:

- `_mark_research_job_running_locked(job) -> bool`
- `_mark_research_job_failed_locked(job, error: str) -> None`
- `_mark_research_job_succeeded_locked(job, result: dict[str, Any]) -> None`

The helpers own timestamp assignment, status mutation, pruning, and worker-side persistence handling.

## Semantics

### Cancelled Before Start

If a job is already `cancelled` when the worker picks it up, the worker returns without changing state or writing the store.

### Running Transition Store Failure

If persisting the `running` transition fails before workflow execution starts:

- the job becomes `failed`
- `finished_at` is set
- `error` is `Research job store failed.`
- the worker tries one best-effort persistence write
- `run_research` is not called
- the worker does not re-raise the store exception

### Workflow Failure

If `run_research` or payload building raises:

- the job becomes `failed`
- `finished_at` is set
- `error` is `Research workflow failed.`
- terminal pruning still runs
- terminal persistence is best-effort and does not re-raise to the worker future

### Workflow Success

If workflow execution succeeds:

- the job becomes `succeeded`
- `finished_at` is set
- `result` is set
- terminal pruning still runs
- terminal persistence is best-effort and does not re-raise to the worker future

If terminal persistence fails after success or workflow failure, in-memory terminal state remains authoritative for the running process. The JSON file may be stale until a later successful write or restart handling.

## Non-Goals

- No retry policy.
- No logging or metrics system.
- No worker pool changes.
- No automatic resume.
- No database changes.
- No endpoint or response shape changes.
- No OpenAPI polish.

## Testing

Add or update tests for:

- running transition store failure does not call `run_research` and marks job failed
- workflow failure plus terminal store failure does not raise from `_run_research_job`
- workflow success plus terminal store failure does not raise from `_run_research_job`
- cancelled job before worker start remains cancelled and does not write store
- existing success/failure/cancel/persistence tests remain green

Run focused API tests, full pytest, and ruff.

## Self-Review

- No placeholders remain.
- Scope is limited to worker failure-state policy cleanup.
- Public API behavior is unchanged.
- JSON persistence schema is unchanged.
- Store write failures are handled explicitly in worker paths.
