import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.campaign import Campaign
from app.schemas.campaign import CampaignCreate
from app.services.campaign_service import CampaignService, CampaignServiceError, equal_shares, make_alias


class FakeKeitaro:
    def __init__(self):
        self.calls = []
        self.next_stream_id = 200
        self.streams = {}
        self.campaigns = {}
        self.domains = [{"id": 1813, "name": "https://in.posdk.xyz/"}]
        self.groups = [{"id": 10332, "name": "FORTESTS"}]
        self.sources = [{"id": 836, "name": "FORTESTS"}]
        self.offers = [
            {"id": 18001, "name": "Offer 1"},
            {"id": 18002, "name": "Offer 2"},
            {"id": 18003, "name": "Offer 3"},
        ]

    async def list_domains(self):
        return self.domains

    async def list_campaign_groups(self):
        return self.groups

    async def list_traffic_sources(self):
        return self.sources

    async def list_offers(self):
        return self.offers

    async def create_campaign(self, payload):
        self.calls.append(("create_campaign", payload))
        campaign = {"id": 51, **payload}
        self.campaigns[51] = campaign
        return campaign

    async def update_campaign(self, campaign_id, payload):
        self.calls.append(("update_campaign", campaign_id, payload))
        self.campaigns[campaign_id].update(payload)
        return self.campaigns[campaign_id]

    async def delete_campaign(self, campaign_id):
        self.calls.append(("delete_campaign", campaign_id))
        self.campaigns.pop(campaign_id, None)

    async def create_stream(self, payload):
        self.calls.append(("create_stream", payload))
        stream = {"id": self.next_stream_id, **payload}
        self.streams[self.next_stream_id] = stream
        self.next_stream_id += 1
        return stream

    async def get_stream(self, stream_id):
        return self.streams[stream_id]

    async def update_stream(self, stream_id, payload):
        self.calls.append(("update_stream", stream_id, payload))
        self.streams[stream_id].update(payload)
        return self.streams[stream_id]

    async def get_campaign(self, campaign_id):
        return self.campaigns[campaign_id]

    async def get_campaign_streams(self, campaign_id):
        return [s for s in self.streams.values() if s["campaign_id"] == campaign_id]


def make_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_equal_shares_sum_to_100():
    assert equal_shares(1) == [100]
    assert equal_shares(2) == [50, 50]
    assert equal_shares(3) == [34, 33, 33]
    assert equal_shares(4) == [25, 25, 25, 25]
    assert sum(equal_shares(7)) == 100


def test_equal_shares_rejects_empty_campaign():
    with pytest.raises(ValueError):
        equal_shares(0)


def test_make_alias_is_url_safe_and_not_empty():
    alias = make_alias("Campaign 2 / Australia")
    assert alias
    assert alias == alias.lower()
    assert all(char.isalnum() or char == "-" for char in alias)


def test_create_campaign_uses_stand_payloads_and_assigns_domain():
    async def scenario():
        db = make_db()
        fake = FakeKeitaro()
        service = CampaignService(db, fake)
        data = CampaignCreate(
            name="Campaign Australia",
            geo_code="au",
            keitaro_offer_id=18001,
            domain_id=1813,
            group_id=10332,
            traffic_source_id=836,
        )

        campaign = await service.create_campaign(data)

        assert campaign.keitaro_campaign_id == 51
        assert campaign.domain_id == 1813
        assert campaign.geo_code == "AU"
        create_call = next(call for call in fake.calls if call[0] == "create_campaign")
        assert create_call[1]["name"] == "Campaign Australia"
        assert create_call[1]["group_id"] == "10332"
        assert create_call[1]["traffic_source_id"] == 836
        assert "domain_id" not in create_call[1]

        update_call = next(call for call in fake.calls if call[0] == "update_campaign")
        assert update_call[2] == {"domain_id": 1813}

        stream_calls = [call[1] for call in fake.calls if call[0] == "create_stream"]
        assert len(stream_calls) == 2
        geo, offer = stream_calls
        assert geo["type"] == "regular"
        assert geo["schema"] == "redirect"
        assert geo["action_type"] == "http"
        assert geo["action_payload"] == "https://google.com"
        assert geo["filters"] == [
            {"name": "country", "mode": "accept", "payload": ["AU"]}
        ]
        assert offer["type"] == "default"
        assert offer["schema"] == "landings"
        assert offer["offers"] == [
            {"offer_id": 18001, "share": 100, "state": "active"}
        ]
        assert "action_type" not in offer
        db.close()

    asyncio.run(scenario())


def test_add_and_remove_offer_replace_full_remote_offers_array():
    async def scenario():
        db = make_db()
        fake = FakeKeitaro()
        fake.streams[301] = {
            "id": 301,
            "campaign_id": 51,
            "offers": [{"offer_id": 18001, "share": 100, "state": "paused"}],
        }
        campaign = Campaign(
            name="Imported",
            geo_code=None,
            keitaro_campaign_id=51,
            offer_stream_id=301,
        )
        campaign.offers = []
        db.add(campaign)
        db.commit()
        service = CampaignService(db, fake)

        await service.add_offer(campaign, 18002)
        assert fake.streams[301]["offers"] == [
            {"offer_id": 18001, "share": 50, "state": "paused"},
            {"offer_id": 18002, "share": 50, "state": "active"},
        ]

        update_call = [call for call in fake.calls if call[0] == "update_stream"][-1]
        assert set(update_call[2]) == {"offers"}
        assert len(update_call[2]["offers"]) == 2

        await service.remove_offer(campaign, 18001)
        assert fake.streams[301]["offers"] == [
            {"offer_id": 18002, "share": 100, "state": "active"}
        ]
        db.close()

    asyncio.run(scenario())


def test_cannot_remove_last_offer():
    async def scenario():
        db = make_db()
        fake = FakeKeitaro()
        fake.streams[301] = {
            "id": 301,
            "campaign_id": 51,
            "offers": [{"offer_id": 18001, "share": 100, "state": "active"}],
        }
        campaign = Campaign(
            name="Imported",
            geo_code=None,
            keitaro_campaign_id=51,
            offer_stream_id=301,
        )
        db.add(campaign)
        db.commit()
        service = CampaignService(db, fake)

        with pytest.raises(CampaignServiceError, match="последний оффер"):
            await service.remove_offer(campaign, 18001)
        db.close()

    asyncio.run(scenario())


class FailingOfferStreamKeitaro(FakeKeitaro):
    async def create_stream(self, payload):
        if payload.get("name") == "Офферы":
            raise RuntimeError("simulated offer-stream failure")
        return await super().create_stream(payload)


def test_create_campaign_deletes_remote_campaign_if_stream_creation_fails():
    async def scenario():
        db = make_db()
        fake = FailingOfferStreamKeitaro()
        service = CampaignService(db, fake)
        data = CampaignCreate(
            name="Campaign Australia",
            geo_code="AU",
            keitaro_offer_id=18001,
            domain_id=1813,
            group_id=10332,
            traffic_source_id=836,
        )

        with pytest.raises(CampaignServiceError, match="ID кампании: 51"):
            await service.create_campaign(data)

        assert 51 not in fake.campaigns
        assert any(call[0] == "delete_campaign" for call in fake.calls)
        assert db.query(Campaign).count() == 0
        db.close()

    asyncio.run(scenario())


def test_import_campaign_detects_offer_stream_automatically():
    async def scenario():
        db = make_db()
        fake = FakeKeitaro()
        fake.campaigns[77] = {
            "id": 77,
            "name": "Existing campaign",
            "domain_id": 1813,
            "group_id": 10332,
            "traffic_source_id": 836,
        }
        fake.streams[401] = {
            "id": 401,
            "campaign_id": 77,
            "name": "Geo redirect",
            "filters": [{"name": "country", "mode": "accept", "payload": ["RU"]}],
        }
        fake.streams[402] = {
            "id": 402,
            "campaign_id": 77,
            "name": "Offers",
            "offers": [
                {"offer_id": 18001, "share": 60, "state": "active"},
                {"offer_id": 18002, "share": 40, "state": "active"},
            ],
        }

        campaign = await CampaignService(db, fake).import_campaign(77)

        assert campaign.keitaro_campaign_id == 77
        assert campaign.name == "Existing campaign"
        assert campaign.offer_stream_id == 402
        assert [item.keitaro_offer_id for item in campaign.offers] == [18001, 18002]
        db.close()

    asyncio.run(scenario())


def test_import_rejects_stream_belonging_to_another_campaign():
    class InconsistentStreamListingKeitaro(FakeKeitaro):
        async def get_campaign_streams(self, campaign_id):
            # Simulate a stale or inconsistent stream listing from the API:
            # the summary says the stream is in this campaign, but its detail
            # response identifies a different campaign.
            if campaign_id == 77:
                return [{"id": 402}]
            return []

    async def scenario():
        db = make_db()
        fake = InconsistentStreamListingKeitaro()
        fake.campaigns[77] = {"id": 77, "name": "Existing campaign"}
        fake.streams[402] = {
            "id": 402,
            "campaign_id": 78,
            "offers": [{"offer_id": 18001, "share": 100, "state": "active"}],
        }

        with pytest.raises(CampaignServiceError, match="принадлежит другой кампании"):
            await CampaignService(db, fake).import_campaign(77, 402)
        db.close()

    asyncio.run(scenario())


def test_geo_code_must_use_two_ascii_letters():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CampaignCreate(
            name="Invalid GEO",
            geo_code="РУ",
            keitaro_offer_id=18001,
            domain_id=1813,
            group_id=10332,
            traffic_source_id=836,
        )
