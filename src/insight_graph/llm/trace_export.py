from typing import Any


def build_full_trace_event(
    *,
    stage: str,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    output_text: str,
    token_usage: dict[str, int | None],
    include_payload: bool = False,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "stage": stage,
        "provider": provider,
        "model": model,
        "token_usage": {key: value for key, value in token_usage.items() if value is not None},
    }
    if include_payload:
        event["messages"] = messages
        event["output_text"] = output_text
    return event
