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
    chunk_index: int | None = None
    document_page: int | None = None
    section_heading: str | None = None
    section_id: str | None = None

    @property
    def source_domain(self) -> str:
        return urlparse(self.source_url).netloc.lower()


class Finding(BaseModel):
    title: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class CompetitiveMatrixRow(BaseModel):
    product: str
    positioning: str
    strengths: list[str] = Field(default_factory=list)
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
    round_index: int = 1
    section_id: str | None = None
    stop_reason: str | None = None


class LLMCallRecord(BaseModel):
    stage: str
    provider: str
    model: str
    wire_api: str | None = None
    router: str | None = None
    router_tier: str | None = None
    router_reason: str | None = None
    router_message_chars: int | None = None
    success: bool
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None


class GraphState(BaseModel):
    user_request: str
    domain_profile: str | None = None
    resolved_entities: list[dict[str, object]] = Field(default_factory=list)
    section_research_plan: list[dict[str, object]] = Field(default_factory=list)
    section_collection_status: list[dict[str, object]] = Field(default_factory=list)
    evidence_scores: list[dict[str, object]] = Field(default_factory=list)
    citation_support: list[dict[str, object]] = Field(default_factory=list)
    replan_requests: list[dict[str, object]] = Field(default_factory=list)
    subtasks: list[Subtask] = Field(default_factory=list)
    evidence_pool: list[Evidence] = Field(default_factory=list)
    global_evidence_pool: list[Evidence] = Field(default_factory=list)
    tool_call_log: list[ToolCallRecord] = Field(default_factory=list)
    llm_call_log: list[LLMCallRecord] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    competitive_matrix: list[CompetitiveMatrixRow] = Field(default_factory=list)
    critique: Critique | None = None
    report_markdown: str | None = None
    iterations: int = 0
    collection_rounds: list[dict[str, object]] = Field(default_factory=list)
    collection_stop_reason: str | None = None
    tried_strategies: list[str] = Field(default_factory=list)
