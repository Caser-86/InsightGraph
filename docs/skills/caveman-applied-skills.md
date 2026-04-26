# Caveman Applied Skills

Source: `https://github.com/JuliusBrussee/caveman.git`

Observed upstream HEAD: `84cc3c14fa1e10182adaced856e003406ccd250d`

Applied date: `2026-04-27`

## Integration Scope

This project applies Caveman skills as local project guidance for OpenCode. The integration does not install global hooks, does not change machine-level agent settings, and does not vendor the full upstream repository.

Local instruction file:

- `.config/opencode/AGENTS.md`

## Applied Skills

### caveman

Purpose: reduce conversational output tokens while preserving technical substance.

Project rule:

- Prefer concise, direct responses.
- Drop filler, pleasantries, hedging, and repeated framing.
- Keep exact technical terms, commands, code, errors, paths, and API names.
- Use normal clarity for security warnings, destructive actions, ambiguous approvals, and multi-step instructions where terse fragments could be misread.

Triggers:

- User asks for `caveman mode`, `talk like caveman`, `less tokens`, or equivalent.
- User asks for concise status/progress.

Stop triggers:

- User asks for `normal mode`, `stop caveman`, or more detail.

### caveman-commit

Purpose: generate terse, accurate commit messages.

Project rule:

- Use Conventional Commits style when drafting commit messages.
- Prefer `why` over restating the file diff.
- Keep subject concise, imperative, and without trailing period.
- Include body only for breaking changes, migrations, security fixes, reversions, or non-obvious rationale.
- Do not add AI attribution.

Boundary:

- This skill drafts commit messages only. It does not stage, commit, amend, or push unless the user explicitly asks.

### caveman-review

Purpose: make code review comments terse and actionable.

Project rule:

- Findings first, ordered by severity.
- Use exact file and line references.
- Each finding should state problem and concrete fix.
- Avoid praise padding and speculative language.
- Use fuller explanation for security findings, architectural tradeoffs, or onboarding context.

Boundary:

- This skill reviews changes only. It does not approve, request changes, or implement fixes unless the user explicitly asks.

### caveman-compress

Purpose: compress natural-language memory or instruction files while preserving technical content.

Project rule:

- Compress only Markdown, text, or instruction prose when explicitly requested.
- Preserve code blocks, inline code, commands, URLs, paths, environment variables, version numbers, dates, and proper nouns exactly.
- Keep Markdown heading structure and list hierarchy.
- Create a human-readable backup before overwriting any memory/instruction file.

Boundary:

- Do not compress source code, config files, lockfiles, `.env` files, scripts, SQL, HTML, CSS, YAML, TOML, JSON, or generated artifacts.
- Do not run upstream compression scripts automatically; they may invoke external LLM tooling.

## Project-Specific Notes

- InsightGraph defaults should remain deterministic/offline unless live behavior is explicitly opt-in.
- Security-sensitive output remains explicit rather than compressed.
- Test/build verification claims still require fresh command output before reporting success.
- Existing repository workflow with `docs/superpowers/specs` and `docs/superpowers/plans` remains unchanged.

## Upstream Files Reviewed

- `README.md`
- `AGENTS.md`
- `skills/caveman/SKILL.md`
- `skills/caveman-commit/SKILL.md`
- `skills/caveman-review/SKILL.md`
- `caveman-compress/SKILL.md`
