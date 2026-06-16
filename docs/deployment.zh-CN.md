# InsightGraph 服务器演示版部署指南

## 服务器规格建议

| 场景 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 演示 (concise/standard) | 2C | 4G | 20G SSD |
| 推荐 (deep) | 4C | 8G | 40G SSD |
| 高强度 (deep-plus) | 8C | 16G | 80G SSD |

## 前置条件

- Docker 24+
- Docker Compose v2
- 2G 以上可用磁盘空间（不含模型）

## 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph

# 2. 创建配置文件
cp .env.example .env
# 编辑 .env，填入 LLM API key 和其他必要配置

# 3. 编译并启动
docker compose up -d

# 4. 验证
curl http://localhost:8000/health
# 应返回 {"status":"ok"}
```

## 环境变量关键配置

```ini
# 必填
INSIGHT_GRAPH_LLM_API_KEY=sk-your-key
INSIGHT_GRAPH_LLM_BASE_URL=https://api.deepseek.com/v1

# 演示建议
INSIGHT_GRAPH_API_KEY=         # 设为强随机字符串以保护接口
INSIGHT_GRAPH_REPORT_INTENSITY=standard
INSIGHT_GRAPH_RELEVANCE_JUDGE=deterministic
INSIGHT_GRAPH_CITATION_JUDGE_PROVIDER=lexical
INSIGHT_GRAPH_RELEVANCE_MODEL=deepseek-v4-flash
```

## 访问 Dashboard

浏览器打开 `http://<服务器IP>:8000/dashboard`

如果配置了 Nginx 反代，则为 `https://<域名>/dashboard`

## 数据持久化

以下目录已通过 Docker volume 挂载：

| 目录 | 用途 |
|------|------|
| `./data` | SQLite job 数据库、运行时数据 |
| `./reports` | 下载的报告输出 |
| `./logs` | 应用日志 |

## 备份

```bash
# 备份 SQLite 数据库
cp data/research_jobs.db backups/research_jobs_$(date -u +%Y%m%dT%H%M%SZ).db

# 停止服务
docker compose down

# 恢复备份
cp backups/research_jobs_20260101T000000Z.db data/research_jobs.db
docker compose up -d
```

## 停止

```bash
docker compose down
```
