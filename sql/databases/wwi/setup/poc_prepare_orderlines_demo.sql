USE [WideWorldImporters];
GO

SET NOCOUNT ON;
GO

DECLARE @ClearQueryStore BIT = 1;
DECLARE @ClearPOCSnapshots BIT = 1;
DECLARE @DropPOCIndexes BIT = 1;

PRINT '=== Preparing OrderLines-focused WWI demo baseline ===';

------------------------------------------------------------------------------
-- 1) Drop any prior IX_POC_* indexes
------------------------------------------------------------------------------

IF @DropPOCIndexes = 1
BEGIN
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
END
GO

------------------------------------------------------------------------------
-- 2) Clear POC tables
------------------------------------------------------------------------------

IF OBJECT_ID('dbo.POC_QueryStoreSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_QueryStoreSnapshot;
IF OBJECT_ID('dbo.POC_MissingIndexSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_MissingIndexSnapshot;
IF OBJECT_ID('dbo.POC_IndexUsageSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_IndexUsageSnapshot;
IF OBJECT_ID('dbo.POC_RunHistory', 'U') IS NOT NULL DELETE FROM dbo.POC_RunHistory;
GO

------------------------------------------------------------------------------
-- 3) Clear Query Store for a clean read-only capture window
------------------------------------------------------------------------------

IF 1 = 1
BEGIN
    ALTER DATABASE CURRENT SET QUERY_STORE CLEAR ALL;
END
GO

------------------------------------------------------------------------------
-- 4) Disable WWI indexes that reduce the dramatic effect of the demo
--    These are safe to rebuild later.
------------------------------------------------------------------------------

IF EXISTS
(
    SELECT 1
    FROM sys.indexes i
    JOIN sys.tables t ON t.object_id = i.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'Sales'
      AND t.name = 'OrderLines'
      AND i.name = 'IX_Sales_OrderLines_Perf_20160301_01'
      AND i.is_disabled = 0
)
BEGIN
    ALTER INDEX [IX_Sales_OrderLines_Perf_20160301_01]
    ON [Sales].[OrderLines]
    DISABLE;
END
GO

-- Optional: for an even bigger effect, disable the nonclustered columnstore too.
-- Leave this ON only if you want the most dramatic demo.
IF EXISTS
(
    SELECT 1
    FROM sys.indexes i
    JOIN sys.tables t ON t.object_id = i.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'Sales'
      AND t.name = 'OrderLines'
      AND i.name = 'NCCX_Sales_OrderLines'
      AND i.is_disabled = 0
)
BEGIN
    ALTER INDEX [NCCX_Sales_OrderLines]
    ON [Sales].[OrderLines]
    DISABLE;
END
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