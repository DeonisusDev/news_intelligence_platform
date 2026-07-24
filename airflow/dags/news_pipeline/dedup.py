"""Canonical dedup/idempotency key, reused unchanged across every layer of the pipeline.

See docs/adr/0004-dedup-key-strategy.md for the reasoning.
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    if "@" in netloc:
        creds, host_port = netloc.rsplit("@", 1)
        netloc = f"{creds}@{host_port}"
    else:
        host_port = netloc

    if ":" in host_port:
        host, port = host_port.split(":", 1)
        default_port = {"http": "80", "https": "443"}.get(scheme)
        if port == default_port:
            netloc = netloc.rsplit(":", 1)[0]

    path = parts.path.rstrip("/") or "/"

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
        and not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
    ]
    kept_params.sort()
    query = urlencode(kept_params)

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
