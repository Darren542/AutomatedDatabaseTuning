from collector.collection.records import IndexUsageObservation


def read_index_usage(connection) -> list[IndexUsageObservation]:
    cursor = connection.cursor()
    try:
        rows = cursor.execute(
            """
            SELECT
                i.object_id AS ObjectId,
                i.index_id AS IndexId,
                s.name AS SchemaName,
                t.name AS TableName,
                i.name AS IndexName,
                COALESCE(u.user_seeks, 0) AS UserSeeks,
                COALESCE(u.user_scans, 0) AS UserScans,
                COALESCE(u.user_lookups, 0) AS UserLookups,
                COALESCE(u.user_updates, 0) AS UserUpdates,
                u.last_user_seek AS LastUserSeekUtc,
                u.last_user_scan AS LastUserScanUtc,
                u.last_user_lookup AS LastUserLookupUtc,
                u.last_user_update AS LastUserUpdateUtc
            FROM sys.tables AS t
            INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            INNER JOIN sys.indexes AS i ON i.object_id = t.object_id
            LEFT JOIN sys.dm_db_index_usage_stats AS u
                ON u.database_id = DB_ID()
                AND u.object_id = i.object_id
                AND u.index_id = i.index_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name, i.index_id;
            """
        ).fetchall()
        return [
            IndexUsageObservation(
                object_id=int(r.ObjectId), index_id=int(r.IndexId),
                schema_name=str(r.SchemaName), table_name=str(r.TableName), index_name=r.IndexName,
                user_seeks=int(r.UserSeeks), user_scans=int(r.UserScans),
                user_lookups=int(r.UserLookups), user_updates=int(r.UserUpdates),
                last_user_seek_utc=r.LastUserSeekUtc, last_user_scan_utc=r.LastUserScanUtc,
                last_user_lookup_utc=r.LastUserLookupUtc, last_user_update_utc=r.LastUserUpdateUtc,
            ) for r in rows
        ]
    finally:
        cursor.close()
