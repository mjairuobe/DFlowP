"""CORS-Origin-Regex (dflowp.online) — gleiche Semantik wie Starlette (fullmatch)."""

import re

import pytest

from dflowp.api.cors import DFLOWP_CORS_ALLOW_ORIGIN_REGEX

_rx = re.compile(DFLOWP_CORS_ALLOW_ORIGIN_REGEX)


@pytest.mark.parametrize(
    "origin",
    [
        "https://x.dflowp.online",
        "https://dflowp.online",
        "https://foo-bar.baz.dflowp.online",
        "https://dflowp.online:8443",
        "http://app.dflowp.online:3000",
    ],
)
def test_cors_regex_allows_dflowp_online_variants(origin: str) -> None:
    assert _rx.fullmatch(origin) is not None, origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.com",
        "https://dflowp-online.evil.com",
        "https://notdflowp.online",
    ],
)
def test_cors_regex_rejects_unrelated_origins(origin: str) -> None:
    assert _rx.fullmatch(origin) is None, origin
