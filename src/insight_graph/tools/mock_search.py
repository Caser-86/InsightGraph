from insight_graph.state import Evidence


def mock_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="cursor-pricing",
            subtask_id=subtask_id,
            title="Cursor Pricing",
            source_url="https://cursor.com/pricing",
            snippet="Cursor publishes product tiers and pricing on its official pricing page.",
            source_type="official_site",
            verified=True,
        ),
        Evidence(
            id="github-copilot-docs",
            subtask_id=subtask_id,
            title="GitHub Copilot Documentation",
            source_url="https://docs.github.com/copilot",
            snippet=(
                "GitHub Copilot documentation describes IDE integrations and enterprise "
                "features."
            ),
            source_type="docs",
            verified=True,
        ),
        Evidence(
            id="opencode-github",
            subtask_id=subtask_id,
            title="OpenCode Repository",
            source_url="https://github.com/sst/opencode",
            snippet=(
                "The OpenCode repository provides public project information, README "
                "content, and release history."
            ),
            source_type="github",
            verified=True,
        ),
    ]
