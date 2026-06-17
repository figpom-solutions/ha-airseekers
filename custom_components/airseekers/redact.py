"""Reusable redaction helper for the AIRSEEKERS integration.

Used by diagnostics and any safe-logging path. It masks:
- sensitive keys (credentials, tokens, serials, stream URLs, ...) — see ``const.SENSITIVE_KEYS``
- ``Authorization`` headers
- tokenised / signed URLs: user-info and sensitive query parameters are stripped

The goal is that **no secret, token, signed URL, or camera stream URL ever leaves the system** through
diagnostics or logs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .const import SENSITIVE_KEYS

REDACTED = "**REDACTED**"

# Query-string parameters that must be stripped from any URL we expose.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth",
        "authorization",
        "sig",
        "signature",
        "key",
        "apikey",
        "api_key",
        "password",
        "pwd",
        "secret",
        "x-amz-signature",
        "x-amz-credential",
        "se",
        "sig",
        "st",
    }
)


def _is_sensitive_key(key: str) -> bool:
    return key.lower() in SENSITIVE_KEYS


def redact_url(url: str) -> str:
    """Strip user-info and sensitive query parameters from a URL.

    Returns a placeholder if the input does not look like a URL we can safely partially keep.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return REDACTED
    if not parts.scheme:
        return url

    # Drop any embedded credentials (user:pass@host).
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username or parts.password:
        netloc = f"{REDACTED}@{netloc}"

    redacted_query = [
        (k, REDACTED if k.lower() in _SENSITIVE_QUERY_KEYS else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    query = urlencode(redacted_query)
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact a value. If ``key`` is sensitive, the whole value is masked."""
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {k: redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(redact_value(v) for v in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(v) for v in value]
    if isinstance(value, str) and "://" in value:
        return redact_url(value)
    return value


def redact_mapping(data: Mapping[str, Any], *, extra_keys: frozenset[str] | None = None) -> dict:
    """Redact a mapping for diagnostics. ``extra_keys`` adds one-off sensitive keys."""
    if extra_keys:
        result: dict[str, Any] = {}
        for k, v in data.items():
            if k.lower() in extra_keys:
                result[k] = REDACTED
            else:
                result[k] = redact_value(v, key=str(k))
        return result
    return {k: redact_value(v, key=str(k)) for k, v in data.items()}
