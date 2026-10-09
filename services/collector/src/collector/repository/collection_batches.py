"""Persistence and state transitions for collection batches."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from collector.repository.connection import RepositorySettings, repository_connection
from collector.repository.models import CollectionBatchRecord, CollectionBatchStatus


class CollectionBatchNotFoundError(KeyError):
    pass


_ALLOWED_TRANSITIONS: dict[CollectionBatchStatus, set[CollectionBatchStatus]] = {
    CollectionBatchStatus.PENDING: {
        CollectionBatchStatus.COLLECTING,
        CollectionBatchStatus.FAILED,
        CollectionBatchStatus.CANCELLED,
    },
    CollectionBatchStatus.COLLECTING: {
        CollectionBatchStatus.COMPLETED,
        CollectionBatchStatus.PARTIAL,
        CollectionBatchStatus.FAILED,
        CollectionBatchStatus.CANCELLED,
    },
    CollectionBatchStatus.COMPLETED: set(),
    CollectionBatchStatus.PARTIAL: set(),
    CollectionBatchStatus.FAILED: set(),
    CollectionBatchStatus.CANCELLED: set(),
}


def _record(row: object) -> CollectionBatchRecord:
    return CollectionBatchRecord(
        batch_id=UUID(str(row.BatchId)),
        target_id=UUID(str(row.TargetId)),
        label=row.Label,
        requested_window_start_utc=row.RequestedWindowStartUtc,
        requested_window_end_utc=row.RequestedWindowEndUtc,
        collection_started_at_utc=row.CollectionStartedAtUtc,
        collection_completed_at_utc=row.CollectionCompletedAtUtc,
        status=CollectionBatchStatus(row.Status),
        completeness_percent=float(row.CompletenessPercent),
        collector_version=row.CollectorVersion,
        failure_reason=row.FailureReason,
        created_at_utc=row.CreatedAtUtc,
        updated_at_utc=row.UpdatedAtUtc,
    )


class SqlCollectionBatchRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def create(
        self,
        *,
        target_id: UUID,
        label: str | None,
        requested_window_start_utc: datetime | None,
        requested_window_end_utc: datetime | None,
        collector_version: str,
    ) -> CollectionBatchRecord:
        if (
            requested_window_start_utc is not None
            and requested_window_end_utc is not None
            and requested_window_start_utc > requested_window_end_utc
        ):
            raise ValueError(
                "requested_window_start_utc must be <= requested_window_end_utc."
            )

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    INSERT INTO dbo.CollectionBatch
                    (
                        TargetId,
                        Label,
                        RequestedWindowStartUtc,
                        RequestedWindowEndUtc,
                        Status,
                        CollectorVersion
                    )
                    OUTPUT
                        inserted.BatchId,
                        inserted.TargetId,
                        inserted.Label,
                        inserted.RequestedWindowStartUtc,
                        inserted.RequestedWindowEndUtc,
                        inserted.CollectionStartedAtUtc,
                        inserted.CollectionCompletedAtUtc,
                        inserted.Status,
                        inserted.CompletenessPercent,
                        inserted.CollectorVersion,
                        inserted.FailureReason,
                        inserted.CreatedAtUtc,
                        inserted.UpdatedAtUtc
                    VALUES (?, ?, ?, ?, N'Pending', ?);
                    """,
                    str(target_id),
                    label,
                    requested_window_start_utc,
                    requested_window_end_utc,
                    collector_version,
                ).fetchone()
                connection.commit()
                return _record(row)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def get(self, batch_id: UUID) -> CollectionBatchRecord | None:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        BatchId,
                        TargetId,
                        Label,
                        RequestedWindowStartUtc,
                        RequestedWindowEndUtc,
                        CollectionStartedAtUtc,
                        CollectionCompletedAtUtc,
                        Status,
                        CompletenessPercent,
                        CollectorVersion,
                        FailureReason,
                        CreatedAtUtc,
                        UpdatedAtUtc
                    FROM dbo.CollectionBatch
                    WHERE BatchId = ?;
                    """,
                    str(batch_id),
                ).fetchone()
                return _record(row) if row is not None else None
            finally:
                cursor.close()

    def list(
        self,
        *,
        target_id: UUID | None = None,
        limit: int = 100,
    ) -> list[CollectionBatchRecord]:
        safe_limit = max(1, min(int(limit), 500))
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                if target_id is None:
                    rows = cursor.execute(
                        f"""
                        SELECT TOP ({safe_limit})
                            BatchId,
                            TargetId,
                            Label,
                            RequestedWindowStartUtc,
                            RequestedWindowEndUtc,
                            CollectionStartedAtUtc,
                            CollectionCompletedAtUtc,
                            Status,
                            CompletenessPercent,
                            CollectorVersion,
                            FailureReason,
                            CreatedAtUtc,
                            UpdatedAtUtc
                        FROM dbo.CollectionBatch
                        ORDER BY CreatedAtUtc DESC;
                        """
                    ).fetchall()
                else:
                    rows = cursor.execute(
                        f"""
                        SELECT TOP ({safe_limit})
                            BatchId,
                            TargetId,
                            Label,
                            RequestedWindowStartUtc,
                            RequestedWindowEndUtc,
                            CollectionStartedAtUtc,
                            CollectionCompletedAtUtc,
                            Status,
                            CompletenessPercent,
                            CollectorVersion,
                            FailureReason,
                            CreatedAtUtc,
                            UpdatedAtUtc
                        FROM dbo.CollectionBatch
                        WHERE TargetId = ?
                        ORDER BY CreatedAtUtc DESC;
                        """,
                        str(target_id),
                    ).fetchall()

                return [_record(row) for row in rows]
            finally:
                cursor.close()

    def transition(
        self,
        batch_id: UUID,
        new_status: CollectionBatchStatus,
        *,
        completeness_percent: float | None = None,
        failure_reason: str | None = None,
    ) -> CollectionBatchRecord:
        current = self.get(batch_id)
        if current is None:
            raise CollectionBatchNotFoundError(str(batch_id))

        if new_status not in _ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(
                f"Invalid collection transition: "
                f"{current.status.value} -> {new_status.value}."
            )

        if completeness_percent is None:
            completeness_percent = (
                100.0
                if new_status == CollectionBatchStatus.COMPLETED
                else current.completeness_percent
            )

        if not 0 <= completeness_percent <= 100:
            raise ValueError("completeness_percent must be from 0 through 100.")

        started_expression = (
            "COALESCE(CollectionStartedAtUtc, SYSUTCDATETIME())"
            if new_status == CollectionBatchStatus.COLLECTING
            else "CollectionStartedAtUtc"
        )
        completed_expression = (
            "SYSUTCDATETIME()"
            if new_status
            in {
                CollectionBatchStatus.COMPLETED,
                CollectionBatchStatus.PARTIAL,
                CollectionBatchStatus.FAILED,
                CollectionBatchStatus.CANCELLED,
            }
            else "CollectionCompletedAtUtc"
        )

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    f"""
                    UPDATE dbo.CollectionBatch
                    SET
                        Status = ?,
                        CompletenessPercent = ?,
                        FailureReason = ?,
                        CollectionStartedAtUtc = {started_expression},
                        CollectionCompletedAtUtc = {completed_expression},
                        UpdatedAtUtc = SYSUTCDATETIME()
                    OUTPUT
                        inserted.BatchId,
                        inserted.TargetId,
                        inserted.Label,
                        inserted.RequestedWindowStartUtc,
                        inserted.RequestedWindowEndUtc,
                        inserted.CollectionStartedAtUtc,
                        inserted.CollectionCompletedAtUtc,
                        inserted.Status,
                        inserted.CompletenessPercent,
                        inserted.CollectorVersion,
                        inserted.FailureReason,
                        inserted.CreatedAtUtc,
                        inserted.UpdatedAtUtc
                    WHERE BatchId = ?;
                    """,
                    new_status.value,
                    completeness_percent,
                    failure_reason,
                    str(batch_id),
                ).fetchone()

                if row is None:
                    raise CollectionBatchNotFoundError(str(batch_id))

                connection.commit()
                return _record(row)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
