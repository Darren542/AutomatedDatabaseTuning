
USE [WideWorldImporters];
GO

/*
POC Compare Runs (v5)

Important:
- Assumes Query Store was cleared between baseline and compare runs
- Matches queries by workload tag if present, otherwise by normalized query text
- Shows totals, tagged groups, and top 10 most important queries
*/

SET NOCOUNT ON;
GO

DECLARE @BaselineRunID INT = 1;
DECLARE @CompareRunID INT = 2;

SELECT *
FROM dbo.POC_RunHistory
WHERE RunID IN (@BaselineRunID, @CompareRunID)
ORDER BY RunID;
GO

DECLARE @BaselineRunID2 INT = 1;
DECLARE @CompareRunID2 INT = 2;

;WITH Base AS
(
    SELECT
        RunID,
        QuerySqlText,
        ExecutionCount,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads,
        CASE
            WHEN CHARINDEX('/*', QuerySqlText) > 0
             AND CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) > CHARINDEX('/*', QuerySqlText)
            THEN LTRIM(RTRIM(SUBSTRING(
                    QuerySqlText,
                    CHARINDEX('/*', QuerySqlText) + 2,
                    CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) - CHARINDEX('/*', QuerySqlText) - 2
                 )))
            ELSE NULL
        END AS WorkloadTag,
        REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(QuerySqlText)), CHAR(13), ' '), CHAR(10), ' '), CHAR(9), ' ') AS NormalizedQueryText
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID IN (@BaselineRunID2, @CompareRunID2)
      AND QuerySqlText NOT LIKE 'CREATE%INDEX%'
      AND QuerySqlText NOT LIKE 'DROP INDEX%'
      AND QuerySqlText NOT LIKE 'ALTER INDEX%'
      AND QuerySqlText NOT LIKE '%CREATE NONCLUSTERED INDEX%'
      AND QuerySqlText NOT LIKE '%DROP INDEX%'
      AND QuerySqlText NOT LIKE '%ALTER INDEX%'
      AND QuerySqlText NOT LIKE '%sys.all_views%'
      AND QuerySqlText NOT LIKE '%sys.all_objects%'
      AND QuerySqlText NOT LIKE '%sys.tables AS tbl%'
      AND QuerySqlText NOT LIKE '%microsoft_database_tools_support%'
      AND QuerySqlText NOT LIKE '%TEMPORAL%'
      AND QuerySqlText NOT LIKE '%sys.extended_properties%'
      AND QuerySqlText NOT LIKE '%)DECLARE @%'
      AND QuerySqlText NOT LIKE 'DECLARE @%'
),
Prepared AS
(
    SELECT
        RunID,
        COALESCE(WorkloadTag, NormalizedQueryText) AS QueryKey,
        MIN(QuerySqlText) AS QueryPreview,
        MIN(WorkloadTag) AS WorkloadTag,
        SUM(ISNULL(ExecutionCount, 0)) AS ExecutionCount,
        SUM(CAST(ISNULL(TotalDurationMs, 0) AS DECIMAL(18,4))) AS TotalDurationMs,
        SUM(CAST(ISNULL(TotalCpuMs, 0) AS DECIMAL(18,4))) AS TotalCpuMs,
        SUM(CAST(ISNULL(TotalLogicalIoReads, 0) AS DECIMAL(18,4))) AS TotalLogicalIoReads
    FROM Base
    GROUP BY RunID, COALESCE(WorkloadTag, NormalizedQueryText)
),
Baseline AS
(
    SELECT * FROM Prepared WHERE RunID = @BaselineRunID2
),
CompareRun AS
(
    SELECT * FROM Prepared WHERE RunID = @CompareRunID2
)
SELECT
    SUM(ISNULL(b.TotalDurationMs, 0)) AS BaselineTotalDurationMs,
    SUM(ISNULL(c.TotalDurationMs, 0)) AS CompareTotalDurationMs,
    CASE
        WHEN SUM(ISNULL(b.TotalDurationMs, 0)) = 0 THEN NULL
        ELSE ((SUM(ISNULL(c.TotalDurationMs, 0)) - SUM(ISNULL(b.TotalDurationMs, 0))) / SUM(ISNULL(b.TotalDurationMs, 0))) * 100.0
    END AS TotalDurationPctChange,
    SUM(ISNULL(b.TotalCpuMs, 0)) AS BaselineTotalCpuMs,
    SUM(ISNULL(c.TotalCpuMs, 0)) AS CompareTotalCpuMs,
    CASE
        WHEN SUM(ISNULL(b.TotalCpuMs, 0)) = 0 THEN NULL
        ELSE ((SUM(ISNULL(c.TotalCpuMs, 0)) - SUM(ISNULL(b.TotalCpuMs, 0))) / SUM(ISNULL(b.TotalCpuMs, 0))) * 100.0
    END AS TotalCpuPctChange,
    SUM(ISNULL(b.TotalLogicalIoReads, 0)) AS BaselineTotalLogicalIoReads,
    SUM(ISNULL(c.TotalLogicalIoReads, 0)) AS CompareTotalLogicalIoReads,
    CASE
        WHEN SUM(ISNULL(b.TotalLogicalIoReads, 0)) = 0 THEN NULL
        ELSE ((SUM(ISNULL(c.TotalLogicalIoReads, 0)) - SUM(ISNULL(b.TotalLogicalIoReads, 0))) / SUM(ISNULL(b.TotalLogicalIoReads, 0))) * 100.0
    END AS TotalLogicalReadsPctChange,
    SUM(ISNULL(b.ExecutionCount, 0)) AS BaselineExecutionCount,
    SUM(ISNULL(c.ExecutionCount, 0)) AS CompareExecutionCount,
    CASE
        WHEN SUM(ISNULL(b.ExecutionCount, 0)) = 0 THEN NULL
        ELSE ((SUM(ISNULL(c.ExecutionCount, 0)) - SUM(ISNULL(b.ExecutionCount, 0))) / CONVERT(DECIMAL(18,4), SUM(ISNULL(b.ExecutionCount, 0)))) * 100.0
    END AS ExecutionCountPctChange
FROM Baseline AS b
FULL OUTER JOIN CompareRun AS c
    ON b.QueryKey = c.QueryKey;
GO

DECLARE @BaselineRunID3 INT = 1;
DECLARE @CompareRunID3 INT = 2;

;WITH Base AS
(
    SELECT
        RunID,
        QuerySqlText,
        ExecutionCount,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads,
        CASE
            WHEN CHARINDEX('/*', QuerySqlText) > 0
             AND CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) > CHARINDEX('/*', QuerySqlText)
            THEN LTRIM(RTRIM(SUBSTRING(
                    QuerySqlText,
                    CHARINDEX('/*', QuerySqlText) + 2,
                    CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) - CHARINDEX('/*', QuerySqlText) - 2
                 )))
            ELSE NULL
        END AS WorkloadTag
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID IN (@BaselineRunID3, @CompareRunID3)
      AND QuerySqlText LIKE '%/* % */%'
      AND QuerySqlText NOT LIKE '%)DECLARE @%'
      AND QuerySqlText NOT LIKE 'DECLARE @%'
),
Grouped AS
(
    SELECT
        RunID,
        WorkloadTag,
        SUM(ISNULL(ExecutionCount, 0)) AS ExecutionCount,
        SUM(CAST(ISNULL(TotalDurationMs, 0) AS DECIMAL(18,4))) AS TotalDurationMs,
        SUM(CAST(ISNULL(TotalCpuMs, 0) AS DECIMAL(18,4))) AS TotalCpuMs,
        SUM(CAST(ISNULL(TotalLogicalIoReads, 0) AS DECIMAL(18,4))) AS TotalLogicalIoReads
    FROM Base
    WHERE WorkloadTag IS NOT NULL
    GROUP BY RunID, WorkloadTag
),
Baseline AS
(
    SELECT * FROM Grouped WHERE RunID = @BaselineRunID3
),
CompareRun AS
(
    SELECT * FROM Grouped WHERE RunID = @CompareRunID3
)
SELECT
    COALESCE(b.WorkloadTag, c.WorkloadTag) AS WorkloadTag,
    b.ExecutionCount AS BaselineExecutionCount,
    c.ExecutionCount AS CompareExecutionCount,
    b.TotalDurationMs AS BaselineTotalDurationMs,
    c.TotalDurationMs AS CompareTotalDurationMs,
    CASE
        WHEN b.TotalDurationMs IS NULL OR b.TotalDurationMs = 0 OR c.TotalDurationMs IS NULL THEN NULL
        ELSE ((c.TotalDurationMs - b.TotalDurationMs) / b.TotalDurationMs) * 100.0
    END AS TotalDurationPctChange,
    b.TotalCpuMs AS BaselineTotalCpuMs,
    c.TotalCpuMs AS CompareTotalCpuMs,
    CASE
        WHEN b.TotalCpuMs IS NULL OR b.TotalCpuMs = 0 OR c.TotalCpuMs IS NULL THEN NULL
        ELSE ((c.TotalCpuMs - b.TotalCpuMs) / b.TotalCpuMs) * 100.0
    END AS TotalCpuPctChange,
    b.TotalLogicalIoReads AS BaselineTotalLogicalIoReads,
    c.TotalLogicalIoReads AS CompareTotalLogicalIoReads,
    CASE
        WHEN b.TotalLogicalIoReads IS NULL OR b.TotalLogicalIoReads = 0 OR c.TotalLogicalIoReads IS NULL THEN NULL
        ELSE ((c.TotalLogicalIoReads - b.TotalLogicalIoReads) / b.TotalLogicalIoReads) * 100.0
    END AS TotalLogicalReadsPctChange
FROM Baseline AS b
FULL OUTER JOIN CompareRun AS c
    ON b.WorkloadTag = c.WorkloadTag
ORDER BY COALESCE(b.WorkloadTag, c.WorkloadTag);
GO

DECLARE @BaselineRunID4 INT = 1;
DECLARE @CompareRunID4 INT = 2;

;WITH Base AS
(
    SELECT
        RunID,
        QuerySqlText,
        ExecutionCount,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads,
        CASE
            WHEN CHARINDEX('/*', QuerySqlText) > 0
             AND CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) > CHARINDEX('/*', QuerySqlText)
            THEN LTRIM(RTRIM(SUBSTRING(
                    QuerySqlText,
                    CHARINDEX('/*', QuerySqlText) + 2,
                    CHARINDEX('*/', QuerySqlText, CHARINDEX('/*', QuerySqlText) + 2) - CHARINDEX('/*', QuerySqlText) - 2
                 )))
            ELSE NULL
        END AS WorkloadTag,
        REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(QuerySqlText)), CHAR(13), ' '), CHAR(10), ' '), CHAR(9), ' ') AS NormalizedQueryText
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID IN (@BaselineRunID4, @CompareRunID4)
      AND QuerySqlText NOT LIKE 'CREATE%INDEX%'
      AND QuerySqlText NOT LIKE 'DROP INDEX%'
      AND QuerySqlText NOT LIKE 'ALTER INDEX%'
      AND QuerySqlText NOT LIKE '%CREATE NONCLUSTERED INDEX%'
      AND QuerySqlText NOT LIKE '%DROP INDEX%'
      AND QuerySqlText NOT LIKE '%ALTER INDEX%'
      AND QuerySqlText NOT LIKE '%sys.all_views%'
      AND QuerySqlText NOT LIKE '%sys.all_objects%'
      AND QuerySqlText NOT LIKE '%sys.tables AS tbl%'
      AND QuerySqlText NOT LIKE '%microsoft_database_tools_support%'
      AND QuerySqlText NOT LIKE '%TEMPORAL%'
      AND QuerySqlText NOT LIKE '%sys.extended_properties%'
      AND QuerySqlText NOT LIKE '%)DECLARE @%'
      AND QuerySqlText NOT LIKE 'DECLARE @%'
),
Prepared AS
(
    SELECT
        RunID,
        COALESCE(WorkloadTag, NormalizedQueryText) AS QueryKey,
        MIN(QuerySqlText) AS QueryPreview,
        SUM(ISNULL(ExecutionCount, 0)) AS ExecutionCount,
        SUM(CAST(ISNULL(TotalDurationMs, 0) AS DECIMAL(18,4))) AS TotalDurationMs,
        SUM(CAST(ISNULL(TotalCpuMs, 0) AS DECIMAL(18,4))) AS TotalCpuMs,
        SUM(CAST(ISNULL(TotalLogicalIoReads, 0) AS DECIMAL(18,4))) AS TotalLogicalIoReads
    FROM Base
    GROUP BY RunID, COALESCE(WorkloadTag, NormalizedQueryText)
),
Baseline AS
(
    SELECT * FROM Prepared WHERE RunID = @BaselineRunID4
),
CompareRun AS
(
    SELECT * FROM Prepared WHERE RunID = @CompareRunID4
)
SELECT TOP (10)
    COALESCE(b.QueryKey, c.QueryKey) AS QueryKey,
    LEFT(COALESCE(b.QueryPreview, c.QueryPreview), 4000) AS QueryPreview,
    b.ExecutionCount AS BaselineExecutionCount,
    c.ExecutionCount AS CompareExecutionCount,
    b.TotalDurationMs AS BaselineTotalDurationMs,
    c.TotalDurationMs AS CompareTotalDurationMs,
    CASE
        WHEN b.TotalDurationMs IS NULL OR b.TotalDurationMs = 0 OR c.TotalDurationMs IS NULL THEN NULL
        ELSE ((c.TotalDurationMs - b.TotalDurationMs) / b.TotalDurationMs) * 100.0
    END AS TotalDurationPctChange,
    b.TotalCpuMs AS BaselineTotalCpuMs,
    c.TotalCpuMs AS CompareTotalCpuMs,
    CASE
        WHEN b.TotalCpuMs IS NULL OR b.TotalCpuMs = 0 OR c.TotalCpuMs IS NULL THEN NULL
        ELSE ((c.TotalCpuMs - b.TotalCpuMs) / b.TotalCpuMs) * 100.0
    END AS TotalCpuPctChange,
    b.TotalLogicalIoReads AS BaselineTotalLogicalIoReads,
    c.TotalLogicalIoReads AS CompareTotalLogicalIoReads,
    CASE
        WHEN b.TotalLogicalIoReads IS NULL OR b.TotalLogicalIoReads = 0 OR c.TotalLogicalIoReads IS NULL THEN NULL
        ELSE ((c.TotalLogicalIoReads - b.TotalLogicalIoReads) / b.TotalLogicalIoReads) * 100.0
    END AS TotalLogicalReadsPctChange
FROM Baseline AS b
FULL OUTER JOIN CompareRun AS c
    ON b.QueryKey = c.QueryKey
ORDER BY COALESCE(b.TotalDurationMs, c.TotalDurationMs) DESC;
GO
