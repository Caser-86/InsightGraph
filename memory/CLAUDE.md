# InsightGraph Project Context

## Project Overview
- Multi-agent deep research engine (LangGraph)
- Product path: `live-research`
- Goal: high-quality, verifiable deep research reports
- Offline fallback for tests/CI

## Status
- **Batch A-F**: Complete
- **Deferred**: MCP, sandboxed Python, `/tasks` API, release automation
- **Docs**: Roadmap updated, A-F complete marked

## Search Engines
| Engine | Status | Config |
|--------|--------|--------|
| **SerpAPI** | Working | `INSIGHT_GRAPH_SERPAPI_KEY` |
| **DuckDuckGo** | Working (CN, no proxy) | `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` |
| **Google API** | 403 - closed to new customers | N/A |

## Key Configs
- `INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1`
- `INSIGHT_GRAPH_LLM_API_KEY=sk-9ee03adb2ddc43ff8a5ce4a09887d224`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`
- Default model: deepseek-v4-pro (user request)

## Reports Generated
1. `xiaomi-full-analysis.md` - 10,296 chars (DeepSeek direct)
2. `xiaomi-serpapi-analysis.md` - 4,558 chars (SerpAPI+DeepSeek)
3. `xiaomi-duckduckgo-analysis.md` - 1,441 chars (DDG+DeepSeek)
4. `deepseek-apple-analysis.md` - Apple mock data analysis
5. `ai-coding-tools-deep-analysis.md` - Cursor/Copilot/OpenCode comparison

## User Preferences
- Language: Chinese
- Default model: deepseek-v4-pro
- Proxy: V2Ray at 173.254.236.217:37612 (not working for DDGS)
- Desired engines: Bing (MS Edge), Google

## Session Summary
- Xiaomi reports generated with real search data (SerpAPI, DDG)
- Google Custom Search API closed to new customers (verified from Google docs)
- DuckDuckGo works in CN via Brave Search backend
- All reports committed to master
