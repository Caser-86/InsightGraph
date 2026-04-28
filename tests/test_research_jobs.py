import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest

import insight_graph.research_jobs as jobs_module
from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_store import ResearchJobsStoreError


def reset_jobs_state() -> None:
    jobs_module.reset_research_jobs_state()


@pytest.fixture(params=["memory", "sqlite"])
def research_jobs_backend(request, tmp_path):
    if request.param == "sqlite":
        jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    else:
        jobs_module.configure_research_jobs_in_memory_backend()
    try:
        yield request.param
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_research_jobs_backend_contract_create_list_cancel(research_jobs_backend) -> None:
    created = jobs_module.create_research_job(
        query="Contract",
        preset=ResearchPreset.offline,
        created_at="2026-04-28T10:00:00Z",
    )
    assert created["status"] == "queued"

    listed = jobs_module.list_research_jobs(status=None, limit=10)
    assert listed["count"] == 1
    assert listed["jobs"][0]["queue_position"] == 1

    cancelled = jobs_module.cancel_research_job(
        created["job_id"],
        finished_at="2026-04-28T10:00:01Z",
    )
    assert cancelled["status"] == "cancelled"
    assert "queue_position" not in cancelled


def test_research_jobs_backend_contract_retry_failed_job(research_jobs_backend) -> None:
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Contract retry",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "failed-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    retry_record = jobs_module.get_research_job_record(retried["job_id"])
    assert retry_record is not None
    assert retry_record.query == "Contract retry"


def test_retry_research_job_clones_failed_job_as_new_queued_job() -> None:
    source = jobs_module.ResearchJob(
        id="failed-job",
        query="Retry me",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="failed",
        finished_at="2026-04-28T10:00:01Z",
        error="Research workflow failed.",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "failed-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    assert retried["job_id"] != "failed-job"
    retry_record = jobs_module.get_research_job_record(retried["job_id"])
    assert retry_record is not None
    assert retry_record.query == source.query
    assert retry_record.preset == source.preset
    assert retry_record.created_order == 2
    assert jobs_module.get_research_job_record("failed-job") == source


def test_retry_research_job_clones_cancelled_job_as_new_queued_job() -> None:
    source = jobs_module.ResearchJob(
        id="cancelled-job",
        query="Retry cancelled",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status="cancelled",
        finished_at="2026-04-28T10:00:01Z",
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    retried = jobs_module.retry_research_job(
        "cancelled-job",
        created_at="2026-04-28T10:00:02Z",
    )

    assert retried["status"] == "queued"
    assert retried["job_id"] != "cancelled-job"


@pytest.mark.parametrize("status", ["queued", "running", "succeeded"])
def test_retry_research_job_rejects_non_retryable_statuses(status: str) -> None:
    source = jobs_module.ResearchJob(
        id="job-1",
        query="Not retryable",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
        status=status,
    )
    jobs_module.reset_research_jobs_state(next_job_sequence=1, jobs=[source])

    with pytest.raises(jobs_module.HTTPException) as exc_info:
        jobs_module.retry_research_job(
            "job-1",
            created_at="2026-04-28T10:00:02Z",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Only failed or cancelled research jobs can be retried."


def test_retry_research_job_returns_404_for_missing_job() -> None:
    jobs_module.reset_research_jobs_state()

    with pytest.raises(jobs_module.HTTPException) as exc_info:
        jobs_module.retry_research_job(
            "missing",
            created_at="2026-04-28T10:00:02Z",
        )

    assert exc_info.value.status_code == 404


def test_sqlite_mark_running_claims_job_with_worker_lease(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Lease service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )

        claimed = jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
            worker_id="worker-a",
            lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
        )

        assert claimed is not None
        assert claimed.status == "running"
        assert claimed.started_at == "2026-04-28T10:00:01Z"
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_sqlite_heartbeat_research_job_returns_false_for_non_owner(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Heartbeat service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        assert (
            jobs_module.mark_research_job_running(
                created["job_id"],
                started_at=lambda: "2026-04-28T10:00:01Z",
                store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
                worker_id="worker-a",
                lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
            )
            is not None
        )

        assert (
            jobs_module.heartbeat_research_job(
                created["job_id"],
                worker_id="worker-b",
                now="2026-04-28T10:01:01Z",
                lease_expires_at="2026-04-28T10:06:01Z",
            )
            is False
        )
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_sqlite_terminal_write_uses_worker_ownership(tmp_path) -> None:
    jobs_module.configure_research_jobs_sqlite_backend(tmp_path / "jobs.sqlite3")
    try:
        created = jobs_module.create_research_job(
            query="Terminal service",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        job = jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
            worker_id="worker-a",
            lease_expires_at=lambda started_at: "2026-04-28T10:05:01Z",
        )
        assert job is not None

        jobs_module.mark_research_job_succeeded(
            job,
            finished_at="2026-04-28T10:00:03Z",
            result={"report_markdown": "# Wrong"},
            worker_id="worker-b",
        )
        record = jobs_module.get_research_job_record(created["job_id"])
        assert record is not None
        assert record.status == "running"

        jobs_module.mark_research_job_succeeded(
            job,
            finished_at="2026-04-28T10:00:04Z",
            result={"report_markdown": "# Right"},
            worker_id="worker-a",
        )
        record = jobs_module.get_research_job_record(created["job_id"])
        assert record is not None
        assert record.status == "succeeded"
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_configure_research_jobs_backend_from_env_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", raising=False)

    jobs_module.configure_research_jobs_backend_from_env()

    try:
        assert (
            jobs_module._RESEARCH_JOBS_BACKEND.__class__.__name__
            == "InMemoryResearchJobsBackend"
        )
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_configure_research_jobs_backend_from_env_selects_sqlite(
    monkeypatch,
    tmp_path,
) -> None:
    sqlite_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(sqlite_path))

    jobs_module.configure_research_jobs_backend_from_env()
    try:
        created = jobs_module.create_research_job(
            query="Env SQLite",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        detail = jobs_module.get_research_job(created["job_id"])
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert sqlite_path.exists()
    assert detail["status"] == "queued"


def test_research_jobs_module_import_uses_sqlite_backend_env(monkeypatch, tmp_path) -> None:
    sqlite_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(sqlite_path))

    importlib.reload(jobs_module)
    try:
        assert jobs_module._RESEARCH_JOBS_BACKEND.__class__.__name__ == "SQLiteResearchJobsBackend"
    finally:
        monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", raising=False)
        monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", raising=False)
        importlib.reload(jobs_module)


def test_configure_research_jobs_backend_from_env_refreshes_json_path(
    monkeypatch,
    tmp_path,
) -> None:
    store_path = tmp_path / "jobs.json"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_PATH", str(store_path))

    jobs_module.configure_research_jobs_backend_from_env()
    try:
        jobs_module.initialize_research_jobs(restart_timestamp="2026-04-28T11:00:00Z")
        jobs_module.create_research_job(
            query="JSON path refresh",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert store_path.exists()


def test_configure_research_jobs_backend_from_env_fails_without_sqlite_path(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", raising=False)

    with pytest.raises(ResearchJobsStoreError, match="SQLite research jobs path is required"):
        jobs_module.configure_research_jobs_backend_from_env()


def test_research_job_repository_helpers_reset_seed_and_inspect_state(tmp_path) -> None:
    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="seeded-job",
        query="Seeded",
        preset=ResearchPreset.offline,
        created_order=7,
        created_at="2026-04-27T20:00:00Z",
    )

    jobs_module.reset_research_jobs_state(
        next_job_sequence=7,
        store_path=store_path,
        retained_limit=3,
        active_limit=2,
        jobs=[job],
    )

    assert jobs_module.get_next_research_job_sequence() == 7
    assert jobs_module.get_research_job_record("seeded-job") == job

    jobs_module.reset_research_jobs_state()

    assert jobs_module.get_next_research_job_sequence() == 0
    assert jobs_module.get_research_job_record("seeded-job") is None


def test_configure_research_jobs_sqlite_backend_preserves_public_behavior(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    jobs_module.configure_research_jobs_sqlite_backend(db_path)
    try:
        created = jobs_module.create_research_job(
            query="SQLite",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        listed = jobs_module.list_research_jobs(status=None, limit=10)
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert created["status"] == "queued"
    assert listed["count"] == 1
    assert listed["jobs"][0]["query"] == "SQLite"


def test_configure_research_jobs_sqlite_backend_supports_worker_lifecycle(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"

    jobs_module.configure_research_jobs_sqlite_backend(db_path)
    try:
        created = jobs_module.create_research_job(
            query="SQLite lifecycle",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:00Z",
        )
        running = jobs_module.mark_research_job_running(
            created["job_id"],
            started_at=lambda: "2026-04-28T10:00:01Z",
            store_failure_finished_at=lambda: "2026-04-28T10:00:02Z",
        )
        assert running is not None

        jobs_module.mark_research_job_succeeded(
            running,
            finished_at="2026-04-28T10:00:03Z",
            result={"report_markdown": "# Report"},
        )
        detail = jobs_module.get_research_job(created["job_id"])
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert detail["status"] == "succeeded"
    assert detail["result"] == {"report_markdown": "# Report"}


def test_sqlite_backend_supports_service_helper_contract(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store_path = tmp_path / "jobs.json"
    job = jobs_module.ResearchJob(
        id="seeded-job",
        query="Seeded",
        preset=ResearchPreset.offline,
        created_order=7,
        created_at="2026-04-28T10:00:00Z",
    )

    jobs_module.configure_research_jobs_sqlite_backend(db_path)
    try:
        jobs_module.reset_research_jobs_state(
            next_job_sequence=7,
            store_path=store_path,
            retained_limit=3,
            active_limit=2,
            jobs=[job],
        )
        seeded = jobs_module.get_research_job_record("seeded-job")
        assert seeded is not None
        assert seeded.id == job.id
        assert seeded.query == job.query
        assert seeded.created_order == job.created_order
        assert jobs_module.get_next_research_job_sequence() == 7

        jobs_module.seed_research_job(
            jobs_module.ResearchJob(
                id="extra-job",
                query="Extra",
                preset=ResearchPreset.offline,
                created_order=8,
                created_at="2026-04-28T10:00:01Z",
            ),
            next_job_sequence=8,
        )
        jobs_module.set_research_job_limits(retained_limit=4, active_limit=3)
        assert jobs_module.get_research_job_record("extra-job") is not None
        assert jobs_module._RESEARCH_JOBS_BACKEND.retained_limit() == 4
        assert jobs_module._RESEARCH_JOBS_BACKEND.active_limit() == 3
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()


def test_sqlite_backend_initialize_imports_configured_json_store(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store_path = tmp_path / "jobs.json"
    store_path.write_text(
        """
        {
          "next_job_sequence": 4,
          "jobs": [
            {
              "id": "job-4",
              "query": "Stored",
              "preset": "offline",
              "created_order": 4,
              "created_at": "2026-04-28T10:00:00Z",
              "status": "succeeded",
              "started_at": "2026-04-28T10:00:01Z",
              "finished_at": "2026-04-28T10:00:02Z",
              "result": {"report_markdown": "# Stored"},
              "error": null
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    jobs_module.configure_research_jobs_sqlite_backend(db_path)
    try:
        jobs_module.set_research_jobs_store_path(store_path)
        jobs_module.initialize_research_jobs(restart_timestamp="2026-04-28T11:00:00Z")
        detail = jobs_module.get_research_job("job-4")
        next_sequence = jobs_module.get_next_research_job_sequence()
    finally:
        jobs_module.configure_research_jobs_in_memory_backend()

    assert next_sequence == 4
    assert detail["status"] == "succeeded"
    assert detail["result"] == {"report_markdown": "# Stored"}


def test_research_job_repository_helpers_seed_jobs_and_configure_store_path(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    first = jobs_module.ResearchJob(
        id="job-1",
        query="First",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    second = jobs_module.ResearchJob(
        id="job-2",
        query="Second",
        preset=ResearchPreset.offline,
        created_order=2,
        created_at="2026-04-27T20:00:01Z",
    )

    jobs_module.set_research_jobs_store_path(store_path)
    jobs_module.seed_research_jobs([first, second], next_job_sequence=2)

    assert jobs_module.get_research_job_record("job-1") == first
    assert jobs_module.get_research_job_record("job-2") == second
    assert jobs_module.get_next_research_job_sequence() == 2


def test_research_job_record_inspection_returns_copy_and_updates_are_explicit() -> None:
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(jobs=[job])

    inspected = jobs_module.get_research_job_record("job-1")
    assert inspected is not None
    inspected.status = "running"

    stored = jobs_module.get_research_job_record("job-1")
    assert stored is not None
    assert stored.status == "queued"

    updated = jobs_module.update_research_job_record(
        "job-1",
        status="running",
        started_at="2026-04-27T20:00:01Z",
    )

    assert updated is not None
    assert updated.status == "running"
    assert updated.started_at == "2026-04-27T20:00:01Z"
    assert jobs_module.get_research_job_record("job-1") == updated


def test_update_research_job_record_rejects_unknown_fields() -> None:
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.reset_research_jobs_state(jobs=[job])

    with pytest.raises(ValueError, match="Unknown research job field: unknown_field"):
        jobs_module.update_research_job_record("job-1", unknown_field="bad")

    assert jobs_module.get_research_job_record("job-1") == job


def test_update_research_job_record_returns_none_for_missing_job() -> None:
    reset_jobs_state()

    assert jobs_module.update_research_job_record("missing", status="running") is None


def test_research_job_helpers_preserve_state_under_concurrent_updates() -> None:
    jobs = [
        jobs_module.ResearchJob(
            id=f"job-{index}",
            query=f"Job {index}",
            preset=ResearchPreset.offline,
            created_order=index,
            created_at="2026-04-27T20:00:00Z",
        )
        for index in range(20)
    ]
    jobs_module.reset_research_jobs_state(jobs=jobs)

    def mark_running(index: int) -> None:
        updated = jobs_module.update_research_job_record(
            f"job-{index}",
            status="running",
            started_at=f"2026-04-27T20:00:{index:02d}Z",
        )
        assert updated is not None
        assert updated.status == "running"

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(mark_running, range(20)))

    records = [jobs_module.get_research_job_record(f"job-{index}") for index in range(20)]
    assert all(record is not None for record in records)
    assert {record.status for record in records if record is not None} == {"running"}
    assert {
        record.started_at for record in records if record is not None
    } == {f"2026-04-27T20:00:{index:02d}Z" for index in range(20)}


def test_research_job_status_constants_match_public_statuses() -> None:
    assert jobs_module.RESEARCH_JOB_STATUSES == (
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    )
    assert jobs_module.ACTIVE_RESEARCH_JOB_STATUSES == {"queued", "running"}
    assert jobs_module.TERMINAL_RESEARCH_JOB_STATUSES == {
        "succeeded",
        "failed",
        "cancelled",
    }


def test_job_create_response_builder_returns_public_shape() -> None:
    reset_jobs_state()
    job = jobs_module.ResearchJob(
        id="job-1",
        query="Compare Cursor",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T10:00:00Z",
    )

    assert jobs_module._job_create_response(job) == {
        "job_id": "job-1",
        "status": "queued",
        "created_at": "2026-04-27T10:00:00Z",
    }


def test_initialize_research_jobs_noops_without_store_path() -> None:
    reset_jobs_state()
    existing = jobs_module.ResearchJob(
        id="existing",
        query="Existing",
        preset=ResearchPreset.offline,
        created_order=8,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.seed_research_job(existing, next_job_sequence=8)

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T20:00:01Z")

    assert jobs_module.get_next_research_job_sequence() == 8
    assert jobs_module.get_research_job_record("existing") == existing


def test_initialize_research_jobs_loads_configured_store(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text(
        """
{
  "jobs": [
    {
      "created_at": "2026-04-27T20:00:00Z",
      "created_order": 4,
      "error": null,
      "finished_at": "2026-04-27T20:00:02Z",
      "id": "job-4",
      "preset": "offline",
      "query": "Persisted",
      "result": {"report_markdown": "# Report"},
      "started_at": "2026-04-27T20:00:01Z",
      "status": "succeeded"
    }
  ],
  "next_job_sequence": 4
}
""".strip(),
        encoding="utf-8",
    )
    jobs_module.set_research_jobs_store_path(store_path)

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")

    job = jobs_module.get_research_job_record("job-4")
    assert jobs_module.get_next_research_job_sequence() == 4
    assert jobs_module._RESEARCH_JOBS_BACKEND.next_sequence() == 4
    assert job is not None
    assert job.status == "succeeded"
    assert job.result == {"report_markdown": "# Report"}


def test_initialize_research_jobs_marks_unfinished_jobs_failed(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text(
        """
{
  "jobs": [
    {
      "created_at": "2026-04-27T20:00:00Z",
      "created_order": 1,
      "error": null,
      "finished_at": null,
      "id": "job-1",
      "preset": "offline",
      "query": "Queued",
      "result": null,
      "started_at": null,
      "status": "queued"
    }
  ],
  "next_job_sequence": 1
}
""".strip(),
        encoding="utf-8",
    )
    jobs_module.set_research_jobs_store_path(store_path)

    jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")

    job = jobs_module.get_research_job_record("job-1")
    assert job is not None
    assert job.status == "failed"
    assert job.finished_at == "2026-04-27T21:00:00Z"
    assert job.error == "Research job did not complete before server restart."


def test_initialize_research_jobs_fails_closed_for_bad_store(tmp_path) -> None:
    reset_jobs_state()
    store_path = tmp_path / "jobs.json"
    store_path.write_text("{bad-json", encoding="utf-8")
    jobs_module.set_research_jobs_store_path(store_path)

    with pytest.raises(ResearchJobsStoreError):
        jobs_module.initialize_research_jobs(restart_timestamp="2026-04-27T21:00:00Z")


def test_research_jobs_state_snapshot_restores_jobs_and_sequence() -> None:
    reset_jobs_state()
    original = jobs_module.ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-27T20:00:00Z",
    )
    jobs_module.seed_research_job(original, next_job_sequence=1)
    snapshot = jobs_module._research_jobs_state_snapshot_locked()

    jobs_module.reset_research_jobs_state(next_job_sequence=2)

    jobs_module._restore_research_jobs_state_locked(snapshot)

    assert jobs_module.get_next_research_job_sequence() == 1
    assert jobs_module.get_research_job_record("job-1") == original


def test_create_research_job_keeps_backend_sequence_synced_for_rollback(monkeypatch) -> None:
    def fail_persist() -> None:
        raise ResearchJobsStoreError("store failed")

    reset_jobs_state()
    created = jobs_module.create_research_job(
        query="First",
        preset=ResearchPreset.offline,
        created_at="2026-04-28T10:00:00Z",
    )
    assert created["status"] == "queued"
    assert jobs_module.get_next_research_job_sequence() == 1
    assert jobs_module._RESEARCH_JOBS_BACKEND.next_sequence() == 1

    monkeypatch.setattr(jobs_module, "_persist_research_jobs_locked", fail_persist)
    with pytest.raises(jobs_module.HTTPException):
        jobs_module.create_research_job(
            query="Second",
            preset=ResearchPreset.offline,
            created_at="2026-04-28T10:00:01Z",
        )

    assert jobs_module.get_next_research_job_sequence() == 1
    assert jobs_module._RESEARCH_JOBS_BACKEND.next_sequence() == 1
