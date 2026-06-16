# Contributing

Thanks for helping improve InsightGraph.

This project is already functionally complete for its current scope, so most
contributions should focus on:

- bug fixes
- report quality improvements
- documentation clarity
- test reliability
- safe operational hardening

## Before You Start

Read these first:

- `README.md`
- `docs/README.md`
- `docs/roadmap.md`
- `docs/report-quality-roadmap.md`

Keep the core product truth in mind:

- product path is `live-research`
- offline remains the deterministic testing/CI fallback
- high-risk runtime expansion stays opt-in or deferred unless explicitly approved

## Local Setup

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Recommended Workflow

1. Create a focused branch.
2. Make the smallest coherent change.
3. Update docs when behavior or operator guidance changes.
4. Add or update tests when behavior changes.
5. Run local verification before opening a PR.

Suggested branch names:

- `feat/<topic>`
- `fix/<topic>`
- `docs/<topic>`
- `test/<topic>`

## Required Verification

Run these before submitting:

```bash
python -m ruff check .
python -m pytest
git diff --check
```

If you touch only a small surface, also run focused tests first.

## Commit Style

Use Conventional Commits:

- `feat:`
- `fix:`
- `docs:`
- `refactor:`
- `test:`
- `chore:`

Examples:

- `fix: harden report retry state handling`
- `docs: clarify restart and resume behavior`
- `test: cover memory writeback edge cases`

## Pull Request Expectations

A good PR should:

- explain what changed
- explain why it changed
- mention user-facing behavior changes
- mention test coverage or verification commands
- link relevant issues when applicable

## What To Avoid

Do not introduce these by default without explicit approval:

- always-on live network behavior
- automatic MCP runtime invocation
- real sandboxed Python/code execution
- release/deploy automation that pushes or force-pushes
- behavior drift away from the documented `live-research` route

## Documentation Contributions

Documentation changes are welcome and encouraged.

When updating docs:

- keep public docs concise and stable
- keep operator docs practical
- keep internal roadmap/reference docs clearly separated
- prefer normal UTF-8 text and avoid mixed-encoding content

## Bug Reports

When filing a bug, include:

- a short description
- reproduction steps
- expected result
- actual result
- environment details
- relevant logs or stack traces

## Security

Do not publish secrets, provider keys, or sensitive trace payloads in issues or
PRs.

For trace-related debugging, prefer safe metadata logs instead of raw
prompt/completion content.

## Code Of Conduct

Please follow [CODE_OF_CONDUCT.md](D:/Files/opencode.files/CODE_OF_CONDUCT.md).
