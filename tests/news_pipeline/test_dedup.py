"""normalize_url/url_hash are the single dedup/idempotency key for the whole pipeline (see
docs/adr/0004-dedup-key-strategy.md) - every case here maps directly to a rule documented there.
"""

from news_pipeline.dedup import normalize_url, url_hash


def test_lowercases_host_but_not_path():
    assert normalize_url("https://EXAMPLE.com/Some/Path") == "https://example.com/Some/Path"


def test_strips_default_https_port():
    assert normalize_url("https://example.com:443/a") == "https://example.com/a"


def test_strips_default_http_port():
    assert normalize_url("http://example.com:80/a") == "http://example.com/a"


def test_keeps_non_default_port():
    assert normalize_url("https://example.com:8443/a") == "https://example.com:8443/a"


def test_strips_trailing_slash():
    assert normalize_url("https://example.com/a/") == "https://example.com/a"


def test_bare_domain_normalizes_to_root_slash():
    assert normalize_url("https://example.com") == "https://example.com/"


def test_strips_utm_and_known_tracking_params():
    url = "https://example.com/a?utm_source=x&utm_medium=y&fbclid=z&gclid=w"
    assert normalize_url(url) == "https://example.com/a"


def test_keeps_and_sorts_non_tracking_params():
    assert normalize_url("https://example.com/a?b=2&a=1") == "https://example.com/a?a=1&b=2"


def test_mixed_tracking_and_real_params_keeps_only_real_ones_sorted():
    url = "https://example.com/a?utm_source=x&z=1&a=2"
    assert normalize_url(url) == "https://example.com/a?a=2&z=1"


def test_preserves_userinfo_in_netloc():
    assert normalize_url("https://user:pass@example.com/a") == "https://user:pass@example.com/a"


def test_strips_leading_trailing_whitespace():
    assert normalize_url("  https://example.com/a  ") == normalize_url("https://example.com/a")


def test_url_hash_is_deterministic():
    assert url_hash("https://example.com/a") == url_hash("https://example.com/a")


def test_url_hash_is_sha256_hex():
    digest = url_hash("https://example.com/a")
    assert len(digest) == 64
    int(digest, 16)  # raises ValueError if not valid hex


def test_url_hash_matches_after_tracking_param_normalization():
    a = url_hash("https://example.com/a?utm_source=newsletter")
    b = url_hash("https://example.com/a")
    assert a == b


def test_url_hash_differs_for_different_paths():
    assert url_hash("https://example.com/a") != url_hash("https://example.com/b")
