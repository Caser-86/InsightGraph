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

## Public Demo Hardening Checklist

Before exposing a demo beyond a private machine or VPN, verify:

- `uvicorn` binds to `127.0.0.1`; only the reverse proxy listens on public interfaces.
- TLS terminates at the reverse proxy or gateway.
- `INSIGHT_GRAPH_API_KEY` is set to a high-entropy value and stored outside the repo.
- API keys are rotated by updating `/etc/insightgraph/auth.env` and restarting the service.
- Provider secrets live in `/etc/insightgraph/secrets.env` with mode `600`.
- Request bodies, headers, query strings, and provider payloads are not logged by the proxy.
- SQLite or JSON job-store files are owned by the service user and not world-readable.
- SQLite/job-store backups exclude provider API keys and are protected like application data.
- Reverse proxy or API gateway rate limits are enabled for `/research` and `/research/jobs/*`.
- `/health` remains reachable for uptime checks but does not expose secrets or job details.

Built-in rate limiting is not part of this MVP. Use Nginx, Caddy, a cloud load balancer,
or an API gateway to enforce request limits for public demos.

## Reverse Proxy Requirements

Minimum reverse proxy behavior:

- Forward `Authorization` and `X-API-Key` headers unchanged.
- Preserve WebSocket upgrade headers for `/research/jobs/<job_id>/stream`.
- Set conservative request body size limits; research queries are text prompts, not uploads.
- Disable access-log capture of sensitive headers and full request bodies.
- Return generic upstream error pages instead of raw backend tracebacks.

If the dashboard is used through the proxy, confirm WebSocket streaming works from the
browser. If WebSockets are blocked, the dashboard falls back to REST polling but live
event latency increases.

## Nginx Example

This example terminates HTTPS at Nginx, forwards REST and WebSocket traffic to a local
uvicorn process, and applies a small request-rate limit to research endpoints. Replace
`insightgraph.example.com` and certificate paths for your host.

```nginx
# Place these directives in the Nginx `http` context.
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

log_format insightgraph_safe '$remote_addr - $remote_user [$time_local] '
                             '"$request_method $uri $server_protocol" $status '
                             '$body_bytes_sent "$http_referer" "$http_user_agent"';

limit_req_zone $binary_remote_addr zone=insightgraph_research:10m rate=30r/m;

server {
    listen 443 ssl http2;
    server_name insightgraph.example.com;

    ssl_certificate /etc/letsencrypt/live/insightgraph.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/insightgraph.example.com/privkey.pem;

    client_max_body_size 1m;

    access_log /var/log/nginx/insightgraph.access.log insightgraph_safe;
    error_log /var/log/nginx/insightgraph.error.log warn;

    location /research {
        limit_req zone=insightgraph_research burst=10 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-API-Key $http_x_api_key;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-API-Key $http_x_api_key;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}

server {
    listen 80;
    server_name insightgraph.example.com;
    return 301 https://$host$request_uri;
}
```

Use a log format like `insightgraph_safe` that records `$uri`, not `$request_uri`, so
dashboard WebSocket API keys are not written through query strings. If your deployment
adds custom log formats, do not log `Authorization`, `X-API-Key`, request bodies, or
full query strings.

## Caddy Example

Caddy can manage TLS automatically. This example proxies to uvicorn on localhost and
applies a request body limit. Use a Caddy rate-limit plugin or an upstream gateway if
you need per-client throttling.

```caddyfile
insightgraph.example.com {
    request_body {
        max_size 1MB
    }

    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up Authorization {header.Authorization}
        header_up X-API-Key {header.X-API-Key}
    }
}
```

Caddy's `reverse_proxy` handles WebSocket upgrades automatically. Confirm the dashboard
shows `WebSocket: connected` for a running job before using it for demos.
If you enable Caddy access logging, configure it so credentials and full query strings
are not written to disk.

## Proxy Verification

After deploying the proxy, verify the public boundary rather than only localhost:

```bash
curl https://insightgraph.example.com/health
curl -H "Authorization: Bearer $INSIGHT_GRAPH_API_KEY" \
  https://insightgraph.example.com/research/jobs/summary
```

Open `https://insightgraph.example.com/dashboard`, save the API key in the dashboard,
start a short research job, and confirm the status line reports `WebSocket: connected`.
If it stays on polling, review the proxy WebSocket upgrade configuration.

You can also run the deployment smoke test script against the public URL:

```bash
INSIGHT_GRAPH_API_KEY=change-me insight-graph-smoke https://insightgraph.example.com
```

The script checks `/health`, `/dashboard`, and `/research/jobs/summary`. It exits `0`
when all checks pass, `1` when any endpoint check fails, and `2` for invalid CLI input.
It emits JSON and does not print the API key.

## Storage and Backup Notes

For SQLite deployments:

- Keep `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH` under a directory owned by the service user.
- Back up the SQLite file with the service stopped, or use SQLite backup tooling.
- Treat job metadata as operational data; reports may include research queries and summaries.
- Use filesystem permissions to prevent unrelated local users from reading job history.

For JSON metadata storage:

- Use it only for single-process demos.
- Do not share the JSON file between multiple API workers.
- Back up the file with the service stopped to avoid copying a partially replaced file.

## Secret Handling Notes

Never pass provider keys or the shared API key in request bodies, dashboard URLs, shell
history snippets, or issue reports. Configure them through environment files or your
deployment platform's secret manager.

The application intentionally keeps LLM observability metadata safe: it records provider,
model, router, duration, success state, and sanitized errors, not prompts, completions,
headers, raw provider payloads, or API keys.

## Operational Checks

Deployment smoke test:

```bash
INSIGHT_GRAPH_API_KEY=change-me insight-graph-smoke http://127.0.0.1:8000
```

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
