from collector.collection.records import SourceState


def read_source_state(connection) -> SourceState:
    cursor = connection.cursor()
    try:
        row = cursor.execute(
            """
            SELECT
                SYSUTCDATETIME() AS ObservedAtUtc,
                osi.sqlserver_start_time AS SqlServerStartTimeUtc,
                DB_ID() AS DatabaseId,
                d.create_date AS DatabaseCreateDateUtc,
                qso.actual_state_desc AS QueryStoreActualState,
                (SELECT MAX(runtime_stats_interval_id) FROM sys.query_store_runtime_stats_interval) AS QueryStoreMaxIntervalId,
                (SELECT MAX(query_id) FROM sys.query_store_query) AS QueryStoreMaxQueryId,
                (SELECT MAX(plan_id) FROM sys.query_store_plan) AS QueryStoreMaxPlanId
            FROM sys.dm_os_sys_info AS osi
            INNER JOIN sys.databases AS d ON d.database_id = DB_ID()
            LEFT JOIN sys.database_query_store_options AS qso ON 1 = 1;
            """
        ).fetchone()
        return SourceState(
            observed_at_utc=row.ObservedAtUtc,
            sql_server_start_time_utc=row.SqlServerStartTimeUtc,
            database_id=int(row.DatabaseId),
            database_create_date_utc=row.DatabaseCreateDateUtc,
            query_store_actual_state=row.QueryStoreActualState,
            query_store_max_interval_id=row.QueryStoreMaxIntervalId,
            query_store_max_query_id=row.QueryStoreMaxQueryId,
            query_store_max_plan_id=row.QueryStoreMaxPlanId,
        )
    finally:
        cursor.close()
