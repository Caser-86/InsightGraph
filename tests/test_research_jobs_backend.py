import pytest

from insight_graph.cli import ResearchPreset
from insight_graph.research_jobs import ResearchJob
from insight_graph.research_jobs_backend import InMemoryResearchJobsBackend


def test_in_memory_research_jobs_backend_copies_reads_and_updates_explicitly() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)
    job = ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    backend.reset(jobs=[job])

    inspected = backend.get("job-1")
    assert inspected is not None
    inspected.status = "running"

    stored = backend.get("job-1")
    assert stored is not None
    assert stored.status == "queued"

    updated = backend.update(
        "job-1",
        status="running",
        started_at="2026-04-28T10:00:01Z",
    )
    assert updated is not None
    assert updated.status == "running"
    assert updated.started_at == "2026-04-28T10:00:01Z"
    assert backend.get("job-1") == updated


def test_in_memory_research_jobs_backend_rejects_unknown_update_fields() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)
    job = ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    backend.reset(jobs=[job])

    with pytest.raises(ValueError, match="Unknown research job field: unknown_field"):
        backend.update("job-1", unknown_field="bad")

    assert backend.get("job-1") == job


def test_in_memory_research_jobs_backend_tracks_sequence_and_limits() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)

    backend.reset(next_job_sequence=4, retained_limit=3, active_limit=2)

    assert backend.next_sequence() == 4
    assert backend.retained_limit() == 3
    assert backend.active_limit() == 2
