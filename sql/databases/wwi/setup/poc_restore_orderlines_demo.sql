USE [WideWorldImporters];
GO

SET NOCOUNT ON;
GO

PRINT '=== Restoring WWI OrderLines demo indexes ===';

IF EXISTS
(
    SELECT 1
    FROM sys.indexes i
    JOIN sys.tables t ON t.object_id = i.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'Sales'
      AND t.name = 'OrderLines'
      AND i.name = 'IX_Sales_OrderLines_Perf_20160301_01'
      AND i.is_disabled = 1
)
BEGIN
    ALTER INDEX [IX_Sales_OrderLines_Perf_20160301_01]
    ON [Sales].[OrderLines]
    REBUILD;
END
GO

IF EXISTS
(
    SELECT 1
    FROM sys.indexes i
    JOIN sys.tables t ON t.object_id = i.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'Sales'
      AND t.name = 'OrderLines'
      AND i.name = 'NCCX_Sales_OrderLines'
      AND i.is_disabled = 1
)
BEGIN
    ALTER INDEX [NCCX_Sales_OrderLines]
    ON [Sales].[OrderLines]
    REBUILD;
END
GO

DECLARE @DropSql NVARCHAR(MAX) = N'';

SELECT @DropSql = @DropSql +
    N'DROP INDEX [' + i.name + N'] ON [' + s.name + N'].[' + t.name + N'];' + CHAR(13) + CHAR(10)
FROM sys.indexes AS i
INNER JOIN sys.tables AS t
    ON t.object_id = i.object_id
INNER JOIN sys.schemas AS s
    ON s.schema_id = t.schema_id
WHERE i.name LIKE N'IX_POC[_]%'
  AND i.index_id > 0
  AND i.is_hypothetical = 0;

IF @DropSql <> N''
    EXEC sp_executesql @DropSql;
GO

SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    i.name AS IndexName,
    i.type_desc,
    i.is_disabled
FROM sys.indexes i
JOIN sys.tables t ON t.object_id = i.object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'Sales'
  AND t.name = 'OrderLines'
ORDER BY i.name;
GO