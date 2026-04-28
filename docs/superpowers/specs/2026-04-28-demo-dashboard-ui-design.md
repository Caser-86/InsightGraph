# Demo Dashboard UI Design

## Goal

Add a lightweight browser dashboard that makes the current InsightGraph MVP demoable without adding a frontend build system. The dashboard should visually resemble the provided dark WENYI-style screenshots: dense dark surfaces, cyan/teal accents, glowing status cards, compact metrics, progress tiles, and a polished report-reading panel.

## Scope

In scope:

- Serve a static, self-contained dashboard at `GET /dashboard` from the existing FastAPI app.
- Keep `/dashboard` public so users can load the page even when `INSIGHT_GRAPH_API_KEY` is configured.
- Let the user enter an API key in the browser; API calls use `Authorization: Bearer <key>` when present.
- Support creating jobs with `POST /research/jobs` using `query` and `preset`.
- Poll `GET /research/jobs/summary`, `GET /research/jobs`, and the selected `GET /research/jobs/{job_id}`.
- Render job status, queue/running load, timestamps, result markdown, findings, competitive matrix, tool calls, LLM metadata, and errors when available.
- Provide cancel and retry controls where the public API supports them.
- Use only local inline HTML/CSS/JavaScript; no CDN, Node, React, Tailwind, or package-data build step.

Out of scope:

- Authentication sessions, cookies, or server-side dashboard login.
- WebSockets or server-sent events.
- Full Markdown compatibility; a safe minimal renderer is enough for headings, bullets, links, paragraphs, and fenced blocks.
- Editing stored jobs or changing backend persistence from the UI.

## Visual Direction

The dashboard uses a single-page dark command-center layout:

- Background: near-black navy gradient with subtle radial cyan highlights.
- Shell: rounded cards with translucent navy surfaces, thin cyan borders, and soft inner shadows.
- Accent color: teal/cyan for primary actions and active states; amber for warnings; red for failed/cancelled states; green for succeeded.
- Typography: system sans-serif with compact uppercase labels, high-contrast numerals, and generous card spacing.
- Layout: screenshot-inspired dashboard with a top query console, a metric strip, progress/job cards, tabbed detail panels, and a report reader.
- Mobile: stack all regions vertically; keep controls reachable without horizontal scrolling.

## Page Structure

The page is divided into five regions:

1. Header: `IG InsightGraph`, environment badge, health/status indicator, auto-refresh toggle.
2. Launch console: API key input, query textarea, preset selector, submit button, selected job id, manual refresh button.
3. Metrics strip: total, queued, running, succeeded, failed, active load, latest status.
4. Job timeline/list: newest jobs as compact cards with status chips, queue position, timestamps, and selection affordance.
5. Detail workspace: tabs for Overview, Report, Findings, Tool Calls, LLM Log, and Raw JSON.

## Data Flow

On page load:

1. Read `insightgraph.dashboard.apiKey`, `query`, `preset`, and selected `jobId` from `localStorage`.
2. Fetch summary and list. If auth fails, show an inline locked state and keep the API key field focused.
3. If a selected job exists, fetch its detail; otherwise select the newest job if available.
4. Poll every 2 seconds while auto-refresh is enabled and any selected/active job is `queued` or `running`; otherwise poll every 8 seconds.

On submit:

1. Validate non-blank query.
2. Send `POST /research/jobs`.
3. Store and select the returned `job_id`.
4. Refresh summary, list, and detail immediately.

On cancel/retry:

1. Call the matching job endpoint.
2. Refresh state and show a transient toast-like status message.
3. For retry, select the new queued job.

## Error Handling

- `401`: show "API key required or invalid" near the key input and keep existing dashboard data visible.
- `422`: show validation feedback from the server when possible.
- `404`: clear the selected job and select the newest available job.
- `409` and `429`: show the API detail message without hiding the page.
- Network failure: show a compact offline banner and retry on the next polling interval.
- Failed research jobs: render the safe `error` field only; never expose raw provider payloads.

## Testing

Add API tests that verify:

- `GET /dashboard` returns HTML and includes the expected root marker.
- `GET /dashboard` remains public when `INSIGHT_GRAPH_API_KEY` is configured.
- `create_app()` and module-level `app` include `/dashboard`.

Manual/browser verification should confirm:

- Desktop and narrow mobile layouts do not overflow.
- Dashboard can create and poll an offline job.
- API key field enables protected API calls when the server has `INSIGHT_GRAPH_API_KEY` set.

## Implementation Notes

- Put the dashboard HTML in a focused module such as `src/insight_graph/dashboard.py` and import it from `api.py`.
- Use FastAPI `HTMLResponse` for the route.
- Keep JavaScript dependency-free and use `fetch` with relative paths so the page works behind a reverse proxy path that preserves the API root.
- Escape all server-provided strings before inserting HTML. The minimal markdown renderer must escape first, then apply conservative formatting.
- Avoid package-data configuration by keeping the HTML as a Python string constant for this MVP.
