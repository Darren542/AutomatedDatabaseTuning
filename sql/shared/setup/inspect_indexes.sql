USE [WideWorldImporters];
GO

SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    i.name AS IndexName,
    i.type_desc,
    ic.key_ordinal,
    ic.is_included_column,
    c.name AS ColumnName
FROM sys.indexes AS i
INNER JOIN sys.tables AS t
    ON t.object_id = i.object_id
INNER JOIN sys.schemas AS s
    ON s.schema_id = t.schema_id
INNER JOIN sys.index_columns AS ic
    ON ic.object_id = i.object_id
   AND ic.index_id = i.index_id
INNER JOIN sys.columns AS c
    ON c.object_id = ic.object_id
   AND c.column_id = ic.column_id
WHERE s.name = 'Sales'
  AND t.name IN ('Orders', 'OrderLines')
ORDER BY
    t.name,
    i.name,
    ic.is_included_column,
    ic.key_ordinal,
    c.column_id;
GO