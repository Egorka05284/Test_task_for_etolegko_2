from typing import Any

import httpx

from app.core.config import settings


class KeitaroError(RuntimeError):
    """Raised when Keitaro Admin API returns an error or cannot be reached."""


class KeitaroClient:
    def __init__(self) -> None:
        if not settings.keitaro_base_url or not settings.keitaro_api_key:
            raise KeitaroError("Не настроены KEITARO_BASE_URL и/или KEITARO_API_KEY в .env")

        self.base_url = settings.keitaro_base_url.rstrip("/") + "/admin_api/v1"
        self.headers = {"Api-Key": settings.keitaro_api_key, "Accept": "application/json"}
        self.timeout = settings.request_timeout_seconds

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self.headers,
                    params=params,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise KeitaroError("Keitaro не ответил вовремя") from exc
        except httpx.HTTPError as exc:
            raise KeitaroError(f"Не удалось подключиться к Keitaro: {exc}") from exc

        if response.is_error:
            detail = response.text[:1500]
            raise KeitaroError(f"Keitaro API вернул HTTP {response.status_code}: {detail}")

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def list_domains(self) -> list[dict[str, Any]]:
        return await self.request("GET", "/domains")

    async def list_campaign_groups(self) -> list[dict[str, Any]]:
        return await self.request("GET", "/groups", params={"type": "campaigns"})

    async def list_traffic_sources(self) -> list[dict[str, Any]]:
        return await self.request("GET", "/traffic_sources")

    async def list_offers(self) -> list[dict[str, Any]]:
        return await self.request("GET", "/offers")

    async def list_campaigns(self, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self.request("GET", "/campaigns", params={"offset": offset, "limit": limit})

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        return await self.request("GET", f"/campaigns/{campaign_id}")

    async def get_campaign_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        return await self.request("GET", f"/campaigns/{campaign_id}/streams")

    async def get_stream(self, stream_id: int) -> dict[str, Any]:
        return await self.request("GET", f"/streams/{stream_id}")

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/campaigns", json=payload)

    async def update_campaign(self, campaign_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", f"/campaigns/{campaign_id}", json=payload)

    async def delete_campaign(self, campaign_id: int) -> Any:
        return await self.request("DELETE", f"/campaigns/{campaign_id}")

    async def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/streams", json=payload)

    async def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", f"/streams/{stream_id}", json=payload)

    async def delete_stream(self, stream_id: int) -> Any:
        return await self.request("DELETE", f"/streams/{stream_id}")
