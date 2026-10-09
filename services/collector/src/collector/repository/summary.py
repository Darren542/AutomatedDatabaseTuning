from __future__ import annotations
from uuid import UUID

from collector.repository.connection import RepositorySettings, repository_connection

class SqlCollectionSummaryRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def source_state(self, batch_id: UUID) -> dict[str, object] | None:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        ObservedAtUtc,
                        SqlServerStartTimeUtc,
                        QueryStoreActualState,
                        DmvResetDetected,
                        QueryStoreResetDetected
                    FROM dbo.CollectionSourceState
                    WHERE BatchId = ?;
                    """,
                    str(batch_id),
                ).fetchone()

                if row is None:
                    return None

                return {
                    "observed_at_utc": row.ObservedAtUtc,
                    "sql_server_start_time_utc": row.SqlServerStartTimeUtc,
                    "query_store_actual_state": row.QueryStoreActualState,
                    "dmv_reset_detected": bool(row.DmvResetDetected),
                    "query_store_reset_detected": bool(row.QueryStoreResetDetected),
                }
            finally:
                cursor.close()

    def evidence_counts(self, batch_id: UUID) -> dict[str, int]:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        (SELECT COUNT_BIG(*) FROM dbo.CollectionQueryStoreEvidence WHERE BatchId = ?) AS QueryRuntimeRows,
                        (SELECT COUNT_BIG(*) FROM dbo.IndexUsageObservation WHERE BatchId = ?) AS IndexUsageRows,
                        (SELECT COUNT_BIG(*) FROM dbo.IndexOperationalObservation WHERE BatchId = ?) AS IndexOperationalRows,
                        (SELECT COUNT_BIG(*) FROM dbo.MissingIndexObservation WHERE BatchId = ?) AS MissingIndexRows,
                        (SELECT COUNT_BIG(*) FROM dbo.TableMetadataSnapshot WHERE BatchId = ?) AS TableMetadataRows,
                        (SELECT COUNT_BIG(*) FROM dbo.ColumnMetadataSnapshot WHERE BatchId = ?) AS ColumnMetadataRows,
                        (SELECT COUNT_BIG(*) FROM dbo.IndexMetadataSnapshot WHERE BatchId = ?) AS IndexMetadataRows,
                        (SELECT COUNT_BIG(*) FROM dbo.IndexColumnMetadataSnapshot WHERE BatchId = ?) AS IndexColumnMetadataRows,
                        (SELECT COUNT_BIG(*) FROM dbo.ConstraintMetadataSnapshot WHERE BatchId = ?) AS ConstraintMetadataRows;
                    """,
                    *([str(batch_id)] * 9),
                ).fetchone()

                metadata_rows = (
                    int(row.TableMetadataRows)
                    + int(row.ColumnMetadataRows)
                    + int(row.IndexMetadataRows)
                    + int(row.IndexColumnMetadataRows)
                    + int(row.ConstraintMetadataRows)
                )

                return {
                    "query_runtime_rows": int(row.QueryRuntimeRows),
                    "index_usage_rows": int(row.IndexUsageRows),
                    "index_operational_rows": int(row.IndexOperationalRows),
                    "missing_index_rows": int(row.MissingIndexRows),
                    "table_metadata_rows": int(row.TableMetadataRows),
                    "column_metadata_rows": int(row.ColumnMetadataRows),
                    "index_metadata_rows": int(row.IndexMetadataRows),
                    "index_column_metadata_rows": int(row.IndexColumnMetadataRows),
                    "constraint_metadata_rows": int(row.ConstraintMetadataRows),
                    "metadata_rows": metadata_rows,
                }
            finally:
                cursor.close()

    def query_runtime_totals(self, batch_id: UUID) -> dict[str, float | int]:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        COUNT_BIG(*) AS RuntimeEvidenceRows,
                        COALESCE(SUM(CAST(e.ExecutionCount AS BIGINT)), 0) AS ExecutionCount,
                        COALESCE(
                            SUM(COALESCE(e.AvgDurationMicroseconds, 0) * e.ExecutionCount) / 1000.0,
                            0
                        ) AS TotalDurationMs,
                        COALESCE(
                            SUM(COALESCE(e.AvgCpuTimeMicroseconds, 0) * e.ExecutionCount) / 1000.0,
                            0
                        ) AS TotalCpuMs,
                        COALESCE(
                            SUM(COALESCE(e.AvgLogicalIoReads, 0) * e.ExecutionCount),
                            0
                        ) AS LogicalReads,
                        COALESCE(
                            SUM(COALESCE(e.AvgLogicalIoWrites, 0) * e.ExecutionCount),
                            0
                        ) AS LogicalWrites,
                        COALESCE(
                            SUM(COALESCE(e.AvgPhysicalIoReads, 0) * e.ExecutionCount),
                            0
                        ) AS PhysicalReads
                    FROM dbo.CollectionQueryStoreEvidence AS b
                    INNER JOIN dbo.QueryStoreRuntimeEvidence AS e
                        ON e.EvidenceId = b.EvidenceId
                    WHERE b.BatchId = ?;
                    """,
                    str(batch_id),
                ).fetchone()

                return {
                    "runtime_evidence_rows": int(row.RuntimeEvidenceRows),
                    "execution_count": int(row.ExecutionCount),
                    "total_duration_ms": float(row.TotalDurationMs),
                    "total_cpu_ms": float(row.TotalCpuMs),
                    "logical_reads": float(row.LogicalReads),
                    "logical_writes": float(row.LogicalWrites),
                    "physical_reads": float(row.PhysicalReads),
                }
            finally:
                cursor.close()
