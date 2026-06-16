import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class McpToolSpec:
    name: str
    description: str
    endpoint: str


def load_mcp_tool_specs() -> list[McpToolSpec]:
    raw_value = os.environ.get("INSIGHT_GRAPH_MCP_TOOLS_JSON", "").strip()
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    specs: list[McpToolSpec] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        description = item.get("description")
        endpoint = item.get("endpoint")
        if all(isinstance(value, str) and value.strip() for value in [name, description, endpoint]):
            specs.append(
                McpToolSpec(
                    name=name.strip(),
                    description=description.strip(),
                    endpoint=endpoint.strip(),
                )
            )
    return specs
