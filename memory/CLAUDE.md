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
- `INSIGHT_GRAPH_LLM_API_KEY=sk-9ee03adb2ddc43ff8a5ce4a09887d224`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`
- User wants model: `deepseek-v4-pro`

### Reports Generated
1. `reports/xiaomi-full-analysis.md` (10k chars, 11 chapters)
2. `reports/xiaomi-serpapi-analysis.md` (4.5k, real search)
3. `reports/xiaomi-duckduckgo-analysis.md` (1.4k, DDG)
4. `reports/deepseek-apple-analysis.md` (3.3k)
5. `reports/ai-coding-tools-deep-analysis.md` (3.5k)

### Verifications
- Search: `$env:PYTHONPATH='src'; python -m pytest tests/test_web_search.py -q`
- Ruff: `$env:PYTHONPATH='src'; python -m ruff check src/insight_graph/tools/search_providers.py`
- Git: `git diff --check`

### Project Structure
- `src/insight_graph/` - core (api.py, graph.py, agents/, tools/, llm/)
- `tests/` - pytest
- `docs/` - configuration, deployment, roadmap, glossary
- `reports/` - generated reports
