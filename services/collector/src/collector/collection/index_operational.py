from collector.collection.records import IndexOperationalObservation


def read_index_operational(connection) -> list[IndexOperationalObservation]:
    cursor = connection.cursor()
    try:
        rows = cursor.execute(
            """
            SELECT
                os.object_id AS ObjectId,
                os.index_id AS IndexId,
                os.partition_number AS PartitionNumber,
                s.name AS SchemaName,
                t.name AS TableName,
                i.name AS IndexName,
                os.leaf_insert_count AS LeafInsertCount,
                os.leaf_delete_count AS LeafDeleteCount,
                os.leaf_update_count AS LeafUpdateCount,
                os.row_lock_count AS RowLockCount,
                os.row_lock_wait_count AS RowLockWaitCount,
                os.row_lock_wait_in_ms AS RowLockWaitMs,
                os.page_lock_count AS PageLockCount,
                os.page_lock_wait_count AS PageLockWaitCount,
                os.page_lock_wait_in_ms AS PageLockWaitMs,
                os.page_latch_wait_count AS PageLatchWaitCount,
                os.page_latch_wait_in_ms AS PageLatchWaitMs
            FROM sys.dm_db_index_operational_stats(DB_ID(), NULL, NULL, NULL) AS os
            INNER JOIN sys.tables AS t ON t.object_id = os.object_id
            INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            INNER JOIN sys.indexes AS i ON i.object_id = os.object_id AND i.index_id = os.index_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name, os.index_id, os.partition_number;
            """
        ).fetchall()
        return [
            IndexOperationalObservation(
                object_id=int(r.ObjectId), index_id=int(r.IndexId), partition_number=int(r.PartitionNumber),
                schema_name=str(r.SchemaName), table_name=str(r.TableName), index_name=r.IndexName,
                leaf_insert_count=int(r.LeafInsertCount), leaf_delete_count=int(r.LeafDeleteCount),
                leaf_update_count=int(r.LeafUpdateCount), row_lock_count=int(r.RowLockCount),
                row_lock_wait_count=int(r.RowLockWaitCount), row_lock_wait_ms=int(r.RowLockWaitMs),
                page_lock_count=int(r.PageLockCount), page_lock_wait_count=int(r.PageLockWaitCount),
                page_lock_wait_ms=int(r.PageLockWaitMs), page_latch_wait_count=int(r.PageLatchWaitCount),
                page_latch_wait_ms=int(r.PageLatchWaitMs),
            ) for r in rows
        ]
    finally:
        cursor.close()
