USE [AutoTunerRepository];
GO
SET NOCOUNT ON;
GO

IF COL_LENGTH(N'dbo.CollectionBatch', N'EffectiveWindowStartUtc') IS NULL
    ALTER TABLE dbo.CollectionBatch ADD EffectiveWindowStartUtc DATETIME2(3) NULL;
GO
IF COL_LENGTH(N'dbo.CollectionBatch', N'EffectiveWindowEndUtc') IS NULL
    ALTER TABLE dbo.CollectionBatch ADD EffectiveWindowEndUtc DATETIME2(3) NULL;
GO
IF COL_LENGTH(N'dbo.CollectionBatch', N'WindowSource') IS NULL
    ALTER TABLE dbo.CollectionBatch ADD WindowSource NVARCHAR(30) NULL;
GO
IF COL_LENGTH(N'dbo.CollectionBatch', N'ForceMetadata') IS NULL
BEGIN
    ALTER TABLE dbo.CollectionBatch
        ADD ForceMetadata BIT NOT NULL
            CONSTRAINT DF_CollectionBatch_ForceMetadata DEFAULT (0)
            WITH VALUES;
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.CollectionBatch')
      AND name = N'CK_CollectionBatch_EffectiveWindow'
)
BEGIN
    ALTER TABLE dbo.CollectionBatch
        ADD CONSTRAINT CK_CollectionBatch_EffectiveWindow CHECK (
            EffectiveWindowStartUtc IS NULL
            OR EffectiveWindowEndUtc IS NULL
            OR EffectiveWindowStartUtc <= EffectiveWindowEndUtc
        );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.CollectionBatch')
      AND name = N'CK_CollectionBatch_WindowSource'
)
BEGIN
    ALTER TABLE dbo.CollectionBatch
        ADD CONSTRAINT CK_CollectionBatch_WindowSource CHECK (
            WindowSource IS NULL
            OR WindowSource IN (N'Explicit', N'Incremental', N'InitialLookback')
        );
END;
GO

IF COL_LENGTH(N'dbo.CollectionComponentResult', N'StatusMessage') IS NULL
    ALTER TABLE dbo.CollectionComponentResult ADD StatusMessage NVARCHAR(2000) NULL;
GO

IF OBJECT_ID(N'dbo.TargetCollectionState', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TargetCollectionState
    (
        TargetId UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT PK_TargetCollectionState PRIMARY KEY,

        LastQueryRuntimeWatermarkUtc DATETIME2(3) NULL,
        LastSuccessfulQueryBatchId UNIQUEIDENTIFIER NULL,

        LastMetadataCollectedAtUtc DATETIME2(3) NULL,
        LastMetadataBatchId UNIQUEIDENTIFIER NULL,

        UpdatedAtUtc DATETIME2(3) NOT NULL
            CONSTRAINT DF_TargetCollectionState_UpdatedAtUtc DEFAULT SYSUTCDATETIME(),

        RowVersion ROWVERSION NOT NULL,

        CONSTRAINT FK_TargetCollectionState_TargetDatabase
            FOREIGN KEY (TargetId)
            REFERENCES dbo.TargetDatabase(TargetId)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.CollectionBatch')
      AND name = N'IX_CollectionBatch_Target_Status_CreatedAtUtc'
)
BEGIN
    CREATE INDEX IX_CollectionBatch_Target_Status_CreatedAtUtc
        ON dbo.CollectionBatch(TargetId, Status, CreatedAtUtc DESC);
END;
GO
