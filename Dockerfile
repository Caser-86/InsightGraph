FROM python:3.11-slim

LABEL org.opencontainers.image.title="InsightGraph"
LABEL org.opencontainers.image.description="LangGraph Multi-Agent Deep Research Engine"
LABEL org.opencontainers.image.version="0.1.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY README.md .

RUN mkdir -p /data /reports /logs

ENV PYTHONPATH=/app/src
ENV INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
ENV INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/data/research_jobs.db

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "insight_graph.api:app", "--host", "0.0.0.0", "--port", "8000"]
