from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from insight_graph.cli import (
    ResearchPreset,
    _apply_research_preset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research

app = FastAPI(title="InsightGraph API")


class ResearchRequest(BaseModel):
    query: str
    preset: ResearchPreset = ResearchPreset.offline

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    _apply_research_preset(request.preset)
    try:
        state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)
