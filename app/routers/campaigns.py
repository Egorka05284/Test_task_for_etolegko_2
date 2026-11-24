from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.campaign import Campaign
from app.schemas.campaign import CampaignCreate, CampaignImport, OfferAdd
from app.services.campaign_service import CampaignService, CampaignServiceError
from app.services.keitaro_client import KeitaroClient, KeitaroError

router = APIRouter(prefix="/api", tags=["campaigns"])


def service(db: Session = Depends(get_db)) -> CampaignService:
    try:
        return CampaignService(db, KeitaroClient())
    except KeitaroError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/keitaro/options")
async def get_keitaro_options(svc: CampaignService = Depends(service)):
    try:
        return {
            **await svc.get_options(),
            "defaults": {
                "domain_id": settings.keitaro_default_domain_id,
                "group_id": settings.keitaro_default_group_id,
                "traffic_source_id": settings.keitaro_default_traffic_source_id,
            },
        }
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/keitaro/campaigns")
async def get_keitaro_campaigns(svc: CampaignService = Depends(service)):
    try:
        return await svc.keitaro.list_campaigns()
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "geo_code": c.geo_code,
            "keitaro_campaign_id": c.keitaro_campaign_id,
            "offer_stream_id": c.offer_stream_id,
        }
        for c in campaigns
    ]


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(data: CampaignCreate, svc: CampaignService = Depends(service)):
    try:
        campaign = await svc.create_campaign(data)
        return {
            "id": campaign.id,
            "name": campaign.name,
            "geo_code": campaign.geo_code,
            "keitaro_campaign_id": campaign.keitaro_campaign_id,
            "offer_stream_id": campaign.offer_stream_id,
        }
    except CampaignServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/campaigns/import", status_code=status.HTTP_201_CREATED)
async def import_campaign(data: CampaignImport, svc: CampaignService = Depends(service)):
    try:
        campaign = await svc.import_campaign(data.keitaro_campaign_id, data.offer_stream_id)
        return {
            "id": campaign.id,
            "name": campaign.name,
            "geo_code": campaign.geo_code,
            "keitaro_campaign_id": campaign.keitaro_campaign_id,
            "offer_stream_id": campaign.offer_stream_id,
        }
    except CampaignServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return {
        "id": campaign.id,
        "name": campaign.name,
        "geo_code": campaign.geo_code,
        "keitaro_campaign_id": campaign.keitaro_campaign_id,
        "offer_stream_id": campaign.offer_stream_id,
    }


@router.get("/campaigns/{campaign_id}/offers")
async def get_campaign_offers(
    campaign_id: int,
    db: Session = Depends(get_db),
    svc: CampaignService = Depends(service),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    try:
        offers = await svc.get_campaign_offers(campaign)
        return {
            "campaign_id": campaign.id,
            "keitaro_campaign_id": campaign.keitaro_campaign_id,
            "offer_stream_id": campaign.offer_stream_id,
            "offers": offers,
            "total_share": sum(item["share"] for item in offers),
        }
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/campaigns/{campaign_id}/offers", status_code=status.HTTP_200_OK)
async def add_campaign_offer(
    campaign_id: int,
    data: OfferAdd,
    db: Session = Depends(get_db),
    svc: CampaignService = Depends(service),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    try:
        await svc.add_offer(campaign, data.keitaro_offer_id)
        offers = await svc.get_campaign_offers(campaign)
        return {"offers": offers, "total_share": sum(item["share"] for item in offers)}
    except CampaignServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/campaigns/{campaign_id}/offers/{offer_id}")
async def remove_campaign_offer(
    campaign_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
    svc: CampaignService = Depends(service),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    try:
        await svc.remove_offer(campaign, offer_id)
        offers = await svc.get_campaign_offers(campaign)
        return {"offers": offers, "total_share": sum(item["share"] for item in offers)}
    except CampaignServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
