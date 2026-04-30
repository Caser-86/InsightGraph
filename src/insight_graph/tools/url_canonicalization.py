from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid"}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = _canonical_port(parsed.scheme, parsed.port)
    netloc = hostname if port is None else f"{hostname}:{port}"
    query = urlencode(_canonical_query_pairs(parsed.query))
    return urlunparse((scheme, netloc, parsed.path or "", "", query, ""))


def _canonical_port(scheme: str, port: int | None) -> int | None:
    if port is None:
        return None
    if scheme.lower() == "http" and port == 80:
        return None
    if scheme.lower() == "https" and port == 443:
        return None
    return port


def _canonical_query_pairs(query: str) -> list[tuple[str, str]]:
    pairs = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        lowered_key = key.lower()
        if lowered_key.startswith("utm_") or lowered_key in TRACKING_QUERY_KEYS:
            continue
        pairs.append((key, value))
    return sorted(pairs)
