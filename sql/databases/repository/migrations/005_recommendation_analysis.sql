/* Sprint 2: immutable, provenance-linked analyses. Run after migrations 001-004.
   This migration writes only AutoTunerRepository. No target tuning DDL is run.
   Review/apply in SSMS before starting the Sprint 2 API.
*/
USE [AutoTunerRepository];
GO
SET XACT_ABORT ON;
GO
BEGIN TRY
    BEGIN TRANSACTION;
    IF OBJECT_ID(N'dbo.CollectionBatch', N'U') IS NULL
        THROW 50001, 'Apply repository migrations 001-004 first.', 1;
    IF OBJECT_ID(N'dbo.RecommendationAnalysis', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.RecommendationAnalysis
        (
            AnalysisId UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
            TargetId UNIQUEIDENTIFIER NOT NULL,
            BatchId UNIQUEIDENTIFIER NOT NULL,
            MetadataBatchId UNIQUEIDENTIFIER NOT NULL,
            EngineVersion NVARCHAR(30) NOT NULL,
            InputHash CHAR(64) NOT NULL,
            RecommendationCount INT NOT NULL CHECK (RecommendationCount >= 0),
            InputJson NVARCHAR(MAX) NOT NULL CHECK (ISJSON(InputJson) = 1),
            ResultJson NVARCHAR(MAX) NOT NULL CHECK (ISJSON(ResultJson) = 1),
            CreatedAtUtc DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_RecommendationAnalysis_Target FOREIGN KEY(TargetId) REFERENCES dbo.TargetDatabase(TargetId),
            CONSTRAINT FK_RecommendationAnalysis_Batch FOREIGN KEY(BatchId) REFERENCES dbo.CollectionBatch(BatchId),
            CONSTRAINT FK_RecommendationAnalysis_Metadata FOREIGN KEY(MetadataBatchId) REFERENCES dbo.CollectionBatch(BatchId)
        );
        CREATE INDEX IX_RecommendationAnalysis_Target_Created ON dbo.RecommendationAnalysis(TargetId, CreatedAtUtc DESC);
        CREATE INDEX IX_RecommendationAnalysis_Batch ON dbo.RecommendationAnalysis(BatchId);
    END;
    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    THROW;
END CATCH;
GO
