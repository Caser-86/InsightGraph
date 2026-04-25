from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

SubtaskType = Literal["research", "company", "product", "market", "technology", "synthesis"]
SourceType = Literal["official_site", "docs", "github", "news", "blog", "unknown"]


class Subtask(BaseModel):
    id: str
    description: str
    subtask_type: SubtaskType = "research"
    dependencies: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    subtask_id: str
    title: str
    source_url: str
    snippet: str
    source_type: SourceType = "unknown"
    verified: bool = False

    @property
    def source_domain(self) -> str:
        return urlparse(self.source_url).netloc.lower()


class Finding(BaseModel):
    title: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    passed: bool
    reason: str
    missing_topics: list[str] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    subtask_id: str
    tool_name: str
    query: str
    evidence_count: int = 0
    filtered_count: int = 0
    success: bool = True
    error: str | None = None


class GraphState(BaseModel):
    user_request: str
    subtasks: list[Subtask] = Field(default_factory=list)
    evidence_pool: list[Evidence] = Field(default_factory=list)
    global_evidence_pool: list[Evidence] = Field(default_factory=list)
    tool_call_log: list[ToolCallRecord] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    critique: Critique | None = None
    report_markdown: str | None = None
    iterations: int = 0
