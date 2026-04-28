# InsightGraph Deployment Guide

This guide describes a minimal MVP deployment for the InsightGraph API. It is suitable for a private demo server or internal tool, not a public multi-tenant SaaS deployment.

## Deployment Shape

Recommended MVP setup:

- Python 3.11+ virtual environment.
- `uvicorn` serving `insight_graph.api:app`.
- SQLite research job metadata storage.
- Explicit live search/LLM opt-in environment variables when needed.
- A reverse proxy or private network boundary in front of the API.

Current security boundary:
- Set `INSIGHT_GRAPH_API_KEY` to require a shared API key for `/research` and `/research/jobs/*`.
- `/health` remains public for health checks.
- Keep reverse proxy, private network, VPN, or API gateway controls for any public demo server.
- Do not pass provider API keys in request bodies or query strings. Configure providers through environment variables.

## Install

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install "uvicorn[standard]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install "uvicorn[standard]"
```

## Optional API Key Auth

Set `INSIGHT_GRAPH_API_KEY` to protect all API endpoints except `/health`:

```bash
export INSIGHT_GRAPH_API_KEY="replace-with-shared-demo-key"
```

Clients can authenticate with either header:

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Authorization: Bearer replace-with-shared-demo-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "X-API-Key: replace-with-shared-demo-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot","preset":"offline"}'
```

When `INSIGHT_GRAPH_API_KEY` is unset or blank, local development remains unauthenticated.

## Offline API Smoke Test

Start the API:

```bash
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

Run a synchronous offline research request:

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

Create an async job:

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot","preset":"offline"}'
```

Then poll:

```bash
curl http://127.0.0.1:8000/research/jobs/summary
curl http://127.0.0.1:8000/research/jobs/<job_id>
```

## SQLite Job Storage

Use SQLite when you want job metadata to survive process restarts and coordinate multiple API processes with internal worker leases.

```bash
export INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
export INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/var/lib/insightgraph/jobs.sqlite3
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

Create the parent directory before startup and make it writable by the API process:

```bash
sudo mkdir -p /var/lib/insightgraph
sudo chown "$USER":"$USER" /var/lib/insightgraph
```

SQLite behavior:
- Queued jobs remain queued across restarts.
- Expired running jobs are requeued through internal worker lease claim.
- Lease metadata is internal and never appears in API responses.
- Workflow execution is not resumed in-place; a later worker claim starts a fresh workflow attempt.

## Live LLM Demo Runtime

The API defaults to deterministic/offline behavior. To enable live LLM paths, configure an OpenAI-compatible provider and use the `live-llm` preset in requests.

```bash
export INSIGHT_GRAPH_LLM_API_KEY="replace-with-your-api-key"
export INSIGHT_GRAPH_LLM_BASE_URL="https://your-provider.example/v1"
export INSIGHT_GRAPH_LLM_MODEL="your-model"
```

Optional rules router:

```bash
export INSIGHT_GRAPH_LLM_ROUTER=rules
export INSIGHT_GRAPH_LLM_MODEL_FAST="cheap-model-alias"
export INSIGHT_GRAPH_LLM_MODEL_DEFAULT="default-model-alias"
export INSIGHT_GRAPH_LLM_MODEL_STRONG="strong-model-alias"
```

Run a live async job:

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"Technical review of AI coding agents for an engineering team","preset":"live-llm"}'
```

Live runtime notes:
- `live-llm` applies missing defaults for DuckDuckGo search, relevance filtering, LLM Analyst, and LLM Reporter.
- Provider failures are sanitized in job/API responses.
- LLM call logs store metadata only, not prompts, completions, raw responses, or API keys.

## Optional JSON Metadata Store

For a single-process demo that only needs simple metadata persistence, use the JSON store instead of SQLite:

```bash
export INSIGHT_GRAPH_RESEARCH_JOBS_PATH=/var/lib/insightgraph/jobs.json
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

JSON store behavior:
- Metadata writes use atomic replace semantics.
- On restart, unfinished queued/running JSON jobs are restored as failed with `Research job did not complete before server restart.`
- JSON persistence is not intended for multi-process coordination.

## systemd Example

Create `/etc/systemd/system/insightgraph.service`:

```ini
[Unit]
Description=InsightGraph API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/InsightGraph
Environment=INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
Environment=INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/var/lib/insightgraph/jobs.sqlite3
Environment=INSIGHT_GRAPH_LLM_BASE_URL=https://your-provider.example/v1
Environment=INSIGHT_GRAPH_LLM_MODEL=your-model
EnvironmentFile=-/etc/insightgraph/auth.env
EnvironmentFile=-/etc/insightgraph/secrets.env
ExecStart=/opt/InsightGraph/.venv/bin/uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Place secrets in `/etc/insightgraph/secrets.env` with restrictive permissions:

```bash
sudo mkdir -p /etc/insightgraph
sudo install -m 600 /dev/null /etc/insightgraph/secrets.env
```

Example `secrets.env`:

```ini
INSIGHT_GRAPH_LLM_API_KEY=replace-with-your-api-key
```

Example `/etc/insightgraph/auth.env`:

```ini
INSIGHT_GRAPH_API_KEY=replace-with-shared-demo-key
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable insightgraph
sudo systemctl start insightgraph
sudo systemctl status insightgraph
```

## Reverse Proxy Boundary

Built-in API key auth is a minimal shared-secret gate. For public demos, still expose the service through a protected boundary. Minimum options:

- Bind uvicorn to `127.0.0.1` and access through SSH tunnel or VPN.
- Put Nginx/Caddy in front with basic auth or gateway auth.
- Restrict inbound firewall rules to trusted client IPs.

Do not bind the MVP API directly to `0.0.0.0` on a public host without an external auth layer.

## Operational Checks

Health:

```bash
curl http://127.0.0.1:8000/health
```

Queue summary:

```bash
curl http://127.0.0.1:8000/research/jobs/summary
```

Recent logs with systemd:

```bash
journalctl -u insightgraph -n 100 --no-pager
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `uvicorn` command not found | Install `uvicorn[standard]` in the active virtual environment. |
| Live LLM falls back or fails | Check `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL`. |
| SQLite startup fails | Verify the parent directory exists and is writable by the API process. |
| Jobs remain queued | Check active job limit, worker logs, and whether the API process is still running. |
| Public access is needed | Put a reverse proxy or gateway with authentication in front of the API first. |
