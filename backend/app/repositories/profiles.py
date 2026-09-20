from uuid import UUID

import httpx

from app.core.config import Settings
from app.schemas.auth import Profile


class ProfileRepository:
    """Server-side profile lookup adapter for future Supabase-backed services."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_by_id(self, profile_id: UUID) -> Profile | None:
        if not self._settings.supabase_url or not self._settings.supabase_secret_key:
            raise RuntimeError("Supabase server configuration is not available.")

        headers = {
            "apikey": self._settings.supabase_secret_key,
            "Authorization": f"Bearer {self._settings.supabase_secret_key}",
        }
        params = {
            "id": f"eq.{profile_id}",
            "select": "id,full_name,email,phone,role,is_active",
            "limit": "1",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self._settings.supabase_rest_url}/profiles",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

        rows = response.json()
        return Profile.model_validate(rows[0]) if rows else None
