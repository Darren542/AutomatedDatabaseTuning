from __future__ import annotations

from datetime import datetime
from uuid import UUID

from collector.collection.records import (
    IndexOperationalObservation, IndexUsageObservation, MetadataBundle,
    MissingIndexObservation, QueryRuntimeEvidence, SourceState,
)
from collector.repository.connection import RepositorySettings, repository_connection


def _executemany(cursor, sql, params):
    if params:
        cursor.executemany(sql, params)


class SqlEvidenceRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def save_source_state(self, *, batch_id: UUID, target_id: UUID, state: SourceState) -> tuple[bool, bool]:
        with repository_connection(self._settings) as conn:
            cur = conn.cursor()
            try:
                prev = cur.execute(
                    """SELECT TOP (1) SqlServerStartTimeUtc,QueryStoreMaxIntervalId,QueryStoreMaxQueryId,QueryStoreMaxPlanId
                       FROM dbo.CollectionSourceState WHERE TargetId=? AND BatchId<>? ORDER BY ObservedAtUtc DESC;""",
                    str(target_id), str(batch_id),
                ).fetchone()
                dmv_reset = bool(prev and prev.SqlServerStartTimeUtc is not None and state.sql_server_start_time_utc is not None and prev.SqlServerStartTimeUtc != state.sql_server_start_time_utc)
                qs_reset = False
                if prev:
                    old = (prev.QueryStoreMaxIntervalId, prev.QueryStoreMaxQueryId, prev.QueryStoreMaxPlanId)
                    new = (state.query_store_max_interval_id, state.query_store_max_query_id, state.query_store_max_plan_id)
                    qs_reset = any(a is not None and b is not None and b < a for a,b in zip(old,new))

                cur.execute("DELETE FROM dbo.CollectionSourceState WHERE BatchId=?;", str(batch_id))
                cur.execute(
                    """INSERT INTO dbo.CollectionSourceState
                       (BatchId,TargetId,ObservedAtUtc,SqlServerStartTimeUtc,DatabaseId,DatabaseCreateDateUtc,
                        QueryStoreActualState,QueryStoreMaxIntervalId,QueryStoreMaxQueryId,QueryStoreMaxPlanId,
                        DmvResetDetected,QueryStoreResetDetected)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?);""",
                    str(batch_id), str(target_id), state.observed_at_utc, state.sql_server_start_time_utc,
                    state.database_id, state.database_create_date_utc, state.query_store_actual_state,
                    state.query_store_max_interval_id, state.query_store_max_query_id, state.query_store_max_plan_id,
                    dmv_reset, qs_reset,
                )
                conn.commit(); return dmv_reset, qs_reset
            except Exception:
                conn.rollback(); raise
            finally:
                cur.close()

    def save_query_runtime(
        self,
        *,
        batch_id: UUID,
        target_id: UUID,
        rows: list[QueryRuntimeEvidence],
    ) -> int:
        """
        Upsert canonical Query Store runtime evidence and link it to this batch.

        Canonical identity:
            TargetId
            + RuntimeStatsIntervalId
            + RuntimeStatsId

        The EvidenceId is always looked up using that canonical key after the
        upsert. We intentionally do not use SCOPE_IDENTITY(), because an existing
        canonical row may be updated rather than inserted.
        """

        with repository_connection(self._settings) as conn:
            cur = conn.cursor()

            try:
                # Rebuilding membership makes persistence retry-safe for the
                # same batch.
                cur.execute(
                    """
                    DELETE FROM dbo.CollectionQueryStoreEvidence
                    WHERE BatchId = ?;
                    """,
                    str(batch_id),
                )

                linked = 0

                for item in rows:
                    # First attempt to update existing canonical evidence.
                    cur.execute(
                        """
                        UPDATE dbo.QueryStoreRuntimeEvidence
                        SET
                            PlanId = ?,
                            QueryId = ?,
                            QueryTextId = ?,
                            ObjectId = ?,

                            QueryHash = ?,
                            QueryPlanHash = ?,
                            QuerySqlText = ?,

                            ExecutionType = ?,
                            ExecutionTypeDesc = ?,

                            IntervalStartUtc = ?,
                            IntervalEndUtc = ?,

                            FirstExecutionTimeUtc = ?,
                            LastExecutionTimeUtc = ?,

                            ExecutionCount = ?,

                            AvgDurationMicroseconds = ?,
                            AvgCpuTimeMicroseconds = ?,
                            AvgLogicalIoReads = ?,
                            AvgLogicalIoWrites = ?,
                            AvgPhysicalIoReads = ?,
                            AvgRowCount = ?,

                            LastObservedAtUtc = SYSUTCDATETIME()

                        WHERE TargetId = ?
                        AND RuntimeStatsIntervalId = ?
                        AND RuntimeStatsId = ?;
                        """,
                        item.plan_id,
                        item.query_id,
                        item.query_text_id,
                        item.object_id,

                        item.query_hash,
                        item.query_plan_hash,
                        item.query_sql_text,

                        item.execution_type,
                        item.execution_type_desc,

                        item.interval_start_utc,
                        item.interval_end_utc,

                        item.first_execution_time_utc,
                        item.last_execution_time_utc,

                        item.execution_count,

                        item.avg_duration_microseconds,
                        item.avg_cpu_time_microseconds,
                        item.avg_logical_io_reads,
                        item.avg_logical_io_writes,
                        item.avg_physical_io_reads,
                        item.avg_row_count,

                        str(target_id),
                        item.runtime_stats_interval_id,
                        item.runtime_stats_id,
                    )

                    # If UPDATE matched nothing, this is new canonical evidence.
                    if cur.rowcount == 0:
                        cur.execute(
                            """
                            INSERT INTO dbo.QueryStoreRuntimeEvidence
                            (
                                TargetId,

                                RuntimeStatsIntervalId,
                                RuntimeStatsId,

                                PlanId,
                                QueryId,
                                QueryTextId,
                                ObjectId,

                                QueryHash,
                                QueryPlanHash,
                                QuerySqlText,

                                ExecutionType,
                                ExecutionTypeDesc,

                                IntervalStartUtc,
                                IntervalEndUtc,

                                FirstExecutionTimeUtc,
                                LastExecutionTimeUtc,

                                ExecutionCount,

                                AvgDurationMicroseconds,
                                AvgCpuTimeMicroseconds,
                                AvgLogicalIoReads,
                                AvgLogicalIoWrites,
                                AvgPhysicalIoReads,
                                AvgRowCount
                            )
                            VALUES
                            (
                                ?,
                                ?, ?,
                                ?, ?, ?, ?,
                                ?, ?, ?,
                                ?, ?,
                                ?, ?,
                                ?, ?,
                                ?,
                                ?, ?, ?, ?, ?, ?
                            );
                            """,
                            str(target_id),

                            item.runtime_stats_interval_id,
                            item.runtime_stats_id,

                            item.plan_id,
                            item.query_id,
                            item.query_text_id,
                            item.object_id,

                            item.query_hash,
                            item.query_plan_hash,
                            item.query_sql_text,

                            item.execution_type,
                            item.execution_type_desc,

                            item.interval_start_utc,
                            item.interval_end_utc,

                            item.first_execution_time_utc,
                            item.last_execution_time_utc,

                            item.execution_count,

                            item.avg_duration_microseconds,
                            item.avg_cpu_time_microseconds,
                            item.avg_logical_io_reads,
                            item.avg_logical_io_writes,
                            item.avg_physical_io_reads,
                            item.avg_row_count,
                        )

                    # Always retrieve the canonical identity using its stable
                    # source key. Do not depend on SCOPE_IDENTITY().
                    evidence_row = cur.execute(
                        """
                        SELECT EvidenceId
                        FROM dbo.QueryStoreRuntimeEvidence
                        WHERE TargetId = ?
                        AND RuntimeStatsIntervalId = ?
                        AND RuntimeStatsId = ?;
                        """,
                        str(target_id),
                        item.runtime_stats_interval_id,
                        item.runtime_stats_id,
                    ).fetchone()

                    if evidence_row is None:
                        raise RuntimeError(
                            "Query Store evidence was upserted but could not "
                            "be retrieved by its canonical source identity."
                        )

                    evidence_id = int(evidence_row.EvidenceId)

                    # Link this collection batch to the canonical evidence.
                    cur.execute(
                        """
                        INSERT INTO dbo.CollectionQueryStoreEvidence
                        (
                            BatchId,
                            EvidenceId
                        )
                        VALUES (?, ?);
                        """,
                        str(batch_id),
                        evidence_id,
                    )

                    linked += 1

                conn.commit()

                return linked

            except Exception:
                conn.rollback()
                raise

            finally:
                cur.close()

    def save_index_usage(self, *, batch_id: UUID, target_id: UUID, sql_server_start_time_utc: datetime | None, observed_at_utc: datetime, rows: list[IndexUsageObservation]) -> int:
        with repository_connection(self._settings) as conn:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM dbo.IndexUsageObservation WHERE BatchId=?;", str(batch_id))
                cur.fast_executemany = True
                _executemany(cur,
                    """INSERT INTO dbo.IndexUsageObservation
                       (BatchId,TargetId,ObjectId,IndexId,SchemaName,TableName,IndexName,UserSeeks,UserScans,UserLookups,UserUpdates,
                        LastUserSeekUtc,LastUserScanUtc,LastUserLookupUtc,LastUserUpdateUtc,SqlServerStartTimeUtc,ObservedAtUtc)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.index_id,x.schema_name,x.table_name,x.index_name,x.user_seeks,x.user_scans,x.user_lookups,x.user_updates,x.last_user_seek_utc,x.last_user_scan_utc,x.last_user_lookup_utc,x.last_user_update_utc,sql_server_start_time_utc,observed_at_utc) for x in rows],
                )
                conn.commit(); return len(rows)
            except Exception:
                conn.rollback(); raise
            finally: cur.close()

    def save_index_operational(self, *, batch_id: UUID, target_id: UUID, sql_server_start_time_utc: datetime | None, observed_at_utc: datetime, rows: list[IndexOperationalObservation]) -> int:
        with repository_connection(self._settings) as conn:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM dbo.IndexOperationalObservation WHERE BatchId=?;", str(batch_id))
                cur.fast_executemany = True
                _executemany(cur,
                    """INSERT INTO dbo.IndexOperationalObservation
                       (BatchId,TargetId,ObjectId,IndexId,PartitionNumber,SchemaName,TableName,IndexName,
                        LeafInsertCount,LeafDeleteCount,LeafUpdateCount,RowLockCount,RowLockWaitCount,RowLockWaitMs,
                        PageLockCount,PageLockWaitCount,PageLockWaitMs,PageLatchWaitCount,PageLatchWaitMs,
                        SqlServerStartTimeUtc,ObservedAtUtc)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.index_id,x.partition_number,x.schema_name,x.table_name,x.index_name,x.leaf_insert_count,x.leaf_delete_count,x.leaf_update_count,x.row_lock_count,x.row_lock_wait_count,x.row_lock_wait_ms,x.page_lock_count,x.page_lock_wait_count,x.page_lock_wait_ms,x.page_latch_wait_count,x.page_latch_wait_ms,sql_server_start_time_utc,observed_at_utc) for x in rows],
                )
                conn.commit(); return len(rows)
            except Exception:
                conn.rollback(); raise
            finally: cur.close()

    def save_missing_indexes(self, *, batch_id: UUID, target_id: UUID, sql_server_start_time_utc: datetime | None, observed_at_utc: datetime, rows: list[MissingIndexObservation]) -> int:
        with repository_connection(self._settings) as conn:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM dbo.MissingIndexObservation WHERE BatchId=?;", str(batch_id))
                cur.fast_executemany = True
                _executemany(cur,
                    """INSERT INTO dbo.MissingIndexObservation
                       (BatchId,TargetId,GroupHandle,IndexHandle,ObjectId,SchemaName,TableName,EqualityColumns,InequalityColumns,
                        IncludedColumns,UserSeeks,UserScans,LastUserSeekUtc,LastUserScanUtc,AvgTotalUserCost,AvgUserImpact,
                        SqlServerStartTimeUtc,ObservedAtUtc)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.group_handle,x.index_handle,x.object_id,x.schema_name,x.table_name,x.equality_columns,x.inequality_columns,x.included_columns,x.user_seeks,x.user_scans,x.last_user_seek_utc,x.last_user_scan_utc,x.avg_total_user_cost,x.avg_user_impact,sql_server_start_time_utc,observed_at_utc) for x in rows],
                )
                conn.commit(); return len(rows)
            except Exception:
                conn.rollback(); raise
            finally: cur.close()

    def save_metadata(self, *, batch_id: UUID, target_id: UUID, observed_at_utc: datetime, metadata: MetadataBundle) -> int:
        with repository_connection(self._settings) as conn:
            cur = conn.cursor()
            try:
                for table in ("ConstraintMetadataSnapshot","IndexColumnMetadataSnapshot","IndexMetadataSnapshot","ColumnMetadataSnapshot","TableMetadataSnapshot"):
                    cur.execute(f"DELETE FROM dbo.{table} WHERE BatchId=?;", str(batch_id))

                cur.fast_executemany = True
                _executemany(cur,"""INSERT INTO dbo.TableMetadataSnapshot
                    (BatchId,TargetId,ObjectId,SchemaName,TableName,[RowCount],ReservedSizeMb,UsedSizeMb,DataSizeMb,ObservedAtUtc)
                    VALUES (?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.schema_name,x.table_name,x.row_count,x.reserved_size_mb,x.used_size_mb,x.data_size_mb,observed_at_utc) for x in metadata.tables])
                _executemany(cur,"""INSERT INTO dbo.ColumnMetadataSnapshot
                    (BatchId,TargetId,ObjectId,ColumnId,ColumnName,DataType,MaxLength,NumericPrecision,NumericScale,IsNullable,IsIdentity,IsComputed)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.column_id,x.column_name,x.data_type,x.max_length,x.numeric_precision,x.numeric_scale,x.is_nullable,x.is_identity,x.is_computed) for x in metadata.columns])
                _executemany(cur,"""INSERT INTO dbo.IndexMetadataSnapshot
                    (BatchId,TargetId,ObjectId,IndexId,IndexName,IndexType,IndexTypeDesc,IsUnique,IsPrimaryKey,IsUniqueConstraint,IsDisabled,HasFilter,FilterDefinition)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.index_id,x.index_name,x.index_type,x.index_type_desc,x.is_unique,x.is_primary_key,x.is_unique_constraint,x.is_disabled,x.has_filter,x.filter_definition) for x in metadata.indexes])
                _executemany(cur,"""INSERT INTO dbo.IndexColumnMetadataSnapshot
                    (BatchId,TargetId,ObjectId,IndexId,ColumnId,KeyOrdinal,IndexColumnId,IsIncludedColumn,IsDescendingKey)
                    VALUES (?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.index_id,x.column_id,x.key_ordinal,x.index_column_id,x.is_included_column,x.is_descending_key) for x in metadata.index_columns])
                _executemany(cur,"""INSERT INTO dbo.ConstraintMetadataSnapshot
                    (BatchId,TargetId,ObjectId,ConstraintObjectId,ConstraintName,ConstraintType,UniqueIndexId,ReferencedObjectId,IsDisabled)
                    VALUES (?,?,?,?,?,?,?,?,?);""",
                    [(str(batch_id),str(target_id),x.object_id,x.constraint_object_id,x.constraint_name,x.constraint_type,x.unique_index_id,x.referenced_object_id,x.is_disabled) for x in metadata.constraints])
                conn.commit()
                return sum(map(len,(metadata.tables,metadata.columns,metadata.indexes,metadata.index_columns,metadata.constraints)))
            except Exception:
                conn.rollback(); raise
            finally: cur.close()
