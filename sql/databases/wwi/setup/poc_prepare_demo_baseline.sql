
USE [WideWorldImporters];
GO

/*
POC Prepare Demo Baseline (drop-index version)

Purpose:
- Drop prior POC indexes (IX_POC_*)
- Clear POC snapshot tables
- Clear Query Store
- Drop selected WWI indexes so missing-index recommendations can surface clearly

Recommended location:
- sql/databases/wwi/setup/poc_prepare_demo_baseline.sql
*/

SET NOCOUNT ON;
GO

PRINT '=== Preparing WWI demo baseline (drop-index version) ===';

------------------------------------------------------------------------------
-- 1) Drop prior POC-created indexes
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
-- 2) Clear POC snapshot tables
------------------------------------------------------------------------------

IF OBJECT_ID('dbo.POC_QueryStoreSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_QueryStoreSnapshot;
IF OBJECT_ID('dbo.POC_MissingIndexSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_MissingIndexSnapshot;
IF OBJECT_ID('dbo.POC_IndexUsageSnapshot', 'U') IS NOT NULL DELETE FROM dbo.POC_IndexUsageSnapshot;
IF OBJECT_ID('dbo.POC_RunHistory', 'U') IS NOT NULL DELETE FROM dbo.POC_RunHistory;
GO

------------------------------------------------------------------------------
-- 3) Clear Query Store history for a clean baseline run
------------------------------------------------------------------------------

ALTER DATABASE CURRENT SET QUERY_STORE CLEAR ALL;
GO

------------------------------------------------------------------------------
-- 4) Drop selected WWI indexes for demo
------------------------------------------------------------------------------

IF EXISTS
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
    PRINT 'Dropping [Sales].[OrderLines].[IX_Sales_OrderLines_Perf_20160301_01]';
    DROP INDEX [IX_Sales_OrderLines_Perf_20160301_01] ON [Sales].[OrderLines];
END
ELSE
BEGIN
    PRINT 'Index IX_Sales_OrderLines_Perf_20160301_01 already absent.';
END
GO

IF EXISTS
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
    PRINT 'Dropping [Sales].[OrderLines].[NCCX_Sales_OrderLines]';
    DROP INDEX [NCCX_Sales_OrderLines] ON [Sales].[OrderLines];
END
ELSE
BEGIN
    PRINT 'Index NCCX_Sales_OrderLines already absent.';
END
GO

------------------------------------------------------------------------------
-- 5) Show current OrderLines indexes
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

PRINT '=== WWI demo baseline preparation complete ===';
GO
