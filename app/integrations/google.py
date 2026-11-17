import asyncio
from typing import Any

from google.auth.transport import requests as g_requests
from google.oauth2 import id_token


async def verify_google_token(token: str, client_id: str) -> dict[str, Any]:
    def _verify() -> dict[str, Any]:
        return id_token.verify_oauth2_token(token, g_requests.Request(), client_id)

    return await asyncio.to_thread(_verify)
