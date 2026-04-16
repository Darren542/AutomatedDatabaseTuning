
USE [WideWorldImporters];
GO

/*
POC Baseline Capture (v5)

This version still accepts exact windows, but for the simplified demo
the runner will clear Query Store between baseline and compare runs.
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID('dbo.POC_RunHistory', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.POC_RunHistory
    (
        RunID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RunLabel NVARCHAR(200) NOT NULL,
        WorkloadType NVARCHAR(50) NULL,
        Notes NVARCHAR(500) NULL,
        CapturedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        WindowStart DATETIME2 NULL,
        WindowEnd DATETIME2 NULL
    );
END;
GO

IF OBJECT_ID('dbo.POC_QueryStoreSnapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.POC_QueryStoreSnapshot
    (
        SnapshotID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RunID INT NOT NULL,
        QueryId BIGINT NOT NULL,
        PlanId BIGINT NOT NULL,
        QuerySqlText NVARCHAR(MAX) NULL,
        ExecutionTypeDesc NVARCHAR(60) NULL,
        ExecutionCount BIGINT NULL,
        AvgDurationMs DECIMAL(18,2) NULL,
        AvgCpuMs DECIMAL(18,2) NULL,
        AvgLogicalIoReads DECIMAL(18,2) NULL,
        AvgRowCount DECIMAL(18,2) NULL,
        TotalDurationMs DECIMAL(18,2) NULL,
        TotalCpuMs DECIMAL(18,2) NULL,
        TotalLogicalIoReads DECIMAL(18,2) NULL,
        LastExecutionTime DATETIME2 NULL,
        CONSTRAINT FK_POC_QueryStoreSnapshot_Run FOREIGN KEY (RunID) REFERENCES dbo.POC_RunHistory(RunID)
    );
END;
GO

IF OBJECT_ID('dbo.POC_MissingIndexSnapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.POC_MissingIndexSnapshot
    (
        SnapshotID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RunID INT NOT NULL,
        DatabaseName SYSNAME NULL,
        SchemaName SYSNAME NULL,
        TableName SYSNAME NULL,
        EqualityColumns NVARCHAR(MAX) NULL,
        InequalityColumns NVARCHAR(MAX) NULL,
        IncludedColumns NVARCHAR(MAX) NULL,
        UserSeeks BIGINT NULL,
        UserScans BIGINT NULL,
        AvgTotalUserCost FLOAT NULL,
        AvgUserImpact FLOAT NULL,
        ImprovementMeasure FLOAT NULL,
        CONSTRAINT FK_POC_MissingIndexSnapshot_Run FOREIGN KEY (RunID) REFERENCES dbo.POC_RunHistory(RunID)
    );
END;
GO

IF OBJECT_ID('dbo.POC_IndexUsageSnapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.POC_IndexUsageSnapshot
    (
        SnapshotID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RunID INT NOT NULL,
        SchemaName SYSNAME NULL,
        TableName SYSNAME NULL,
        IndexName SYSNAME NULL,
        IndexTypeDesc NVARCHAR(60) NULL,
        UserSeeks BIGINT NULL,
        UserScans BIGINT NULL,
        UserLookups BIGINT NULL,
        UserUpdates BIGINT NULL,
        LastUserSeek DATETIME NULL,
        LastUserScan DATETIME NULL,
        LastUserLookup DATETIME NULL,
        LastUserUpdate DATETIME NULL,
        CONSTRAINT FK_POC_IndexUsageSnapshot_Run FOREIGN KEY (RunID) REFERENCES dbo.POC_RunHistory(RunID)
    );
END;
GO

DECLARE @RunLabel NVARCHAR(200) = N'Baseline - Python POC';
DECLARE @WorkloadType NVARCHAR(50) = N'read';
DECLARE @Notes NVARCHAR(500) = N'Captured by Python runner';
DECLARE @LookbackMinutes INT = 10;
DECLARE @WindowStart DATETIME2 = NULL;
DECLARE @WindowEnd DATETIME2 = NULL;

IF @WindowStart IS NULL OR @WindowEnd IS NULL
BEGIN
    SET @WindowEnd = SYSUTCDATETIME();
    SET @WindowStart = DATEADD(MINUTE, -@LookbackMinutes, @WindowEnd);
END;

DECLARE @RunID INT;

INSERT INTO dbo.POC_RunHistory
(
    RunLabel, WorkloadType, Notes, CapturedAt, WindowStart, WindowEnd
)
VALUES
(
    @RunLabel, @WorkloadType, @Notes, SYSUTCDATETIME(), @WindowStart, @WindowEnd
);

SET @RunID = SCOPE_IDENTITY();

;WITH QueryStoreWindow AS
(
    SELECT
        q.query_id,
        p.plan_id,
        qt.query_sql_text,
        rs.execution_type_desc,
        SUM(CAST(rs.count_executions AS BIGINT)) AS execution_count,
        AVG(CAST(rs.avg_duration / 1000.0 AS DECIMAL(18,2))) AS avg_duration_ms,
        AVG(CAST(rs.avg_cpu_time / 1000.0 AS DECIMAL(18,2))) AS avg_cpu_ms,
        AVG(CAST(rs.avg_logical_io_reads AS DECIMAL(18,2))) AS avg_logical_io_reads,
        AVG(CAST(rs.avg_rowcount AS DECIMAL(18,2))) AS avg_row_count,
        SUM(CAST((rs.avg_duration * rs.count_executions) / 1000.0 AS DECIMAL(18,2))) AS total_duration_ms,
        SUM(CAST((rs.avg_cpu_time * rs.count_executions) / 1000.0 AS DECIMAL(18,2))) AS total_cpu_ms,
        SUM(CAST(rs.avg_logical_io_reads * rs.count_executions AS DECIMAL(18,2))) AS total_logical_io_reads,
        MAX(rs.last_execution_time) AS last_execution_time
    FROM sys.query_store_runtime_stats AS rs
    INNER JOIN sys.query_store_plan AS p ON p.plan_id = rs.plan_id
    INNER JOIN sys.query_store_query AS q ON q.query_id = p.query_id
    INNER JOIN sys.query_store_query_text AS qt ON qt.query_text_id = q.query_text_id
    WHERE rs.last_execution_time >= @WindowStart
      AND rs.last_execution_time <= @WindowEnd
    GROUP BY q.query_id, p.plan_id, qt.query_sql_text, rs.execution_type_desc
)
INSERT INTO dbo.POC_QueryStoreSnapshot
(
    RunID, QueryId, PlanId, QuerySqlText, ExecutionTypeDesc, ExecutionCount,
    AvgDurationMs, AvgCpuMs, AvgLogicalIoReads, AvgRowCount,
    TotalDurationMs, TotalCpuMs, TotalLogicalIoReads, LastExecutionTime
)
SELECT TOP (200)
    @RunID, query_id, plan_id, query_sql_text, execution_type_desc, execution_count,
    avg_duration_ms, avg_cpu_ms, avg_logical_io_reads, avg_row_count,
    total_duration_ms, total_cpu_ms, total_logical_io_reads, last_execution_time
FROM QueryStoreWindow
ORDER BY total_duration_ms DESC, total_cpu_ms DESC;

INSERT INTO dbo.POC_MissingIndexSnapshot
(
    RunID, DatabaseName, SchemaName, TableName,
    EqualityColumns, InequalityColumns, IncludedColumns,
    UserSeeks, UserScans, AvgTotalUserCost, AvgUserImpact, ImprovementMeasure
)
SELECT
    @RunID,
    DB_NAME(mid.database_id),
    OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id),
    OBJECT_NAME(mid.object_id, mid.database_id),
    mid.equality_columns,
    mid.inequality_columns,
    mid.included_columns,
    migs.user_seeks,
    migs.user_scans,
    migs.avg_total_user_cost,
    migs.avg_user_impact,
    (migs.avg_total_user_cost * migs.avg_user_impact * (migs.user_seeks + migs.user_scans))
FROM sys.dm_db_missing_index_group_stats AS migs
INNER JOIN sys.dm_db_missing_index_groups AS mig
    ON migs.group_handle = mig.index_group_handle
INNER JOIN sys.dm_db_missing_index_details AS mid
    ON mig.index_handle = mid.index_handle
WHERE mid.database_id = DB_ID();

INSERT INTO dbo.POC_IndexUsageSnapshot
(
    RunID, SchemaName, TableName, IndexName, IndexTypeDesc,
    UserSeeks, UserScans, UserLookups, UserUpdates,
    LastUserSeek, LastUserScan, LastUserLookup, LastUserUpdate
)
SELECT
    @RunID,
    s.name,
    o.name,
    i.name,
    i.type_desc,
    ius.user_seeks,
    ius.user_scans,
    ius.user_lookups,
    ius.user_updates,
    ius.last_user_seek,
    ius.last_user_scan,
    ius.last_user_lookup,
    ius.last_user_update
FROM sys.dm_db_index_usage_stats AS ius
INNER JOIN sys.indexes AS i
    ON i.object_id = ius.object_id
   AND i.index_id = ius.index_id
INNER JOIN sys.objects AS o
    ON o.object_id = i.object_id
INNER JOIN sys.schemas AS s
    ON s.schema_id = o.schema_id
WHERE ius.database_id = DB_ID()
  AND o.type = 'U';

SELECT *
FROM dbo.POC_RunHistory
WHERE RunID = @RunID;

SELECT TOP (20)
    QueryId,
    PlanId,
    ExecutionCount,
    AvgDurationMs,
    AvgCpuMs,
    AvgLogicalIoReads,
    TotalDurationMs,
    TotalCpuMs,
    TotalLogicalIoReads,
    LastExecutionTime,
    LEFT(QuerySqlText, 4000) AS QueryPreview
FROM dbo.POC_QueryStoreSnapshot
WHERE RunID = @RunID
ORDER BY TotalDurationMs DESC, TotalCpuMs DESC;

SELECT TOP (20)
    SchemaName,
    TableName,
    EqualityColumns,
    InequalityColumns,
    IncludedColumns,
    UserSeeks,
    UserScans,
    AvgTotalUserCost,
    AvgUserImpact,
    ImprovementMeasure
FROM dbo.POC_MissingIndexSnapshot
WHERE RunID = @RunID
ORDER BY ImprovementMeasure DESC;

SELECT TOP (20)
    SchemaName,
    TableName,
    IndexName,
    IndexTypeDesc,
    UserSeeks,
    UserScans,
    UserLookups,
    UserUpdates,
    LastUserUpdate
FROM dbo.POC_IndexUsageSnapshot
WHERE RunID = @RunID
ORDER BY UserUpdates DESC, UserSeeks DESC, UserScans DESC;
GO
