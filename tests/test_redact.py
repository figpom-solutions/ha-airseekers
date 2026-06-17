"""Tests for the reusable redaction helper."""

from __future__ import annotations

from custom_components.airseekers.redact import REDACTED, redact_mapping, redact_url, redact_value


def test_redact_url_strips_userinfo_and_sensitive_query() -> None:
    url = "https://user:pass@cam.example.com:8443/live?token=abc123&view=front"
    out = redact_url(url)
    assert "user:pass" not in out
    assert "abc123" not in out
    assert REDACTED in out
    assert "view=front" in out  # non-sensitive query preserved
    assert "cam.example.com" in out


def test_redact_url_passthrough_for_non_url() -> None:
    assert redact_url("front") == "front"


def test_redact_value_masks_sensitive_keys() -> None:
    assert redact_value("hunter2", key="password") == REDACTED
    assert redact_value("hunter2", key="state") == "hunter2"


def test_redact_value_redacts_urls_in_values() -> None:
    out = redact_value("rtsp://a:b@host/stream?sig=xyz")
    assert "a:b" not in out
    assert "xyz" not in out


def test_redact_mapping_nested_and_extra_keys() -> None:
    data = {
        "state": "mowing",
        "password": "secret",
        "nested": {"token": "tok", "battery": 80},
        "stream_url": "https://host/s?token=zzz",
        "custom": "keep-unless-extra",
    }
    out = redact_mapping(data, extra_keys=frozenset({"custom"}))
    assert out["state"] == "mowing"
    assert out["password"] == REDACTED
    assert out["nested"]["token"] == REDACTED
    assert out["nested"]["battery"] == 80
    assert out["stream_url"] == REDACTED  # sensitive key name
    assert out["custom"] == REDACTED  # via extra_keys
