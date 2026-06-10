import pytest

from insight_graph.tools.http_client import FetchError
from insight_graph.tools.rendered_fetch import render_page


def test_render_page_rejects_localhost_before_browser_launch() -> None:
    with pytest.raises(FetchError, match="not allowed"):
        render_page("http://localhost/admin")
