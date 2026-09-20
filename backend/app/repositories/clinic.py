from typing import Any
import httpx
from app.core.config import Settings

class ClinicRepository:
    """Server-only PostgREST adapter. Services own all authorization decisions."""
    def __init__(self, settings: Settings): self.settings = settings
    @property
    def headers(self):
        key = self.settings.supabase_secret_key
        return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}
    async def request(self, method: str, table: str, *, params: dict[str, str] | None=None, payload: Any=None) -> Any:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, f"{self.settings.supabase_rest_url}/{table}", headers=self.headers, params=params, json=payload)
        if response.is_error: raise httpx.HTTPStatusError("Database request failed", request=response.request, response=response)
        return response.json() if response.content else []
    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        return await self.request("POST", f"rpc/{name}", payload=payload)
