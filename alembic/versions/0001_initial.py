"""Initial campaign and campaign-offer tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geo_code", sa.String(length=2), nullable=True),
        sa.Column("keitaro_campaign_id", sa.Integer(), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("traffic_source_id", sa.Integer(), nullable=True),
        sa.Column("geo_stream_id", sa.Integer(), nullable=True),
        sa.Column("offer_stream_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keitaro_campaign_id"),
    )
    op.create_index("ix_campaigns_keitaro_campaign_id", "campaigns", ["keitaro_campaign_id"], unique=True)
    op.create_table(
        "campaign_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("keitaro_offer_id", sa.Integer(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "keitaro_offer_id", name="uq_campaign_offer"),
    )
    op.create_index("ix_campaign_offers_campaign_id", "campaign_offers", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_campaign_offers_campaign_id", table_name="campaign_offers")
    op.drop_table("campaign_offers")
    op.drop_index("ix_campaigns_keitaro_campaign_id", table_name="campaigns")
    op.drop_table("campaigns")
