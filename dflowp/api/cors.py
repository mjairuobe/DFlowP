"""CORS für Browser-Frontends (SPA) auf dflowp.online.

Mit ``allow_credentials=True`` sendet der Browser ggf. Cookies/HTTP-Auth mit; die
DFlowP-API nutzt typisch den ``X-API-Key``-Header – dann wäre theoretisch
``allow_credentials=False`` denkbar. ``True`` hält Sitzungen/ Cookies möglich,
falls die gleiche Seite (oder ein Proxy) Sitzungscookies setzt, ohne
Header-basiertes CORS anzubrechen.
"""

from __future__ import annotations

from fastapi import FastAPI

# Regex für Starlette CORSMiddleware (fullmatch). Erlaubt:
# - http(s) (http für lokal, z. B. hinter dev-Port)
# - bel. Subdomain-Kette vor dflowp.online, inkl. Apex: „dflowp.online“
#   (Apex mit erlaubt, weil es dieselbe registrierte Domäne ist wie
#   app.*.dflowp.online – kein fremder Host.)
# - optional :PORT für lokale Tests
DFLOWP_CORS_ALLOW_ORIGIN_REGEX = (
    r"^https?://(?:(?:[a-z0-9-]+)\.)*dflowp\.online(?::\d+)?$",
    r"http://localhost:3000"
)


def add_cors_middleware(app: FastAPI) -> None:
    """Registriert ``CORSMiddleware`` an der FastAPI-App (vor Route-Handlern)."""
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=DFLOWP_CORS_ALLOW_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
