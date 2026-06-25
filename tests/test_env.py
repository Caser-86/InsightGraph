import os

from insight_graph.env import load_local_dotenv


def test_load_local_dotenv_skips_when_pytest_is_loaded(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("INSIGHT_GRAPH_TEST_ENV=loaded\n", encoding="utf-8")

    assert load_local_dotenv(skip_when_pytest_loaded=True, env_path=env_file) is False


def test_load_local_dotenv_skips_during_current_pytest_test(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("INSIGHT_GRAPH_TEST_ENV=loaded\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_env.py::test")

    assert load_local_dotenv(env_path=env_file) is False


def test_load_local_dotenv_reads_explicit_path(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("INSIGHT_GRAPH_TEST_ENV=loaded\n", encoding="utf-8")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_TEST_ENV", raising=False)

    assert load_local_dotenv(
        skip_when_pytest_loaded=False,
        skip_when_pytest_current_test=False,
        env_path=env_file,
    )
    assert os.environ["INSIGHT_GRAPH_TEST_ENV"] == "loaded"
