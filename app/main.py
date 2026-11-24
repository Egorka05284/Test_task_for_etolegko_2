from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import Base, engine
from app.models import Campaign, CampaignOffer  # noqa: F401 - register models with metadata
from app.routers.campaigns import router as campaigns_router
from app.routers.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages_router)
app.include_router(campaigns_router)


@app.get("/health")
def health():
    return {"status": "ok"}
