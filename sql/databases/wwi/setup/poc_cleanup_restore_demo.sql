
USE [WideWorldImporters];
GO

/*
POC Cleanup / Restore Demo (drop-index version)

Purpose:
- Recreate dropped WWI indexes used in the demo
- Drop IX_POC_* indexes
- Optionally clear POC tables / Query Store if wanted later

Recommended location:
- sql/databases/wwi/setup/poc_cleanup_restore_demo.sql
*/

SET NOCOUNT ON;
GO

PRINT '=== Restoring WWI demo indexes ===';

------------------------------------------------------------------------------
-- 1) Recreate IX_Sales_OrderLines_Perf_20160301_01 if missing
------------------------------------------------------------------------------

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes i
    INNER JOIN sys.tables t ON t.object_id = i.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = N'Sales'
      AND t.name = N'OrderLines'
      AND i.name = N'IX_Sales_OrderLines_Perf_20160301_01'
)
BEGIN
    PRINT 'Recreating IX_Sales_OrderLines_Perf_20160301_01';
    CREATE NONCLUSTERED INDEX [IX_Sales_OrderLines_Perf_20160301_01]
    ON [Sales].[OrderLines] ([PickingCompletedWhen], [OrderID], [OrderLineID])
    INCLUDE ([StockItemID], [Quantity]);
END
ELSE
BEGIN
    PRINT 'IX_Sales_OrderLines_Perf_20160301_01 already exists.';
END
GO

------------------------------------------------------------------------------
-- 2) Recreate NCCX_Sales_OrderLines if missing
------------------------------------------------------------------------------

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes i
    INNER JOIN sys.tables t ON t.object_id = i.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = N'Sales'
      AND t.name = N'OrderLines'
      AND i.name = N'NCCX_Sales_OrderLines'
)
BEGIN
    PRINT 'Recreating NCCX_Sales_OrderLines';
    CREATE NONCLUSTERED COLUMNSTORE INDEX [NCCX_Sales_OrderLines]
    ON [Sales].[OrderLines]
    (
        [OrderID],
        [StockItemID],
        [Description],
        [Quantity],
        [UnitPrice],
        [PickedQuantity]
    );
END
ELSE
BEGIN
    PRINT 'NCCX_Sales_OrderLines already exists.';
END
GO

------------------------------------------------------------------------------
-- 3) Drop IX_POC_* indexes if they exist
------------------------------------------------------------------------------

DECLARE @DropPocSql NVARCHAR(MAX) = N'';

SELECT @DropPocSql = @DropPocSql +
    N'DROP INDEX [' + i.name + N'] ON [' + s.name + N'].[' + t.name + N'];' + CHAR(13) + CHAR(10)
FROM sys.indexes AS i
INNER JOIN sys.tables AS t ON t.object_id = i.object_id
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE i.name LIKE N'IX_POC[_]%'
  AND i.index_id > 0
  AND i.is_hypothetical = 0;

IF @DropPocSql <> N''
BEGIN
    PRINT 'Dropping IX_POC_* indexes...';
    EXEC sp_executesql @DropPocSql;
END
ELSE
BEGIN
    PRINT 'No IX_POC_* indexes found.';
END
GO

------------------------------------------------------------------------------
-- 4) Show current OrderLines indexes
------------------------------------------------------------------------------

SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    i.name AS IndexName,
    i.type_desc,
    i.is_disabled
FROM sys.indexes AS i
INNER JOIN sys.tables AS t ON t.object_id = i.object_id
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'Sales'
  AND t.name = N'OrderLines'
ORDER BY i.name;
GO

PRINT '=== WWI demo cleanup / restore complete ===';
GO
