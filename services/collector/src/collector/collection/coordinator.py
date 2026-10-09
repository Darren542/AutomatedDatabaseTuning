"""WC-02 collection-batch orchestration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.models import CollectionBatchRecord, CollectionBatchStatus
from collector.repository.targets import SqlTargetRepository


class TargetUnavailableError(ValueError):
    pass


class CollectionCoordinator:
    def __init__(
        self,
        targets: SqlTargetRepository | None = None,
        batches: SqlCollectionBatchRepository | None = None,
        collector_version: str = "0.1.0",
    ):
        self._targets = targets or SqlTargetRepository()
        self._batches = batches or SqlCollectionBatchRepository()
        self._collector_version = collector_version

    def create_batch(
        self,
        *,
        target_id: UUID,
        label: str | None = None,
        requested_window_start_utc: datetime | None = None,
        requested_window_end_utc: datetime | None = None,
    ) -> CollectionBatchRecord:
        target = self._targets.get(target_id)
        if target is None:
            raise TargetUnavailableError("Target does not exist.")
        if not target.is_enabled:
            raise TargetUnavailableError("Target is disabled.")

        return self._batches.create(
            target_id=target_id,
            label=label,
            requested_window_start_utc=requested_window_start_utc,
            requested_window_end_utc=requested_window_end_utc,
            collector_version=self._collector_version,
        )

    def start(self, batch_id: UUID) -> CollectionBatchRecord:
        return self._batches.transition(
            batch_id,
            CollectionBatchStatus.COLLECTING,
        )

    def complete(self, batch_id: UUID) -> CollectionBatchRecord:
        return self._batches.transition(
            batch_id,
            CollectionBatchStatus.COMPLETED,
            completeness_percent=100.0,
        )

    def partial(
        self,
        batch_id: UUID,
        *,
        completeness_percent: float,
        reason: str | None = None,
    ) -> CollectionBatchRecord:
        return self._batches.transition(
            batch_id,
            CollectionBatchStatus.PARTIAL,
            completeness_percent=completeness_percent,
            failure_reason=reason,
        )

    def fail(
        self,
        batch_id: UUID,
        *,
        reason: str,
    ) -> CollectionBatchRecord:
        return self._batches.transition(
            batch_id,
            CollectionBatchStatus.FAILED,
            failure_reason=reason,
        )
