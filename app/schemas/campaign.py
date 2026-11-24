from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo_code: str = Field(min_length=2, max_length=2, examples=["AU"])
    keitaro_offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название кампании не может быть пустым")
        return value

    @field_validator("geo_code")
    @classmethod
    def normalize_geo(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("GEO должен быть двухбуквенным кодом страны латиницей, например AU")
        return value


class OfferAdd(BaseModel):
    keitaro_offer_id: int = Field(gt=0)


class CampaignImport(BaseModel):
    keitaro_campaign_id: int = Field(gt=0)
    offer_stream_id: int | None = Field(default=None, gt=0)


class OfferItem(BaseModel):
    keitaro_offer_id: int
    name: str
    share: int
    position: int


class CampaignSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    geo_code: str | None
    keitaro_campaign_id: int
    offer_stream_id: int


class CampaignOfferList(BaseModel):
    campaign_id: int
    keitaro_campaign_id: int
    offer_stream_id: int
    offers: list[OfferItem]
    total_share: int


class Message(BaseModel):
    message: str
