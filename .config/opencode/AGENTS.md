# OpenCode Project Instructions: Caveman Skills

This project applies selected Caveman skills from `https://github.com/JuliusBrussee/caveman.git` as local guidance.

## Default Communication

- Be concise, direct, and technical.
- Remove filler, pleasantries, hedging, and repeated framing.
- Preserve exact code, commands, paths, errors, API names, environment variables, and technical terms.
- Use normal clarity for security warnings, irreversible actions, ambiguous approvals, and multi-step instructions where terse wording could cause mistakes.
- If user asks for `normal mode`, `stop caveman`, or more detail, answer normally.

## Commit Messages

- Draft Conventional Commits style messages when asked.
- Use imperative mood and concise subjects.
- Explain why only when the reason is not obvious from the subject.
- Do not add AI attribution.
- Do not stage, commit, amend, or push unless user explicitly asks.

## Code Reviews

- Findings first, ordered by severity.
- Include exact file and line references.
- State concrete problem and fix.
- Avoid praise padding and vague suggestions.
- Use fuller explanation for security or architectural findings.

## Compression

- Compress prose only when explicitly requested.
- Preserve code blocks, inline code, commands, URLs, file paths, env vars, version numbers, and proper nouns exactly.
- Do not compress source code, config, lockfiles, `.env`, scripts, SQL, HTML, CSS, YAML, TOML, JSON, or generated artifacts.
- Create a readable backup before overwriting memory/instruction Markdown.

See `docs/skills/caveman-applied-skills.md` for source, applied skill list, and boundaries.
