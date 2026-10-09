from __future__ import annotations
from uuid import UUID

from collector.repository.connection import RepositorySettings, repository_connection

class SqlComponentResultRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def start(self, batch_id: UUID, component_name: str) -> None:
        self._upsert(
            batch_id=batch_id,
            component_name=component_name,
            status="Collecting",
            rows_collected=None,
            error_code=None,
            error_message=None,
            status_message=None,
            set_started=True,
            set_completed=False,
        )

    def complete(
        self,
        batch_id: UUID,
        component_name: str,
        rows_collected: int,
    ) -> None:
        self._upsert(
            batch_id=batch_id,
            component_name=component_name,
            status="Completed",
            rows_collected=rows_collected,
            error_code=None,
            error_message=None,
            status_message=None,
            set_started=False,
            set_completed=True,
        )

    def skip(
        self,
        batch_id: UUID,
        component_name: str,
        *,
        status_message: str,
    ) -> None:
        self._upsert(
            batch_id=batch_id,
            component_name=component_name,
            status="Skipped",
            rows_collected=0,
            error_code=None,
            error_message=None,
            status_message=status_message[:2000],
            set_started=False,
            set_completed=True,
        )

    def fail(
        self,
        batch_id: UUID,
        component_name: str,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        self._upsert(
            batch_id=batch_id,
            component_name=component_name,
            status="Failed",
            rows_collected=None,
            error_code=error_code[:100],
            error_message=error_message[:2000],
            status_message=None,
            set_started=False,
            set_completed=True,
        )

    def list(self, batch_id: UUID) -> list[dict[str, object]]:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                rows = cursor.execute(
                    """
                    SELECT
                        ComponentName,
                        Status,
                        RowsCollected,
                        StartedAtUtc,
                        CompletedAtUtc,
                        ErrorCode,
                        ErrorMessage,
                        StatusMessage
                    FROM dbo.CollectionComponentResult
                    WHERE BatchId = ?
                    ORDER BY ComponentName;
                    """,
                    str(batch_id),
                ).fetchall()

                return [
                    {
                        "component_name": row.ComponentName,
                        "status": row.Status,
                        "rows_collected": row.RowsCollected,
                        "started_at_utc": row.StartedAtUtc,
                        "completed_at_utc": row.CompletedAtUtc,
                        "error_code": row.ErrorCode,
                        "error_message": row.ErrorMessage,
                        "status_message": row.StatusMessage,
                    }
                    for row in rows
                ]
            finally:
                cursor.close()

    def _upsert(
        self,
        *,
        batch_id: UUID,
        component_name: str,
        status: str,
        rows_collected: int | None,
        error_code: str | None,
        error_message: str | None,
        status_message: str | None,
        set_started: bool,
        set_completed: bool,
    ) -> None:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                existing = cursor.execute(
                    """
                    SELECT 1
                    FROM dbo.CollectionComponentResult
                    WHERE BatchId = ?
                      AND ComponentName = ?;
                    """,
                    str(batch_id),
                    component_name,
                ).fetchone()

                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO dbo.CollectionComponentResult
                        (
                            BatchId,
                            ComponentName,
                            Status,
                            RowsCollected,
                            StartedAtUtc,
                            CompletedAtUtc,
                            ErrorCode,
                            ErrorMessage,
                            StatusMessage
                        )
                        VALUES
                        (
                            ?, ?, ?, ?,
                            CASE WHEN ? = 1 THEN SYSUTCDATETIME() ELSE NULL END,
                            CASE WHEN ? = 1 THEN SYSUTCDATETIME() ELSE NULL END,
                            ?, ?, ?
                        );
                        """,
                        str(batch_id),
                        component_name,
                        status,
                        rows_collected,
                        set_started,
                        set_completed,
                        error_code,
                        error_message,
                        status_message,
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE dbo.CollectionComponentResult
                        SET
                            Status = ?,
                            RowsCollected = ?,
                            StartedAtUtc =
                                CASE
                                    WHEN ? = 1
                                    THEN COALESCE(StartedAtUtc, SYSUTCDATETIME())
                                    ELSE StartedAtUtc
                                END,
                            CompletedAtUtc =
                                CASE
                                    WHEN ? = 1
                                    THEN SYSUTCDATETIME()
                                    ELSE NULL
                                END,
                            ErrorCode = ?,
                            ErrorMessage = ?,
                            StatusMessage = ?
                        WHERE BatchId = ?
                          AND ComponentName = ?;
                        """,
                        status,
                        rows_collected,
                        set_started,
                        set_completed,
                        error_code,
                        error_message,
                        status_message,
                        str(batch_id),
                        component_name,
                    )

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
