from collector.collection.records import (
    ColumnMetadata, ConstraintMetadata, IndexColumnMetadata,
    IndexMetadata, MetadataBundle, TableMetadata,
)


def read_metadata(connection) -> MetadataBundle:
    cursor = connection.cursor()
    try:
        table_rows = cursor.execute(
            """
            SELECT t.object_id AS ObjectId, s.name AS SchemaName, t.name AS TableName,
                   COALESCE(SUM(CASE WHEN ps.index_id IN (0,1) THEN ps.row_count ELSE 0 END),0) AS [RowCount],
                   CAST(COALESCE(SUM(ps.reserved_page_count),0)*8.0/1024.0 AS DECIMAL(19,3)) AS ReservedSizeMb,
                   CAST(COALESCE(SUM(ps.used_page_count),0)*8.0/1024.0 AS DECIMAL(19,3)) AS UsedSizeMb,
                   CAST(COALESCE(SUM(CASE WHEN ps.index_id IN (0,1)
                        THEN ps.in_row_data_page_count + ps.lob_used_page_count + ps.row_overflow_used_page_count
                        ELSE 0 END),0)*8.0/1024.0 AS DECIMAL(19,3)) AS DataSizeMb
            FROM sys.tables AS t
            INNER JOIN sys.schemas AS s ON s.schema_id=t.schema_id
            LEFT JOIN sys.dm_db_partition_stats AS ps ON ps.object_id=t.object_id
            WHERE t.is_ms_shipped=0
            GROUP BY t.object_id,s.name,t.name
            ORDER BY s.name,t.name;
            """
        ).fetchall()

        column_rows = cursor.execute(
            """
            SELECT c.object_id AS ObjectId,c.column_id AS ColumnId,c.name AS ColumnName,
                   ty.name AS DataType,c.max_length AS MaxLength,c.precision AS NumericPrecision,
                   c.scale AS NumericScale,c.is_nullable AS IsNullable,c.is_identity AS IsIdentity,
                   c.is_computed AS IsComputed
            FROM sys.columns AS c
            INNER JOIN sys.tables AS t ON t.object_id=c.object_id
            INNER JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
            WHERE t.is_ms_shipped=0
            ORDER BY c.object_id,c.column_id;
            """
        ).fetchall()

        index_rows = cursor.execute(
            """
            SELECT i.object_id AS ObjectId,i.index_id AS IndexId,i.name AS IndexName,
                   i.type AS IndexType,i.type_desc AS IndexTypeDesc,i.is_unique AS IsUnique,
                   i.is_primary_key AS IsPrimaryKey,i.is_unique_constraint AS IsUniqueConstraint,
                   i.is_disabled AS IsDisabled,i.has_filter AS HasFilter,i.filter_definition AS FilterDefinition
            FROM sys.indexes AS i
            INNER JOIN sys.tables AS t ON t.object_id=i.object_id
            WHERE t.is_ms_shipped=0
            ORDER BY i.object_id,i.index_id;
            """
        ).fetchall()

        index_column_rows = cursor.execute(
            """
            SELECT ic.object_id AS ObjectId,ic.index_id AS IndexId,ic.column_id AS ColumnId,
                   ic.key_ordinal AS KeyOrdinal,ic.index_column_id AS IndexColumnId,
                   ic.is_included_column AS IsIncludedColumn,ic.is_descending_key AS IsDescendingKey
            FROM sys.index_columns AS ic
            INNER JOIN sys.tables AS t ON t.object_id=ic.object_id
            WHERE t.is_ms_shipped=0
            ORDER BY ic.object_id,ic.index_id,ic.index_column_id;
            """
        ).fetchall()

        constraint_rows = cursor.execute(
            """
            SELECT kc.parent_object_id AS ObjectId,kc.object_id AS ConstraintObjectId,
                   kc.name AS ConstraintName,
                   CASE kc.type WHEN 'PK' THEN 'PRIMARY_KEY' WHEN 'UQ' THEN 'UNIQUE' ELSE kc.type_desc END AS ConstraintType,
                   kc.unique_index_id AS UniqueIndexId,CAST(NULL AS INT) AS ReferencedObjectId,
                   CAST(NULL AS BIT) AS IsDisabled
            FROM sys.key_constraints AS kc
            INNER JOIN sys.tables AS t ON t.object_id=kc.parent_object_id
            WHERE t.is_ms_shipped=0
            UNION ALL
            SELECT fk.parent_object_id,fk.object_id,fk.name,'FOREIGN_KEY',NULL,fk.referenced_object_id,fk.is_disabled
            FROM sys.foreign_keys AS fk
            INNER JOIN sys.tables AS t ON t.object_id=fk.parent_object_id
            WHERE t.is_ms_shipped=0
            UNION ALL
            SELECT cc.parent_object_id,cc.object_id,cc.name,'CHECK',NULL,NULL,cc.is_disabled
            FROM sys.check_constraints AS cc
            INNER JOIN sys.tables AS t ON t.object_id=cc.parent_object_id
            WHERE t.is_ms_shipped=0;
            """
        ).fetchall()

        return MetadataBundle(
            tables=[TableMetadata(int(r.ObjectId),str(r.SchemaName),str(r.TableName),int(r.RowCount),float(r.ReservedSizeMb),float(r.UsedSizeMb),float(r.DataSizeMb)) for r in table_rows],
            columns=[ColumnMetadata(int(r.ObjectId),int(r.ColumnId),str(r.ColumnName),str(r.DataType),int(r.MaxLength),int(r.NumericPrecision),int(r.NumericScale),bool(r.IsNullable),bool(r.IsIdentity),bool(r.IsComputed)) for r in column_rows],
            indexes=[IndexMetadata(int(r.ObjectId),int(r.IndexId),r.IndexName,int(r.IndexType),str(r.IndexTypeDesc),bool(r.IsUnique),bool(r.IsPrimaryKey),bool(r.IsUniqueConstraint),bool(r.IsDisabled),bool(r.HasFilter),r.FilterDefinition) for r in index_rows],
            index_columns=[IndexColumnMetadata(int(r.ObjectId),int(r.IndexId),int(r.ColumnId),int(r.KeyOrdinal),int(r.IndexColumnId),bool(r.IsIncludedColumn),bool(r.IsDescendingKey)) for r in index_column_rows],
            constraints=[ConstraintMetadata(int(r.ObjectId),int(r.ConstraintObjectId),str(r.ConstraintName),str(r.ConstraintType),int(r.UniqueIndexId) if r.UniqueIndexId is not None else None,int(r.ReferencedObjectId) if r.ReferencedObjectId is not None else None,bool(r.IsDisabled) if r.IsDisabled is not None else None) for r in constraint_rows],
        )
    finally:
        cursor.close()
