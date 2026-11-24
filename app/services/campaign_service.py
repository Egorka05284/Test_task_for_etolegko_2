import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign, CampaignOffer
from app.schemas.campaign import CampaignCreate
from app.services.keitaro_client import KeitaroClient


class CampaignServiceError(RuntimeError):
    pass


def make_alias(name: str) -> str:
    """Build a URL-safe, unique campaign alias."""
    normalized = name.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        normalized = "campaign"
    return f"{normalized[:35]}-{secrets.token_hex(3)}"


def equal_shares(count: int) -> list[int]:
    """Split 100% into integer shares; remainder is distributed from first item."""
    if count < 1:
        raise ValueError("Должен остаться хотя бы один оффер")
    base, remainder = divmod(100, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


class CampaignService:
    def __init__(self, db: Session, keitaro: KeitaroClient) -> None:
        self.db = db
        self.keitaro = keitaro

    async def create_campaign(self, data: CampaignCreate) -> Campaign:
        """Create a Keitaro campaign and its two required streams."""
        options = await self.get_options()
        self._require_entity(options["domains"], data.domain_id, "домен")
        self._require_entity(options["groups"], data.group_id, "группу")
        self._require_entity(options["traffic_sources"], data.traffic_source_id, "источник")
        self._require_entity(options["offers"], data.keitaro_offer_id, "оффер")

        # The public Admin API schema requires alias and name. The test stand
        # can generate an alias, but sending one explicitly is compatible with it.
        remote_campaign = await self.keitaro.create_campaign(
            {
                "alias": make_alias(data.name),
                "name": data.name,
                "type": "position",
                "group_id": str(data.group_id),
                "traffic_source_id": data.traffic_source_id,
            }
        )
        try:
            keitaro_campaign_id = int(remote_campaign["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CampaignServiceError(
                f"Keitaro создал кампанию, но не вернул корректный ID: {remote_campaign!r}"
            ) from exc

        try:
            # In the public schema domain_id is available on campaign update;
            # keep it separate from POST /campaigns for compatibility.
            await self.keitaro.update_campaign(
                keitaro_campaign_id,
                {"domain_id": data.domain_id},
            )

            # Flow 1: only the selected country is accepted and redirected to Google.
            geo_flow = await self.keitaro.create_stream(
                {
                    "campaign_id": keitaro_campaign_id,
                    "name": "Geo redirect",
                    "type": "regular",
                    "schema": "redirect",
                    "action_type": "http",
                    "action_payload": settings.google_redirect_url,
                    "filters": [
                        {"name": "country", "mode": "accept", "payload": [data.geo_code]}
                    ],
                }
            )

            # Flow 2 is a default flow and therefore receives traffic not
            # matched by the GEO-filtered regular flow.
            offer_flow = await self.keitaro.create_stream(
                {
                    "campaign_id": keitaro_campaign_id,
                    "name": "Офферы",
                    "type": "default",
                    "schema": "landings",
                    "offers": [
                        {"offer_id": data.keitaro_offer_id, "share": 100, "state": "active"}
                    ],
                }
            )
        except Exception as exc:
            # The stand deletes a campaign together with its streams. This is
            # safer than leaving a partially configured campaign behind.
            try:
                await self.keitaro.delete_campaign(keitaro_campaign_id)
            except Exception:
                pass
            raise CampaignServiceError(
                "Не удалось полностью настроить кампанию в Keitaro. "
                f"Проверьте журнал стенда. ID кампании: {keitaro_campaign_id}. Причина: {exc}"
            ) from exc

        try:
            geo_stream_id = int(geo_flow["id"])
            offer_stream_id = int(offer_flow["id"])
        except (KeyError, TypeError, ValueError) as exc:
            try:
                await self.keitaro.delete_campaign(keitaro_campaign_id)
            except Exception:
                pass
            raise CampaignServiceError(
                "Keitaro создал потоки, но не вернул корректные ID. "
                f"ID кампании: {keitaro_campaign_id}"
            ) from exc

        campaign = Campaign(
            name=data.name,
            geo_code=data.geo_code,
            keitaro_campaign_id=keitaro_campaign_id,
            domain_id=data.domain_id,
            group_id=data.group_id,
            traffic_source_id=data.traffic_source_id,
            geo_stream_id=geo_stream_id,
            offer_stream_id=offer_stream_id,
        )
        campaign.offers.append(
            CampaignOffer(keitaro_offer_id=data.keitaro_offer_id, share=100, position=1)
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    async def get_options(self) -> dict[str, list[dict[str, Any]]]:
        """Return the read-only catalogs needed by the campaign forms."""
        domains = await self.keitaro.list_domains()
        groups = await self.keitaro.list_campaign_groups()
        sources = await self.keitaro.list_traffic_sources()
        offers = await self.keitaro.list_offers()
        return {
            "domains": domains,
            "groups": groups,
            "traffic_sources": sources,
            "offers": offers,
        }

    @staticmethod
    def _require_entity(items: list[dict[str, Any]], entity_id: int, label: str) -> None:
        if not any(int(item.get("id", -1)) == entity_id for item in items):
            raise CampaignServiceError(f"В Keitaro не найден {label} с ID {entity_id}")

    async def _get_remote_offer_rows(self, campaign: Campaign) -> list[dict[str, Any]]:
        stream = await self.keitaro.get_stream(campaign.offer_stream_id)
        offers = stream.get("offers") or []
        rows: list[dict[str, Any]] = []
        for item in offers:
            offer_id = item.get("offer_id", item.get("id"))
            if offer_id is None:
                continue
            rows.append(
                {
                    "keitaro_offer_id": int(offer_id),
                    "share": int(item.get("share", 0)),
                    "state": item.get("state", "active"),
                }
            )
        return rows

    async def get_campaign_offers(self, campaign: Campaign) -> list[dict[str, Any]]:
        remote_rows = await self._get_remote_offer_rows(campaign)
        remote_offers = await self.keitaro.list_offers()
        names = {
            int(item["id"]): str(item.get("name", f"Offer {item['id']}"))
            for item in remote_offers
        }
        return [
            {
                "keitaro_offer_id": item["keitaro_offer_id"],
                "name": names.get(item["keitaro_offer_id"], f"Offer {item['keitaro_offer_id']}"),
                "share": item["share"],
                "position": index,
                "state": item["state"],
            }
            for index, item in enumerate(remote_rows, start=1)
        ]

    async def add_offer(self, campaign: Campaign, offer_id: int) -> list[CampaignOffer]:
        current_rows = await self._get_remote_offer_rows(campaign)
        current_ids = [item["keitaro_offer_id"] for item in current_rows]
        if offer_id in current_ids:
            raise CampaignServiceError("Этот оффер уже добавлен в кампанию")

        available = await self.keitaro.list_offers()
        self._require_entity(available, offer_id, "оффер")

        offer_ids = current_ids + [offer_id]
        shares = equal_shares(len(offer_ids))
        states = {item["keitaro_offer_id"]: item["state"] for item in current_rows}
        states[offer_id] = "active"
        await self._sync_remote_offers(campaign, offer_ids, shares, states)
        return self._store_local_offers(campaign, offer_ids, shares)

    async def remove_offer(self, campaign: Campaign, offer_id: int) -> list[CampaignOffer]:
        current_rows = await self._get_remote_offer_rows(campaign)
        current_ids = [item["keitaro_offer_id"] for item in current_rows]
        offer_ids = [current_id for current_id in current_ids if current_id != offer_id]
        if len(offer_ids) == len(current_ids):
            raise CampaignServiceError("Оффер не найден в этой кампании")
        if not offer_ids:
            raise CampaignServiceError("Нельзя удалить последний оффер из потока")

        shares = equal_shares(len(offer_ids))
        states = {
            item["keitaro_offer_id"]: item["state"]
            for item in current_rows
            if item["keitaro_offer_id"] in offer_ids
        }
        await self._sync_remote_offers(campaign, offer_ids, shares, states)
        return self._store_local_offers(campaign, offer_ids, shares)

    def _store_local_offers(
        self, campaign: Campaign, offer_ids: list[int], shares: list[int]
    ) -> list[CampaignOffer]:
        campaign.offers.clear()
        self.db.flush()
        updated = [
            CampaignOffer(keitaro_offer_id=offer_id, share=share, position=index)
            for index, (offer_id, share) in enumerate(zip(offer_ids, shares), start=1)
        ]
        campaign.offers.extend(updated)
        self.db.commit()
        self.db.refresh(campaign)
        return updated

    async def _sync_remote_offers(
        self,
        campaign: Campaign,
        offer_ids: list[int],
        shares: list[int],
        states: dict[int, str] | None = None,
    ) -> None:
        # PUT /streams/{id} replaces the complete offers array. Always send
        # the full new list; do not send a one-item patch.
        await self.keitaro.update_stream(
            campaign.offer_stream_id,
            {
                "offers": [
                    {
                        "offer_id": offer_id,
                        "share": share,
                        "state": (states or {}).get(offer_id, "active"),
                    }
                    for offer_id, share in zip(offer_ids, shares)
                ]
            },
        )

    async def import_campaign(
        self, keitaro_campaign_id: int, offer_stream_id: int | None = None
    ) -> Campaign:
        existing = self.db.scalar(
            select(Campaign).where(Campaign.keitaro_campaign_id == keitaro_campaign_id)
        )
        if existing:
            return existing

        remote_campaign = await self.keitaro.get_campaign(keitaro_campaign_id)
        stream_summaries = await self.keitaro.get_campaign_streams(keitaro_campaign_id)

        if offer_stream_id is not None:
            summary = next(
                (row for row in stream_summaries if int(row.get("id", -1)) == offer_stream_id),
                None,
            )
            if summary is None:
                raise CampaignServiceError(
                    f"В кампании {keitaro_campaign_id} нет потока с ID {offer_stream_id}"
                )
            candidate = await self.keitaro.get_stream(offer_stream_id)
        else:
            streams = []
            for summary in stream_summaries:
                stream_id = int(summary["id"])
                streams.append(await self.keitaro.get_stream(stream_id))
            with_offers = [stream for stream in streams if stream.get("offers")]
            if not with_offers:
                raise CampaignServiceError(
                    "Не найден поток с офферами. Укажите ID нужного потока вручную."
                )
            candidate = max(with_offers, key=lambda stream: len(stream.get("offers", [])))

        if int(candidate.get("campaign_id", keitaro_campaign_id)) != keitaro_campaign_id:
            raise CampaignServiceError("Выбранный поток принадлежит другой кампании")
        remote_rows = candidate.get("offers") or []
        if not remote_rows:
            raise CampaignServiceError("У выбранного потока пока нет офферов")

        campaign = Campaign(
            name=str(remote_campaign.get("name") or f"Campaign {keitaro_campaign_id}"),
            geo_code=None,
            keitaro_campaign_id=keitaro_campaign_id,
            domain_id=remote_campaign.get("domain_id"),
            group_id=remote_campaign.get("group_id"),
            traffic_source_id=remote_campaign.get("traffic_source_id"),
            geo_stream_id=None,
            offer_stream_id=int(candidate["id"]),
        )
        for index, item in enumerate(remote_rows, start=1):
            offer_id = item.get("offer_id", item.get("id"))
            if offer_id is None:
                continue
            campaign.offers.append(
                CampaignOffer(
                    keitaro_offer_id=int(offer_id),
                    share=int(item.get("share", 0)),
                    position=index,
                )
            )
        if not campaign.offers:
            raise CampaignServiceError("Keitaro не вернул корректные ID офферов")

        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign
