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


def test_in_memory_research_jobs_backend_counts_active_jobs() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)
    backend.reset(
        jobs=[
            ResearchJob(
                id="queued",
                query="Queued",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
            ),
            ResearchJob(
                id="running",
                query="Running",
                preset=ResearchPreset.offline,
                created_order=2,
                created_at="2026-04-28T10:00:01Z",
                status="running",
            ),
            ResearchJob(
                id="done",
                query="Done",
                preset=ResearchPreset.offline,
                created_order=3,
                created_at="2026-04-28T10:00:02Z",
                status="succeeded",
            ),
        ]
    )

    assert backend.active_count() == 2


def test_in_memory_research_jobs_backend_prunes_oldest_terminal_jobs_only() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)
    backend.reset(
        retained_limit=1,
        jobs=[
            ResearchJob(
                id="old-finished",
                query="Old",
                preset=ResearchPreset.offline,
                created_order=1,
                created_at="2026-04-28T10:00:00Z",
                status="succeeded",
            ),
            ResearchJob(
                id="queued",
                query="Queued",
                preset=ResearchPreset.offline,
                created_order=2,
                created_at="2026-04-28T10:00:01Z",
            ),
            ResearchJob(
                id="new-finished",
                query="New",
                preset=ResearchPreset.offline,
                created_order=3,
                created_at="2026-04-28T10:00:02Z",
                status="failed",
            ),
        ],
    )

    backend.prune_finished()

    assert backend.get("old-finished") is None
    assert backend.get("queued") is not None
    assert backend.get("new-finished") is not None


def test_in_memory_research_jobs_backend_snapshot_restores_jobs_and_sequence() -> None:
    backend = InMemoryResearchJobsBackend(store_path=None)
    original = ResearchJob(
        id="job-1",
        query="Original",
        preset=ResearchPreset.offline,
        created_order=1,
        created_at="2026-04-28T10:00:00Z",
    )
    backend.reset(next_job_sequence=1, jobs=[original])
    snapshot = backend.snapshot()

    backend.reset(next_job_sequence=2)
    backend.restore(snapshot)

    assert backend.next_sequence() == 1
    assert backend.get("job-1") == original
