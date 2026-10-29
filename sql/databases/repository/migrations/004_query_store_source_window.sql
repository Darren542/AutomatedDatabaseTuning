/* Run after migrations 001-003, with the API/collector stopped.
   Keep canonical evidence separate when Query Store IDs are reused after CLEAR.
   Existing evidence and batch links are preserved. No target database changes.
*/
USE [AutoTunerRepository];
GO
SET XACT_ABORT ON;
GO
BEGIN TRY
    BEGIN TRANSACTION;
    IF OBJECT_ID(N'dbo.QueryStoreRuntimeEvidence', N'U') IS NULL
        THROW 50001, 'Apply repository migrations 001-003 first.', 1;

    IF NOT EXISTS (
        SELECT 1 FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.QueryStoreRuntimeEvidence')
          AND name = N'UQ_QueryStoreRuntimeEvidence_SourceWindow'
    )
    BEGIN
        ALTER TABLE dbo.QueryStoreRuntimeEvidence
        ADD CONSTRAINT UQ_QueryStoreRuntimeEvidence_SourceWindow
            UNIQUE (TargetId, RuntimeStatsIntervalId, RuntimeStatsId, IntervalStartUtc);
    END;
    IF EXISTS (
        SELECT 1 FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.QueryStoreRuntimeEvidence')
          AND name = N'UQ_QueryStoreRuntimeEvidence_Source'
    )
        ALTER TABLE dbo.QueryStoreRuntimeEvidence
            DROP CONSTRAINT UQ_QueryStoreRuntimeEvidence_Source;
    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    THROW;
END CATCH;
GO
