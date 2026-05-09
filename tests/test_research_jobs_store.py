import json
from dataclasses import dataclass

import pytest

from insight_graph.research_jobs_store import (
    RESTART_FAILURE_ERROR,
    ResearchJobsStoreError,
    load_research_jobs,
    research_jobs_backend_from_env,
    research_jobs_path_from_env,
    research_jobs_sqlite_path_from_env,
    save_research_jobs,
    serialize_research_job,
)


@dataclass
class FakeJob:
    id: str
    query: str
    preset: object
    created_order: int
    created_at: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, object] | None = None
    error: str | None = None
    events: list[dict[str, object]] | None = None


class FakePreset:
    value = "offline"


def test_serialize_research_job_uses_public_fields() -> None:
    job = FakeJob(
        id="job-1",
        query="Compare Cursor",
        preset=FakePreset(),
        created_order=7,
        created_at="2026-04-27T10:00:00Z",
        status="succeeded",
        started_at="2026-04-27T10:00:01Z",
        finished_at="2026-04-27T10:00:02Z",
        result={"report_markdown": "# Report"},
    )

    assert serialize_research_job(job) == {
        "id": "job-1",
        "query": "Compare Cursor",
        "preset": "offline",
        "report_intensity": "standard",
        "single_entity_detail_mode": "auto",
        "relevance_judge": "deterministic",
        "search_provider": "auto",
        "web_search_mode": "auto",
        "created_order": 7,
        "created_at": "2026-04-27T10:00:00Z",
        "status": "succeeded",
        "started_at": "2026-04-27T10:00:01Z",
        "finished_at": "2026-04-27T10:00:02Z",
        "result": {"report_markdown": "# Report"},
        "error": None,
        "events": [],
    }


def test_research_jobs_path_from_env_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_PATH", raising=False)

    assert research_jobs_path_from_env() is None


def test_research_jobs_backend_from_env_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", raising=False)

    assert research_jobs_backend_from_env() == "memory"


def test_research_jobs_backend_from_env_accepts_sqlite(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "sqlite")

    assert research_jobs_backend_from_env() == "sqlite"


def test_research_jobs_backend_from_env_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND", "postgres")

    with pytest.raises(ResearchJobsStoreError, match="Unknown research jobs backend"):
        research_jobs_backend_from_env()


def test_research_jobs_sqlite_path_from_env_requires_value(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", raising=False)

    with pytest.raises(ResearchJobsStoreError, match="SQLite research jobs path is required"):
        research_jobs_sqlite_path_from_env()


def test_research_jobs_sqlite_path_from_env_returns_path(monkeypatch, tmp_path) -> None:
    path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH", str(path))

    assert research_jobs_sqlite_path_from_env() == path


def test_save_and_load_research_jobs_round_trips_terminal_jobs(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    job = FakeJob(
        id="job-1",
        query="Compare Cursor",
        preset="offline",
        created_order=3,
        created_at="2026-04-27T10:00:00Z",
        status="succeeded",
        started_at="2026-04-27T10:00:01Z",
        finished_at="2026-04-27T10:00:02Z",
        result={"report_markdown": "# Report"},
    )

    save_research_jobs(path=path, jobs=[job], next_job_sequence=3)
    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert loaded.next_job_sequence == 3
    assert loaded.jobs == [serialize_research_job(job)]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["next_job_sequence"] == 3
    assert raw["jobs"][0]["id"] == "job-1"


def test_save_and_load_research_jobs_round_trips_events(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    job = FakeJob(
        id="job-1",
        query="Compare Cursor",
        preset="offline",
        created_order=3,
        created_at="2026-04-27T10:00:00Z",
        status="succeeded",
        started_at="2026-04-27T10:00:01Z",
        finished_at="2026-04-27T10:00:02Z",
        result={"report_markdown": "# Report"},
        events=[{"type": "stage_started", "stage": "planner", "sequence": 1}],
    )

    save_research_jobs(path=path, jobs=[job], next_job_sequence=3)
    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert loaded.jobs[0]["events"] == [
        {"type": "stage_started", "stage": "planner", "sequence": 1}
    ]


def test_load_research_jobs_accepts_legacy_jobs_without_events(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "next_job_sequence": 1,
                "jobs": [
                    {
                        "id": "job-1",
                        "query": "Legacy",
                        "preset": "offline",
                        "created_order": 1,
                        "created_at": "2026-04-27T10:00:00Z",
                        "status": "succeeded",
                        "started_at": "2026-04-27T10:00:01Z",
                        "finished_at": "2026-04-27T10:00:02Z",
                        "result": {"report_markdown": "# Report"},
                        "error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert loaded.jobs[0]["events"] == []


def test_load_research_jobs_marks_unfinished_jobs_failed(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "next_job_sequence": 2,
                "jobs": [
                    {
                        "id": "queued-job",
                        "query": "Queued",
                        "preset": "offline",
                        "created_order": 1,
                        "created_at": "2026-04-27T10:00:00Z",
                        "status": "queued",
                        "started_at": None,
                        "finished_at": None,
                        "result": None,
                        "error": None,
                    },
                    {
                        "id": "running-job",
                        "query": "Running",
                        "preset": "offline",
                        "created_order": 2,
                        "created_at": "2026-04-27T10:00:01Z",
                        "status": "running",
                        "started_at": "2026-04-27T10:00:02Z",
                        "finished_at": None,
                        "result": None,
                        "error": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_research_jobs(
        path=path,
        restart_timestamp="2026-04-27T11:00:00Z",
    )

    assert [job["status"] for job in loaded.jobs] == ["failed", "failed"]
    assert [job["finished_at"] for job in loaded.jobs] == [
        "2026-04-27T11:00:00Z",
        "2026-04-27T11:00:00Z",
    ]
    assert [job["error"] for job in loaded.jobs] == [
        RESTART_FAILURE_ERROR,
        RESTART_FAILURE_ERROR,
    ]


def test_load_research_jobs_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ResearchJobsStoreError):
        load_research_jobs(path=path, restart_timestamp="2026-04-27T11:00:00Z")


def test_load_research_jobs_rejects_boolean_sequence(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps({"next_job_sequence": True, "jobs": []}),
        encoding="utf-8",
    )

    with pytest.raises(ResearchJobsStoreError):
        load_research_jobs(path=path, restart_timestamp="2026-04-27T11:00:00Z")


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 123),
        ("query", 123),
        ("preset", 123),
        ("preset", []),
        ("created_order", "1"),
        ("created_order", True),
        ("created_at", 123),
        ("status", "paused"),
        ("status", {}),
        ("single_entity_detail_mode", 123),
        ("single_entity_detail_mode", "invalid"),
        ("search_provider", 123),
        ("search_provider", "bing"),
        ("web_search_mode", 123),
        ("web_search_mode", "disabled"),
        ("started_at", 123),
        ("finished_at", 123),
        ("result", "not-object"),
        ("error", 123),
    ],
)
def test_load_research_jobs_rejects_invalid_job_values(
    tmp_path,
    field: str,
    value: object,
) -> None:
    path = tmp_path / "jobs.json"
    job = {
        "id": "job-1",
        "query": "Compare Cursor",
        "preset": "offline",
        "created_order": 1,
        "created_at": "2026-04-27T10:00:00Z",
        "status": "succeeded",
        "started_at": None,
        "finished_at": "2026-04-27T10:00:01Z",
        "result": {"report_markdown": "# Report"},
        "error": None,
    }
    job[field] = value
    path.write_text(
        json.dumps({"next_job_sequence": 1, "jobs": [job]}),
        encoding="utf-8",
    )

    with pytest.raises(ResearchJobsStoreError):
        load_research_jobs(path=path, restart_timestamp="2026-04-27T11:00:00Z")
