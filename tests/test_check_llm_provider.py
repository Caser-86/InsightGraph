import json
import os
import subprocess
import sys
from pathlib import Path

import scripts.check_llm_provider as check_llm_provider


def test_main_fails_for_non_json_model_response(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_llm_provider, "load_env_file", lambda: None)
    monkeypatch.setattr(
        check_llm_provider,
        "check_model",
        lambda label, model: {
            "label": label,
            "status": "non-json: plain text",
            "model": model,
        },
    )
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    assert check_llm_provider.main() == 1

    output = capsys.readouterr().out
    assert "non-json" in output


def test_import_does_not_load_env_file() -> None:
    repo_root = Path(__file__).parents[1]
    env = os.environ.copy()
    env.pop("INSIGHT_GRAPH_LLM_MODEL_FAST", None)
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import scripts.check_llm_provider; "
                "print(os.environ.get('INSIGHT_GRAPH_LLM_MODEL_FAST', ''))"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
        check=True,
    )

    assert result.stdout.strip() == ""


def test_check_model_closes_provider_response(monkeypatch) -> None:
    class FakeResponse:
        closed = False

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            self.closed = True

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": '{"status":"ok"}'}},
                    ],
                    "usage": {"total_tokens": 1},
                }
            ).encode("utf-8")

    response = FakeResponse()
    captured_payload: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured_payload.update(json.loads(request.data.decode("utf-8")))
        return response

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "sk-test")

    result = check_llm_provider.check_model("fast", "fast-model")

    assert result["status"] == "PASS"
    assert captured_payload["max_tokens"] >= 512
    assert response.closed is True
