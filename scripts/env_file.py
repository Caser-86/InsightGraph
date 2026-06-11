from __future__ import annotations

import os
from pathlib import Path


def load_env_file() -> None:
    env_file = os.environ.get("INSIGHT_GRAPH_ENV_FILE")
    env_path = (
        Path(env_file)
        if env_file is not None
        else Path(__file__).resolve().parent.parent / ".env"
    )
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            os.environ.setdefault(key, _strip_env_value(value.strip()))


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
