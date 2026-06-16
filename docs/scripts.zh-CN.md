# InsightGraph 脚本说明

这份文档说明项目中适合直接使用的脚本，重点覆盖本地研究、日志、验证、评测和 Dashboard 启动。

## 常用脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/run_research.py` | 运行一次研究任务，输出 Markdown 或 JSON |
| `scripts/run_with_llm_log.py` | 运行任务并输出安全 LLM 元数据日志 |
| `scripts/start_dashboard.ps1` | Windows 本地 Dashboard 稳定启动脚本，带健康检查和端口回退 |
| `scripts/dashboard_status.ps1` | 查看脚本托管的 Dashboard 进程、地址和健康状态 |
| `scripts/stop_dashboard.ps1` | 停止脚本托管的本地 Dashboard |
| `scripts/validate_sources.py` | 离线验证引用和 References |
| `scripts/benchmark_research.py` | 离线 benchmark |
| `scripts/benchmark_live_research.py` | 手动 opt-in live benchmark |
| `scripts/validate_document_reader.py` | 验证本地文档读取 |
| `scripts/validate_pdf_fetch.py` | 验证 PDF 抓取与检索 |
| `insight-graph-smoke` | API / Dashboard 部署 smoke |

## Dashboard 稳定启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\dashboard_status.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\stop_dashboard.ps1
```

`start_dashboard.ps1` 会自动注入本地 `src` 路径、选择可用端口、写入 `.runtime/insightgraph-dashboard.json`，并等待 `/health` 返回正常。浏览器应打开 `dashboard_status.ps1` 输出的 Dashboard URL。

## 研究与验证示例

```bash
python scripts/run_research.py "Analyze Xiaomi EV strategy"
python scripts/run_with_llm_log.py "Analyze Xiaomi EV strategy"
python scripts/benchmark_research.py --markdown
python scripts/validate_sources.py report.md --markdown
```
