"""API-Authentifizierung via statischem API-Key."""

import os

from fastapi import Header, HTTPException, status


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Prüft den übergebenen API-Key gegen DFlowP_API_Key."""
    expected_key = os.environ.get("DFlowP_API_Key")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serverkonfiguration unvollständig: DFlowP_API_Key fehlt.",
        )

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger API-Key.",
        )
