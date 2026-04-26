import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
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


@contextmanager
def _research_preset_environment(preset: ResearchPreset) -> Iterator[None]:
    if preset == ResearchPreset.offline:
        yield
        return

    previous_values = {name: os.environ.get(name) for name in LIVE_LLM_PRESET_DEFAULTS}
    try:
        for name, value in LIVE_LLM_PRESET_DEFAULTS.items():
            os.environ.setdefault(name, value)
        yield
    finally:
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/research")
def research(request: ResearchRequest) -> dict[str, Any]:
    try:
        with _research_preset_environment(request.preset):
            state = run_research(request.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research workflow failed.") from exc
    return _build_research_json_payload(state)
