import pytest

import insight_graph.research_jobs as jobs_module
from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs_store import ResearchJobsStoreError


def reset_jobs_state() -> None:
    jobs_module.reset_research_jobs_state()


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
