import pytest

from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
from insight_graph.state import Evidence, Subtask


def make_evidence(**overrides) -> Evidence:
    data = {
        "id": "e1",
        "subtask_id": "collect",
        "title": "Cursor Pricing",
        "source_url": "https://cursor.com/pricing",
        "snippet": "Cursor pricing page.",
        "verified": True,
    }
    data.update(overrides)
    return Evidence(**data)


def test_deterministic_judge_keeps_complete_verified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence()

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="e1",
        relevant=True,
        reason="Evidence is verified and has required content.",
    )


def test_deterministic_judge_rejects_unverified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(verified=False)

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == "Evidence is not verified."


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("title", "Evidence title is empty."),
        ("source_url", "Evidence source URL is empty."),
        ("snippet", "Evidence snippet is empty."),
    ],
)
def test_deterministic_judge_rejects_empty_required_content(field: str, reason: str) -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(**{field: "   "})

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == reason


def test_get_relevance_judge_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", raising=False)

    assert isinstance(get_relevance_judge(), DeterministicRelevanceJudge)


def test_get_relevance_judge_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown relevance judge"):
        get_relevance_judge("unknown")


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE"])
def test_relevance_filter_enabled_for_truthy_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_relevance_filter_disabled_for_other_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is False



def test_filter_relevant_evidence_returns_kept_items_and_filtered_count() -> None:
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = [
        make_evidence(id="kept"),
        make_evidence(id="filtered", verified=False),
    ]

    kept, filtered_count = filter_relevant_evidence(
        "Compare AI coding agents",
        subtask,
        evidence,
        judge=DeterministicRelevanceJudge(),
    )

    assert [item.id for item in kept] == ["kept"]
    assert filtered_count == 1
