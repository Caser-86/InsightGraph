from insight_graph.state import Evidence


def github_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="github-opencode-repository",
            subtask_id=subtask_id,
            title="OpenCode Repository",
            source_url="https://github.com/sst/opencode",
            snippet=(
                "The OpenCode repository provides public project information, README "
                "content, and release history for an AI coding tool."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-copilot-docs-content",
            subtask_id=subtask_id,
            title="GitHub Docs Copilot Content",
            source_url="https://github.com/github/docs/tree/main/content/copilot",
            snippet=(
                "The GitHub Docs repository contains public Copilot documentation content "
                "covering product behavior, integrations, and enterprise guidance."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-ai-coding-assistant-ecosystem",
            subtask_id=subtask_id,
            title="AI Coding Assistant Ecosystem Repository",
            source_url="https://github.com/safishamsi/graphify",
            snippet=(
                "This GitHub repository describes AI coding assistant tooling across "
                "Claude Code, Codex, OpenCode, Cursor, Gemini CLI, and GitHub Copilot CLI."
            ),
            source_type="github",
            verified=True,
        ),
    ]
