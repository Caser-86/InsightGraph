"""Tests for scripts/validate_demo_env.py."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def run_validate(env_overrides: dict[str, str] | None = None) -> tuple[int, dict]:
    env = os.environ.copy()
    env.pop("INSIGHT_GRAPH_API_KEY", None)
    env.pop("INSIGHT_GRAPH_LLM_API_KEY", None)
    env.pop("INSIGHT_GRAPH_LLM_MODEL", None)
    env.pop("INSIGHT_GRAPH_LLM_MODEL_FAST", None)
    env.pop("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", None)
    env.pop("INSIGHT_GRAPH_LLM_MODEL_STRONG", None)
    env.pop("INSIGHT_GRAPH_SERPAPI_KEY", None)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_demo_env.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {}
    return result.returncode, data


def test_missing_all_returns_fail():
    returncode, data = run_validate()
    assert returncode == 1
    labels = [r["label"] for r in data.get("results", [])]
    assert any("API" in label for label in labels)


def test_minimal_config_passes():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "test-key-at-least-16-chars",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert returncode == 0


def test_placeholder_key_returns_warning():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "replace-me-with-strong-random-key",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert returncode == 1
    assert any(r["status"] == "FAIL" and "占位符" in r["label"] for r in data.get("results", []))


def test_serpapi_no_key_requires_key():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "test-key-at-least-16-chars-long",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "serpapi",
        "INSIGHT_GRAPH_SERPAPI_KEY": "",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert returncode == 1
    assert any(r["status"] == "FAIL" and "SerpAPI" in r["label"] for r in data.get("results", []))


def test_serpapi_with_key_passes():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "test-key-at-least-16-chars-long",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "serpapi",
        "INSIGHT_GRAPH_SERPAPI_KEY": "test-serpapi-key",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert returncode == 0


def test_invalid_intensity_returns_fail():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "test-key-at-least-16-chars-long",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
        "INSIGHT_GRAPH_REPORT_INTENSITY": "invalid-intensity",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert returncode == 1
    assert any(r["status"] == "FAIL" and "报告强度" in r["label"] for r in data.get("results", []))


def test_json_output_is_valid():
    returncode, data = run_validate({
        "INSIGHT_GRAPH_API_KEY": "test-key-at-least-16-chars-long",
        "INSIGHT_GRAPH_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "INSIGHT_GRAPH_LLM_API_KEY": "sk-test",
        "INSIGHT_GRAPH_LLM_MODEL": "deepseek-chat",
        "INSIGHT_GRAPH_LLM_MODEL_FAST": "deepseek-v4-flash",
        "INSIGHT_GRAPH_LLM_MODEL_DEFAULT": "deepseek-reasoner",
        "INSIGHT_GRAPH_LLM_MODEL_STRONG": "deepseek-v4-pro",
        "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
        "INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE": "8",
        "INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE": "8",
    })
    assert "results" in data
    assert isinstance(data["results"], list)
    for r in data["results"]:
        assert "label" in r
        assert "status" in r
