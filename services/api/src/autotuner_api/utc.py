from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class UTCResponse(BaseModel):
    @field_validator('*', mode='after')
    @classmethod
    def utc_dates(cls, value):
        return as_utc(value) if isinstance(value, datetime) else value
