from __future__ import annotations
from datetime import datetime, timezone
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

_SELECT_COLUMNS = """
    BatchId,
    TargetId,
    Label,
    RequestedWindowStartUtc,
    RequestedWindowEndUtc,
    EffectiveWindowStartUtc,
    EffectiveWindowEndUtc,
    WindowSource,
    ForceMetadata,
    CollectionStartedAtUtc,
    CollectionCompletedAtUtc,
    Status,
    CompletenessPercent,
    CollectorVersion,
    FailureReason,
    CreatedAtUtc,
    UpdatedAtUtc
"""

def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

def _output_columns() -> str:
    return """
        inserted.BatchId,
        inserted.TargetId,
        inserted.Label,
        inserted.RequestedWindowStartUtc,
        inserted.RequestedWindowEndUtc,
        inserted.EffectiveWindowStartUtc,
        inserted.EffectiveWindowEndUtc,
        inserted.WindowSource,
        inserted.ForceMetadata,
        inserted.CollectionStartedAtUtc,
        inserted.CollectionCompletedAtUtc,
        inserted.Status,
        inserted.CompletenessPercent,
        inserted.CollectorVersion,
        inserted.FailureReason,
        inserted.CreatedAtUtc,
        inserted.UpdatedAtUtc
    """

def _record(row: object) -> CollectionBatchRecord:
    return CollectionBatchRecord(
        batch_id=UUID(str(row.BatchId)),
        target_id=UUID(str(row.TargetId)),
        label=row.Label,
        requested_window_start_utc=row.RequestedWindowStartUtc,
        requested_window_end_utc=row.RequestedWindowEndUtc,
        effective_window_start_utc=row.EffectiveWindowStartUtc,
        effective_window_end_utc=row.EffectiveWindowEndUtc,
        window_source=row.WindowSource,
        force_metadata=bool(row.ForceMetadata),
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
        force_metadata: bool = False,
    ) -> CollectionBatchRecord:
        start = _utc_naive(requested_window_start_utc)
        end = _utc_naive(requested_window_end_utc)

        if (start is None) != (end is None):
            raise ValueError(
                "Requested window start and end must either both be supplied or both be omitted."
            )
        if start is not None and end is not None and start > end:
            raise ValueError(
                "requested_window_start_utc must be <= requested_window_end_utc."
            )

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    f"""
                    INSERT INTO dbo.CollectionBatch
                    (
                        TargetId,
                        Label,
                        RequestedWindowStartUtc,
                        RequestedWindowEndUtc,
                        ForceMetadata,
                        Status,
                        CollectorVersion
                    )
                    OUTPUT {_output_columns()}
                    VALUES (?, ?, ?, ?, ?, N'Pending', ?);
                    """,
                    str(target_id),
                    label,
                    start,
                    end,
                    force_metadata,
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
                    f"""
                    SELECT {_SELECT_COLUMNS}
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
        status: CollectionBatchStatus | None = None,
        created_from_utc: datetime | None = None,
        created_to_utc: datetime | None = None,
        limit: int = 100,
    ) -> list[CollectionBatchRecord]:
        safe_limit = max(1, min(int(limit), 500))
        conditions: list[str] = []
        parameters: list[object] = []

        if target_id is not None:
            conditions.append("TargetId = ?")
            parameters.append(str(target_id))
        if status is not None:
            conditions.append("Status = ?")
            parameters.append(status.value)
        if created_from_utc is not None:
            conditions.append("CreatedAtUtc >= ?")
            parameters.append(_utc_naive(created_from_utc))
        if created_to_utc is not None:
            conditions.append("CreatedAtUtc <= ?")
            parameters.append(_utc_naive(created_to_utc))

        where_clause = (
            "WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                rows = cursor.execute(
                    f"""
                    SELECT TOP ({safe_limit})
                        {_SELECT_COLUMNS}
                    FROM dbo.CollectionBatch
                    {where_clause}
                    ORDER BY CreatedAtUtc DESC;
                    """,
                    *parameters,
                ).fetchall()
                return [_record(row) for row in rows]
            finally:
                cursor.close()

    def set_effective_window(
        self,
        batch_id: UUID,
        *,
        start_utc: datetime,
        end_utc: datetime,
        window_source: str,
    ) -> CollectionBatchRecord:
        start = _utc_naive(start_utc)
        end = _utc_naive(end_utc)

        if start is None or end is None:
            raise ValueError("Effective collection window cannot be null.")
        if start > end:
            raise ValueError("Effective collection window start must be <= end.")
        if window_source not in {"Explicit", "Incremental", "InitialLookback"}:
            raise ValueError("Invalid window source.")

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    f"""
                    UPDATE dbo.CollectionBatch
                    SET
                        EffectiveWindowStartUtc = ?,
                        EffectiveWindowEndUtc = ?,
                        WindowSource = ?,
                        UpdatedAtUtc = SYSUTCDATETIME()
                    OUTPUT {_output_columns()}
                    WHERE BatchId = ?;
                    """,
                    start,
                    end,
                    window_source,
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
                f"Invalid collection transition: {current.status.value} -> {new_status.value}."
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
            if new_status in {
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
                    OUTPUT {_output_columns()}
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
