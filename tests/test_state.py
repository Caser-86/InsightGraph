from insight_graph import __version__
from insight_graph.cli import app


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_app_is_importable() -> None:
    assert app.info.help == "InsightGraph research workflow CLI"
