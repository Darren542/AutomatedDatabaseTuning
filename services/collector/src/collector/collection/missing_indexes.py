from collector.collection.records import MissingIndexObservation


def read_missing_indexes(connection) -> list[MissingIndexObservation]:
    cursor = connection.cursor()
    try:
        rows = cursor.execute(
            """
            SELECT
                mig.index_group_handle AS GroupHandle,
                mid.index_handle AS IndexHandle,
                mid.object_id AS ObjectId,
                s.name AS SchemaName,
                t.name AS TableName,
                mid.equality_columns AS EqualityColumns,
                mid.inequality_columns AS InequalityColumns,
                mid.included_columns AS IncludedColumns,
                migs.user_seeks AS UserSeeks,
                migs.user_scans AS UserScans,
                migs.last_user_seek AS LastUserSeekUtc,
                migs.last_user_scan AS LastUserScanUtc,
                migs.avg_total_user_cost AS AvgTotalUserCost,
                migs.avg_user_impact AS AvgUserImpact
            FROM sys.dm_db_missing_index_group_stats AS migs
            INNER JOIN sys.dm_db_missing_index_groups AS mig
                ON mig.index_group_handle = migs.group_handle
            INNER JOIN sys.dm_db_missing_index_details AS mid
                ON mid.index_handle = mig.index_handle
            INNER JOIN sys.tables AS t ON t.object_id = mid.object_id
            INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            WHERE mid.database_id = DB_ID() AND t.is_ms_shipped = 0
            ORDER BY s.name, t.name, mig.index_group_handle, mid.index_handle;
            """
        ).fetchall()
        return [
            MissingIndexObservation(
                group_handle=int(r.GroupHandle), index_handle=int(r.IndexHandle), object_id=int(r.ObjectId),
                schema_name=str(r.SchemaName), table_name=str(r.TableName),
                equality_columns=r.EqualityColumns, inequality_columns=r.InequalityColumns,
                included_columns=r.IncludedColumns, user_seeks=int(r.UserSeeks), user_scans=int(r.UserScans),
                last_user_seek_utc=r.LastUserSeekUtc, last_user_scan_utc=r.LastUserScanUtc,
                avg_total_user_cost=float(r.AvgTotalUserCost), avg_user_impact=float(r.AvgUserImpact),
            ) for r in rows
        ]
    finally:
        cursor.close()
