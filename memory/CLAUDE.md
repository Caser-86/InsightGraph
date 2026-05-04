## InsightGraph Project Context
Product: multi-agent deep research (LangGraph). Goal: high-quality verifiable reports. Path: `live-research`. Offline=CI fallback.

### Status
Batch A-F complete. Deferred: MCP sandbox /tasks release - need explicit decision.

### Search Engines
- **DuckDuckGo**: works CN no proxy. Env: `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`
- **SerpAPI**: works 100 free/mo. Env: `INSIGHT_GRAPH_SERPAPI_KEY`
- **Google API**: dead for new users. 403. Confirmed closed 2026-02-18.
- **Mock**: default, offline only

### Key Env Vars
- `INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1`
- `INSIGHT_GRAPH_LLM_API_KEY=<set in local .env; never commit>`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`
- User wants model: `deepseek-reasoner`

### Reports Generated
Generated reports are local artifacts and should not be committed.

### Verifications
- Search: `$env:PYTHONPATH='src'; python -m pytest tests/test_web_search.py -q`
- Ruff: `$env:PYTHONPATH='src'; python -m ruff check src/insight_graph/tools/search_providers.py`
- Git: `git diff --check`

### Project Structure
- `src/insight_graph/` - core (api.py, graph.py, agents/, tools/, llm/)
- `tests/` - pytest
- `docs/` - configuration, deployment, roadmap, glossary
- `reports/` - generated reports
