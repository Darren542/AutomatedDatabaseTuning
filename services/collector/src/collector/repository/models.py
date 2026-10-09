from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID
from collector.targets import TargetConfiguration

class CollectionBatchStatus(str, Enum):
    PENDING = "Pending"
    COLLECTING = "Collecting"
    COMPLETED = "Completed"
    PARTIAL = "Partial"
    FAILED = "Failed"
    CANCELLED = "Cancelled"

@dataclass(frozen=True)
class TargetRecord:
    target_id: UUID
    configuration: TargetConfiguration
    credential_reference: str | None
    is_enabled: bool
    created_at_utc: datetime
    updated_at_utc: datetime

@dataclass(frozen=True)
class CollectionBatchRecord:
    batch_id: UUID
    target_id: UUID
    label: str | None
    requested_window_start_utc: datetime | None
    requested_window_end_utc: datetime | None
    effective_window_start_utc: datetime | None
    effective_window_end_utc: datetime | None
    window_source: str | None
    force_metadata: bool
    collection_started_at_utc: datetime | None
    collection_completed_at_utc: datetime | None
    status: CollectionBatchStatus
    completeness_percent: float
    collector_version: str | None
    failure_reason: str | None
    created_at_utc: datetime
    updated_at_utc: datetime
