from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    geo_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geo_stream_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_stream_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    offers: Mapped[list["CampaignOffer"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignOffer.position"
    )


class CampaignOffer(Base):
    __tablename__ = "campaign_offers"
    __table_args__ = (UniqueConstraint("campaign_id", "keitaro_offer_id", name="uq_campaign_offer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    keitaro_offer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    share: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="offers")
