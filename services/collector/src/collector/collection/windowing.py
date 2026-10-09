from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

@dataclass(frozen=True)
class EffectiveCollectionWindow:
    start_utc: datetime
    end_utc: datetime
    source: str

def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def resolve_effective_window(
    *,
    requested_start_utc: datetime | None,
    requested_end_utc: datetime | None,
    previous_watermark_utc: datetime | None,
    now_utc: datetime,
    initial_lookback_minutes: int,
) -> EffectiveCollectionWindow:
    if (requested_start_utc is None) != (requested_end_utc is None):
        raise ValueError(
            "Requested collection start/end must both be supplied or omitted."
        )
    now = utc_naive(now_utc)

    if requested_start_utc is not None:
        start = utc_naive(requested_start_utc)
        end = utc_naive(requested_end_utc)
        if start > end:
            raise ValueError("Requested collection window start must be <= end.")
        return EffectiveCollectionWindow(start, end, "Explicit")

    if previous_watermark_utc is not None:
        start = utc_naive(previous_watermark_utc)
        if start > now:
            start = now
        return EffectiveCollectionWindow(start, now, "Incremental")

    return EffectiveCollectionWindow(
        now - timedelta(minutes=initial_lookback_minutes),
        now,
        "InitialLookback",
    )

def metadata_is_due(
    *,
    last_metadata_collected_at_utc: datetime | None,
    now_utc: datetime,
    refresh_minutes: int,
    force_metadata: bool,
) -> bool:
    if force_metadata or last_metadata_collected_at_utc is None:
        return True
    return (
        utc_naive(now_utc) - utc_naive(last_metadata_collected_at_utc)
        >= timedelta(minutes=refresh_minutes)
    )
