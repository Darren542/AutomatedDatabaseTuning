from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from collector.repository.connection import RepositorySettings, repository_connection

@dataclass(frozen=True)
class TargetCollectionState:
    target_id: UUID
    last_query_runtime_watermark_utc: datetime | None
    last_successful_query_batch_id: UUID | None
    last_metadata_collected_at_utc: datetime | None
    last_metadata_batch_id: UUID | None
    updated_at_utc: datetime

def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

class SqlTargetCollectionStateRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def get(self, target_id: UUID) -> TargetCollectionState | None:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        TargetId,
                        LastQueryRuntimeWatermarkUtc,
                        LastSuccessfulQueryBatchId,
                        LastMetadataCollectedAtUtc,
                        LastMetadataBatchId,
                        UpdatedAtUtc
                    FROM dbo.TargetCollectionState
                    WHERE TargetId = ?;
                    """,
                    str(target_id),
                ).fetchone()
                if row is None:
                    return None
                return TargetCollectionState(
                    target_id=UUID(str(row.TargetId)),
                    last_query_runtime_watermark_utc=row.LastQueryRuntimeWatermarkUtc,
                    last_successful_query_batch_id=(
                        UUID(str(row.LastSuccessfulQueryBatchId))
                        if row.LastSuccessfulQueryBatchId is not None
                        else None
                    ),
                    last_metadata_collected_at_utc=row.LastMetadataCollectedAtUtc,
                    last_metadata_batch_id=(
                        UUID(str(row.LastMetadataBatchId))
                        if row.LastMetadataBatchId is not None
                        else None
                    ),
                    updated_at_utc=row.UpdatedAtUtc,
                )
            finally:
                cursor.close()

    def advance_query_watermark(
        self,
        *,
        target_id: UUID,
        watermark_utc: datetime,
        batch_id: UUID,
    ) -> None:
        watermark = _utc_naive(watermark_utc)
        current = self.get(target_id)

        if (
            current is not None
            and current.last_query_runtime_watermark_utc is not None
            and watermark <= current.last_query_runtime_watermark_utc
        ):
            return

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                updated = cursor.execute(
                    """
                    UPDATE dbo.TargetCollectionState
                    SET
                        LastQueryRuntimeWatermarkUtc = ?,
                        LastSuccessfulQueryBatchId = ?,
                        UpdatedAtUtc = SYSUTCDATETIME()
                    WHERE TargetId = ?;
                    """,
                    watermark,
                    str(batch_id),
                    str(target_id),
                ).rowcount

                if updated == 0:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TargetCollectionState
                        (
                            TargetId,
                            LastQueryRuntimeWatermarkUtc,
                            LastSuccessfulQueryBatchId
                        )
                        VALUES (?, ?, ?);
                        """,
                        str(target_id),
                        watermark,
                        str(batch_id),
                    )

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def mark_metadata_collected(
        self,
        *,
        target_id: UUID,
        collected_at_utc: datetime,
        batch_id: UUID,
    ) -> None:
        collected_at = _utc_naive(collected_at_utc)

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                updated = cursor.execute(
                    """
                    UPDATE dbo.TargetCollectionState
                    SET
                        LastMetadataCollectedAtUtc = ?,
                        LastMetadataBatchId = ?,
                        UpdatedAtUtc = SYSUTCDATETIME()
                    WHERE TargetId = ?;
                    """,
                    collected_at,
                    str(batch_id),
                    str(target_id),
                ).rowcount

                if updated == 0:
                    cursor.execute(
                        """
                        INSERT INTO dbo.TargetCollectionState
                        (
                            TargetId,
                            LastMetadataCollectedAtUtc,
                            LastMetadataBatchId
                        )
                        VALUES (?, ?, ?);
                        """,
                        str(target_id),
                        collected_at,
                        str(batch_id),
                    )

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
