from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.campaign import Campaign

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="campaigns.html",
        context={"campaigns": campaigns},
    )


@router.get("/campaigns/{campaign_id}/edit", response_class=HTMLResponse)
def campaign_editor(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return templates.TemplateResponse(
        request=request,
        name="campaign_detail.html",
        context={"campaign": campaign},
    )
