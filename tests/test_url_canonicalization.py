from insight_graph.tools.url_canonicalization import canonicalize_url


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    url = (
        "HTTPS://Example.COM:443/path/?utm_source=newsletter&b=2&"
        "fbclid=abc&a=1#section"
    )

    assert canonicalize_url(url) == "https://example.com/path/?a=1&b=2"


def test_canonicalize_url_preserves_meaningful_sorted_query() -> None:
    url = "http://Example.com:80/search?z=last&q=ai+agents&a=first"

    assert canonicalize_url(url) == "http://example.com/search?a=first&q=ai+agents&z=last"
