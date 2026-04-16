USE [WideWorldImporters];
GO

/*
POC Compare Runs

Purpose:
- Compare two captured runs from:
  dbo.POC_RunHistory
  dbo.POC_QueryStoreSnapshot
  dbo.POC_MissingIndexSnapshot
  dbo.POC_IndexUsageSnapshot

How to use:
- Set @BaselineRunID and @CompareRunID
- Set @ExcludeSSMSNoise = 1 to filter common SSMS metadata/object explorer queries
*/

SET NOCOUNT ON;
GO

DECLARE @BaselineRunID INT = 1;
DECLARE @CompareRunID INT = 2;
DECLARE @ExcludeSSMSNoise BIT = 1;

------------------------------------------------------------------------------
-- 1) Show the two runs being compared
------------------------------------------------------------------------------

SELECT *
FROM dbo.POC_RunHistory
WHERE RunID IN (@BaselineRunID, @CompareRunID)
ORDER BY RunID;

------------------------------------------------------------------------------
-- 2) Query-level comparison
--    Join by QuerySqlText because QueryId/PlanId can vary across captures.
------------------------------------------------------------------------------

;WITH Baseline AS
(
    SELECT
        QuerySqlText,
        ExecutionCount,
        AvgDurationMs,
        AvgCpuMs,
        AvgLogicalIoReads,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads,
        LastExecutionTime
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID = @BaselineRunID
),
CompareRun AS
(
    SELECT
        QuerySqlText,
        ExecutionCount,
        AvgDurationMs,
        AvgCpuMs,
        AvgLogicalIoReads,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads,
        LastExecutionTime
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID = @CompareRunID
),
Joined AS
(
    SELECT
        COALESCE(b.QuerySqlText, c.QuerySqlText) AS QuerySqlText,

        b.ExecutionCount AS BaselineExecutionCount,
        b.AvgDurationMs AS BaselineAvgDurationMs,
        b.AvgCpuMs AS BaselineAvgCpuMs,
        b.AvgLogicalIoReads AS BaselineAvgLogicalIoReads,
        b.TotalDurationMs AS BaselineTotalDurationMs,
        b.TotalCpuMs AS BaselineTotalCpuMs,
        b.TotalLogicalIoReads AS BaselineTotalLogicalIoReads,

        c.ExecutionCount AS CompareExecutionCount,
        c.AvgDurationMs AS CompareAvgDurationMs,
        c.AvgCpuMs AS CompareAvgCpuMs,
        c.AvgLogicalIoReads AS CompareAvgLogicalIoReads,
        c.TotalDurationMs AS CompareTotalDurationMs,
        c.TotalCpuMs AS CompareTotalCpuMs,
        c.TotalLogicalIoReads AS CompareTotalLogicalIoReads
    FROM Baseline AS b
    FULL OUTER JOIN CompareRun AS c
        ON b.QuerySqlText = c.QuerySqlText
),
Filtered AS
(
    SELECT *
    FROM Joined
    WHERE
        (
            @ExcludeSSMSNoise = 0
            OR
            (
                QuerySqlText NOT LIKE '%sys.all_views%'
                AND QuerySqlText NOT LIKE '%sys.all_objects%'
                AND QuerySqlText NOT LIKE '%sys.tables AS tbl%'
                AND QuerySqlText NOT LIKE '%microsoft_database_tools_support%'
                AND QuerySqlText NOT LIKE '%TEMPORAL%'
            )
        )
)
SELECT TOP (50)
    LEFT(QuerySqlText, 4000) AS QueryPreview,

    BaselineExecutionCount,
    CompareExecutionCount,

    BaselineAvgDurationMs,
    CompareAvgDurationMs,
    CASE
        WHEN BaselineAvgDurationMs IS NULL OR BaselineAvgDurationMs = 0 OR CompareAvgDurationMs IS NULL THEN NULL
        ELSE ((CompareAvgDurationMs - BaselineAvgDurationMs) / BaselineAvgDurationMs) * 100.0
    END AS AvgDurationPctChange,

    BaselineAvgCpuMs,
    CompareAvgCpuMs,
    CASE
        WHEN BaselineAvgCpuMs IS NULL OR BaselineAvgCpuMs = 0 OR CompareAvgCpuMs IS NULL THEN NULL
        ELSE ((CompareAvgCpuMs - BaselineAvgCpuMs) / BaselineAvgCpuMs) * 100.0
    END AS AvgCpuPctChange,

    BaselineAvgLogicalIoReads,
    CompareAvgLogicalIoReads,
    CASE
        WHEN BaselineAvgLogicalIoReads IS NULL OR BaselineAvgLogicalIoReads = 0 OR CompareAvgLogicalIoReads IS NULL THEN NULL
        ELSE ((CompareAvgLogicalIoReads - BaselineAvgLogicalIoReads) / BaselineAvgLogicalIoReads) * 100.0
    END AS AvgLogicalReadsPctChange,

    BaselineTotalDurationMs,
    CompareTotalDurationMs
FROM Filtered
ORDER BY
    CASE
        WHEN BaselineTotalDurationMs IS NULL THEN CompareTotalDurationMs
        ELSE BaselineTotalDurationMs
    END DESC;
GO

------------------------------------------------------------------------------
-- 3) Summary totals across matched workload queries
------------------------------------------------------------------------------

DECLARE @BaselineRunID2 INT = 1;
DECLARE @CompareRunID2 INT = 2;
DECLARE @ExcludeSSMSNoise2 BIT = 1;

;WITH Baseline AS
(
    SELECT
        QuerySqlText,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID = @BaselineRunID2
),
CompareRun AS
(
    SELECT
        QuerySqlText,
        TotalDurationMs,
        TotalCpuMs,
        TotalLogicalIoReads
    FROM dbo.POC_QueryStoreSnapshot
    WHERE RunID = @CompareRunID2
),
Joined AS
(
    SELECT
        COALESCE(b.QuerySqlText, c.QuerySqlText) AS QuerySqlText,
        ISNULL(b.TotalDurationMs, 0) AS BaselineTotalDurationMs,
        ISNULL(b.TotalCpuMs, 0) AS BaselineTotalCpuMs,
        ISNULL(b.TotalLogicalIoReads, 0) AS BaselineTotalLogicalIoReads,
        ISNULL(c.TotalDurationMs, 0) AS CompareTotalDurationMs,
        ISNULL(c.TotalCpuMs, 0) AS CompareTotalCpuMs,
        ISNULL(c.TotalLogicalIoReads, 0) AS CompareTotalLogicalIoReads
    FROM Baseline AS b
    FULL OUTER JOIN CompareRun AS c
        ON b.QuerySqlText = c.QuerySqlText
),
Filtered AS
(
    SELECT *
    FROM Joined
    WHERE
        (
            @ExcludeSSMSNoise2 = 0
            OR
            (
                QuerySqlText NOT LIKE '%sys.all_views%'
                AND QuerySqlText NOT LIKE '%sys.all_objects%'
                AND QuerySqlText NOT LIKE '%sys.tables AS tbl%'
                AND QuerySqlText NOT LIKE '%microsoft_database_tools_support%'
                AND QuerySqlText NOT LIKE '%TEMPORAL%'
            )
        )
)
SELECT
    SUM(BaselineTotalDurationMs) AS BaselineTotalDurationMs,
    SUM(CompareTotalDurationMs) AS CompareTotalDurationMs,
    CASE
        WHEN SUM(BaselineTotalDurationMs) = 0 THEN NULL
        ELSE ((SUM(CompareTotalDurationMs) - SUM(BaselineTotalDurationMs)) / SUM(BaselineTotalDurationMs)) * 100.0
    END AS TotalDurationPctChange,

    SUM(BaselineTotalCpuMs) AS BaselineTotalCpuMs,
    SUM(CompareTotalCpuMs) AS CompareTotalCpuMs,
    CASE
        WHEN SUM(BaselineTotalCpuMs) = 0 THEN NULL
        ELSE ((SUM(CompareTotalCpuMs) - SUM(BaselineTotalCpuMs)) / SUM(BaselineTotalCpuMs)) * 100.0
    END AS TotalCpuPctChange,

    SUM(BaselineTotalLogicalIoReads) AS BaselineTotalLogicalIoReads,
    SUM(CompareTotalLogicalIoReads) AS CompareTotalLogicalIoReads,
    CASE
        WHEN SUM(BaselineTotalLogicalIoReads) = 0 THEN NULL
        ELSE ((SUM(CompareTotalLogicalIoReads) - SUM(BaselineTotalLogicalIoReads)) / SUM(BaselineTotalLogicalIoReads)) * 100.0
    END AS TotalLogicalReadsPctChange
FROM Filtered;
GO

------------------------------------------------------------------------------
-- 4) Missing-index comparison
------------------------------------------------------------------------------

DECLARE @BaselineRunID3 INT = 1;
DECLARE @CompareRunID3 INT = 2;

;WITH Baseline AS
(
    SELECT
        SchemaName,
        TableName,
        EqualityColumns,
        InequalityColumns,
        IncludedColumns,
        ImprovementMeasure
    FROM dbo.POC_MissingIndexSnapshot
    WHERE RunID = @BaselineRunID3
),
CompareRun AS
(
    SELECT
        SchemaName,
        TableName,
        EqualityColumns,
        InequalityColumns,
        IncludedColumns,
        ImprovementMeasure
    FROM dbo.POC_MissingIndexSnapshot
    WHERE RunID = @CompareRunID3
)
SELECT
    COALESCE(b.SchemaName, c.SchemaName) AS SchemaName,
    COALESCE(b.TableName, c.TableName) AS TableName,
    COALESCE(b.EqualityColumns, c.EqualityColumns) AS EqualityColumns,
    COALESCE(b.InequalityColumns, c.InequalityColumns) AS InequalityColumns,
    COALESCE(b.IncludedColumns, c.IncludedColumns) AS IncludedColumns,
    b.ImprovementMeasure AS BaselineImprovementMeasure,
    c.ImprovementMeasure AS CompareImprovementMeasure,
    CASE
        WHEN b.ImprovementMeasure IS NULL OR b.ImprovementMeasure = 0 OR c.ImprovementMeasure IS NULL THEN NULL
        ELSE ((c.ImprovementMeasure - b.ImprovementMeasure) / b.ImprovementMeasure) * 100.0
    END AS ImprovementMeasurePctChange
FROM Baseline AS b
FULL OUTER JOIN CompareRun AS c
    ON ISNULL(b.SchemaName, '') = ISNULL(c.SchemaName, '')
   AND ISNULL(b.TableName, '') = ISNULL(c.TableName, '')
   AND ISNULL(b.EqualityColumns, '') = ISNULL(c.EqualityColumns, '')
   AND ISNULL(b.InequalityColumns, '') = ISNULL(c.InequalityColumns, '')
   AND ISNULL(b.IncludedColumns, '') = ISNULL(c.IncludedColumns, '')
ORDER BY COALESCE(c.ImprovementMeasure, b.ImprovementMeasure) DESC;
GO

------------------------------------------------------------------------------
-- 5) Index usage comparison
------------------------------------------------------------------------------

DECLARE @BaselineRunID4 INT = 1;
DECLARE @CompareRunID4 INT = 2;

;WITH Baseline AS
(
    SELECT
        SchemaName,
        TableName,
        IndexName,
        IndexTypeDesc,
        UserSeeks,
        UserScans,
        UserLookups,
        UserUpdates
    FROM dbo.POC_IndexUsageSnapshot
    WHERE RunID = @BaselineRunID4
),
CompareRun AS
(
    SELECT
        SchemaName,
        TableName,
        IndexName,
        IndexTypeDesc,
        UserSeeks,
        UserScans,
        UserLookups,
        UserUpdates
    FROM dbo.POC_IndexUsageSnapshot
    WHERE RunID = @CompareRunID4
)
SELECT
    COALESCE(b.SchemaName, c.SchemaName) AS SchemaName,
    COALESCE(b.TableName, c.TableName) AS TableName,
    COALESCE(b.IndexName, c.IndexName) AS IndexName,
    COALESCE(b.IndexTypeDesc, c.IndexTypeDesc) AS IndexTypeDesc,

    b.UserSeeks AS BaselineUserSeeks,
    c.UserSeeks AS CompareUserSeeks,
    b.UserScans AS BaselineUserScans,
    c.UserScans AS CompareUserScans,
    b.UserLookups AS BaselineUserLookups,
    c.UserLookups AS CompareUserLookups,
    b.UserUpdates AS BaselineUserUpdates,
    c.UserUpdates AS CompareUserUpdates
FROM Baseline AS b
FULL OUTER JOIN CompareRun AS c
    ON ISNULL(b.SchemaName, '') = ISNULL(c.SchemaName, '')
   AND ISNULL(b.TableName, '') = ISNULL(c.TableName, '')
   AND ISNULL(b.IndexName, '') = ISNULL(c.IndexName, '')
ORDER BY
    COALESCE(c.UserSeeks, b.UserSeeks, 0) DESC,
    COALESCE(c.UserScans, b.UserScans, 0) DESC;
GO