"""WC-03: read closed Query Store runtime intervals and plan/query references."""

from __future__ import annotations

from datetime import datetime

from collector.collection.records import QueryRuntimeEvidence


def read_query_runtime(
    connection,
    *,
    requested_window_start_utc: datetime | None = None,
    requested_window_end_utc: datetime | None = None,
) -> list[QueryRuntimeEvidence]:
    """
    Read Query Store runtime evidence from completed intervals.

    Query Store timestamp columns are datetimeoffset. Some pyodbc versions do
    not deserialize SQL Server datetimeoffset (ODBC type -155), so all Query
    Store timestamps are normalized to UTC and converted to datetime2 before
    they are returned to Python.
    """

    interval_start_expression = """
        CAST(
            SWITCHOFFSET(rsi.start_time, '+00:00')
            AS datetime2(7)
        )
    """

    interval_end_expression = """
        CAST(
            SWITCHOFFSET(rsi.end_time, '+00:00')
            AS datetime2(7)
        )
    """

    filters = [
        # Only collect completed Query Store intervals.
        # The current/open interval can still change and therefore is not
        # suitable as canonical evidence.
        f"{interval_end_expression} <= SYSUTCDATETIME()"
    ]

    parameters: list[object] = []

    if requested_window_start_utc is not None:
        filters.append(
            f"{interval_end_expression} > ?"
        )
        parameters.append(requested_window_start_utc)

    if requested_window_end_utc is not None:
        filters.append(
            f"{interval_start_expression} < ?"
        )
        parameters.append(requested_window_end_utc)

    where_clause = " AND ".join(filters)

    sql = f"""
        SELECT
            rsi.runtime_stats_interval_id
                AS RuntimeStatsIntervalId,

            rs.runtime_stats_id
                AS RuntimeStatsId,

            p.plan_id
                AS PlanId,

            q.query_id
                AS QueryId,

            q.query_text_id
                AS QueryTextId,

            NULLIF(q.object_id, 0)
                AS ObjectId,

            q.query_hash
                AS QueryHash,

            p.query_plan_hash
                AS QueryPlanHash,

            qt.query_sql_text
                AS QuerySqlText,

            rs.execution_type
                AS ExecutionType,

            rs.execution_type_desc
                AS ExecutionTypeDesc,

            CAST(
                SWITCHOFFSET(rsi.start_time, '+00:00')
                AS datetime2(7)
            ) AS IntervalStartUtc,

            CAST(
                SWITCHOFFSET(rsi.end_time, '+00:00')
                AS datetime2(7)
            ) AS IntervalEndUtc,

            CAST(
                SWITCHOFFSET(rs.first_execution_time, '+00:00')
                AS datetime2(7)
            ) AS FirstExecutionTimeUtc,

            CAST(
                SWITCHOFFSET(rs.last_execution_time, '+00:00')
                AS datetime2(7)
            ) AS LastExecutionTimeUtc,

            rs.count_executions
                AS ExecutionCount,

            rs.avg_duration
                AS AvgDurationMicroseconds,

            rs.avg_cpu_time
                AS AvgCpuTimeMicroseconds,

            rs.avg_logical_io_reads
                AS AvgLogicalIoReads,

            rs.avg_logical_io_writes
                AS AvgLogicalIoWrites,

            rs.avg_physical_io_reads
                AS AvgPhysicalIoReads,

            rs.avg_rowcount
                AS AvgRowCount

        FROM sys.query_store_runtime_stats AS rs

        INNER JOIN sys.query_store_runtime_stats_interval AS rsi
            ON rsi.runtime_stats_interval_id =
               rs.runtime_stats_interval_id

        INNER JOIN sys.query_store_plan AS p
            ON p.plan_id = rs.plan_id

        INNER JOIN sys.query_store_query AS q
            ON q.query_id = p.query_id

        INNER JOIN sys.query_store_query_text AS qt
            ON qt.query_text_id = q.query_text_id

        WHERE {where_clause}

        ORDER BY
            rsi.start_time,
            q.query_id,
            p.plan_id,
            rs.runtime_stats_id;
    """

    cursor = connection.cursor()

    try:
        rows = cursor.execute(
            sql,
            *parameters,
        ).fetchall()

        return [
            QueryRuntimeEvidence(
                runtime_stats_interval_id=int(
                    row.RuntimeStatsIntervalId
                ),
                runtime_stats_id=int(
                    row.RuntimeStatsId
                ),
                plan_id=int(
                    row.PlanId
                ),
                query_id=int(
                    row.QueryId
                ),
                query_text_id=int(
                    row.QueryTextId
                ),
                object_id=(
                    int(row.ObjectId)
                    if row.ObjectId is not None
                    else None
                ),
                query_hash=(
                    bytes(row.QueryHash)
                    if row.QueryHash is not None
                    else None
                ),
                query_plan_hash=(
                    bytes(row.QueryPlanHash)
                    if row.QueryPlanHash is not None
                    else None
                ),
                query_sql_text=str(
                    row.QuerySqlText
                ),
                execution_type=int(
                    row.ExecutionType
                ),
                execution_type_desc=(
                    row.ExecutionTypeDesc
                ),
                interval_start_utc=(
                    row.IntervalStartUtc
                ),
                interval_end_utc=(
                    row.IntervalEndUtc
                ),
                first_execution_time_utc=(
                    row.FirstExecutionTimeUtc
                ),
                last_execution_time_utc=(
                    row.LastExecutionTimeUtc
                ),
                execution_count=int(
                    row.ExecutionCount
                ),
                avg_duration_microseconds=(
                    float(row.AvgDurationMicroseconds)
                    if row.AvgDurationMicroseconds is not None
                    else None
                ),
                avg_cpu_time_microseconds=(
                    float(row.AvgCpuTimeMicroseconds)
                    if row.AvgCpuTimeMicroseconds is not None
                    else None
                ),
                avg_logical_io_reads=(
                    float(row.AvgLogicalIoReads)
                    if row.AvgLogicalIoReads is not None
                    else None
                ),
                avg_logical_io_writes=(
                    float(row.AvgLogicalIoWrites)
                    if row.AvgLogicalIoWrites is not None
                    else None
                ),
                avg_physical_io_reads=(
                    float(row.AvgPhysicalIoReads)
                    if row.AvgPhysicalIoReads is not None
                    else None
                ),
                avg_row_count=(
                    float(row.AvgRowCount)
                    if row.AvgRowCount is not None
                    else None
                ),
            )
            for row in rows
        ]

    finally:
        cursor.close()