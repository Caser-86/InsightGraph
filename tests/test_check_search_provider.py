import json
import os
import subprocess
import sys
from pathlib import Path

import scripts.check_search_provider as check_search_provider


def test_import_does_not_load_env_file() -> None:
    repo_root = Path(__file__).parents[1]
    env = os.environ.copy()
    env.pop("INSIGHT_GRAPH_SEARCH_PROVIDER", None)
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import scripts.check_search_provider; "
                "print(os.environ.get('INSIGHT_GRAPH_SEARCH_PROVIDER', ''))"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
        check=True,
    )

    assert result.stdout.strip() == ""


def test_serpapi_check_closes_provider_response(monkeypatch) -> None:
    class FakeResponse:
        closed = False

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            self.closed = True

        def read(self) -> bytes:
            return json.dumps(
                {
                    "organic_results": [
                        {"link": "https://example.test/result"},
                    ]
                }
            ).encode("utf-8")

    response = FakeResponse()

    def fake_urlopen(url, timeout):
        return response

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("INSIGHT_GRAPH_SERPAPI_KEY", "serpapi-test")

    result = check_search_provider.check_serpapi("query", 1)

    assert result["status"] == "PASS"
    assert response.closed is True
