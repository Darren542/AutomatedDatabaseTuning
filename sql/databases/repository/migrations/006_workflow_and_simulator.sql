/* Apply to the repository after 005. No monitored target is modified. */
USE [AutoTunerRepository];
GO
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF OBJECT_ID('dbo.RecommendationAnalysis','U') IS NULL
    THROW 50001, 'Apply migrations 001-005 first.', 1;
IF OBJECT_ID('dbo.CandidateSet','U') IS NULL
BEGIN
    CREATE TABLE dbo.CandidateSet (
        CandidateSetId uniqueidentifier NOT NULL PRIMARY KEY,
        TargetId uniqueidentifier NOT NULL REFERENCES dbo.TargetDatabase(TargetId),
        BatchId uniqueidentifier NOT NULL REFERENCES dbo.CollectionBatch(BatchId),
        MetadataBatchId uniqueidentifier NOT NULL REFERENCES dbo.CollectionBatch(BatchId),
        EngineVersion nvarchar(30) NOT NULL,
        InputHash char(64) NOT NULL,
        InputJson nvarchar(max) NOT NULL CHECK(ISJSON(InputJson)=1),
        ResultJson nvarchar(max) NOT NULL CHECK(ISJSON(ResultJson)=1),
        CreatedAtUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX IX_CandidateSet_TargetCreated ON dbo.CandidateSet(TargetId,CreatedAtUtc DESC);
END;
IF COL_LENGTH('dbo.RecommendationAnalysis','CandidateSetId') IS NULL
    ALTER TABLE dbo.RecommendationAnalysis ADD CandidateSetId uniqueidentifier NULL
        REFERENCES dbo.CandidateSet(CandidateSetId);
IF OBJECT_ID('dbo.WorkloadSimulation','U') IS NULL
BEGIN
    CREATE TABLE dbo.WorkloadSimulation (
        RunId uniqueidentifier NOT NULL PRIMARY KEY,
        TargetId uniqueidentifier NOT NULL REFERENCES dbo.TargetDatabase(TargetId),
        Status nvarchar(20) NOT NULL CHECK(Status IN ('Pending','Running','Stopping','Completed','Stopped','Failed','Interrupted')),
        ConfigJson nvarchar(max) NOT NULL CHECK(ISJSON(ConfigJson)=1),
        StatsJson nvarchar(max) NOT NULL CHECK(ISJSON(StatsJson)=1),
        CreatedAtUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX IX_WorkloadSimulation_TargetCreated ON dbo.WorkloadSimulation(TargetId,CreatedAtUtc DESC);
    CREATE TABLE dbo.WorkloadSimulationControl (
        ControlId bigint IDENTITY PRIMARY KEY,
        RunId uniqueidentifier NOT NULL REFERENCES dbo.WorkloadSimulation(RunId) ON DELETE CASCADE,
        PhaseJson nvarchar(max) NOT NULL CHECK(ISJSON(PhaseJson)=1),
        CreatedAtUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
COMMIT;
GO
