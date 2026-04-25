from insight_graph.state import Evidence


def news_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="news-github-copilot-changelog",
            subtask_id=subtask_id,
            title="GitHub Copilot Product Changelog",
            source_url="https://github.blog/changelog/",
            snippet=(
                "GitHub's changelog publishes product updates and release notes for "
                "GitHub Copilot and adjacent developer platform features."
            ),
            source_type="news",
            verified=True,
        ),
        Evidence(
            id="news-openai-codex-update",
            subtask_id=subtask_id,
            title="OpenAI Codex Product Update",
            source_url="https://openai.com/index/introducing-codex/",
            snippet=(
                "OpenAI's Codex announcement describes product capabilities and release "
                "context for cloud-based coding assistance."
            ),
            source_type="news",
            verified=True,
        ),
        Evidence(
            id="news-cursor-changelog",
            subtask_id=subtask_id,
            title="Cursor Product Changelog",
            source_url="https://www.cursor.com/changelog",
            snippet=(
                "Cursor's changelog tracks product updates, feature launches, and release "
                "signals for the AI coding editor."
            ),
            source_type="news",
            verified=True,
        ),
    ]
