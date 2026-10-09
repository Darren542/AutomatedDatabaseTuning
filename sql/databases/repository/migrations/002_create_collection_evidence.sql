USE [AutoTunerRepository];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.CollectionSourceState', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CollectionSourceState
    (
        BatchId UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObservedAtUtc DATETIME2(3) NOT NULL,
        SqlServerStartTimeUtc DATETIME2(3) NULL,
        DatabaseId INT NOT NULL,
        DatabaseCreateDateUtc DATETIME2(3) NULL,
        QueryStoreActualState NVARCHAR(60) NULL,
        QueryStoreMaxIntervalId BIGINT NULL,
        QueryStoreMaxQueryId BIGINT NULL,
        QueryStoreMaxPlanId BIGINT NULL,
        DmvResetDetected BIT NOT NULL DEFAULT (0),
        QueryStoreResetDetected BIT NOT NULL DEFAULT (0),
        CONSTRAINT FK_CollectionSourceState_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE,
        CONSTRAINT FK_CollectionSourceState_Target FOREIGN KEY (TargetId)
            REFERENCES dbo.TargetDatabase(TargetId)
    );
    CREATE INDEX IX_CollectionSourceState_Target_Observed
        ON dbo.CollectionSourceState(TargetId, ObservedAtUtc DESC);
END;
GO

IF OBJECT_ID(N'dbo.QueryStoreRuntimeEvidence', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.QueryStoreRuntimeEvidence
    (
        EvidenceId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        RuntimeStatsIntervalId BIGINT NOT NULL,
        RuntimeStatsId BIGINT NOT NULL,
        PlanId BIGINT NOT NULL,
        QueryId BIGINT NOT NULL,
        QueryTextId BIGINT NOT NULL,
        ObjectId BIGINT NULL,
        QueryHash VARBINARY(64) NULL,
        QueryPlanHash VARBINARY(64) NULL,
        QuerySqlText NVARCHAR(MAX) NOT NULL,
        ExecutionType TINYINT NOT NULL,
        ExecutionTypeDesc NVARCHAR(60) NULL,
        IntervalStartUtc DATETIMEOFFSET(7) NOT NULL,
        IntervalEndUtc DATETIMEOFFSET(7) NOT NULL,
        FirstExecutionTimeUtc DATETIMEOFFSET(7) NULL,
        LastExecutionTimeUtc DATETIMEOFFSET(7) NULL,
        ExecutionCount BIGINT NOT NULL,
        AvgDurationMicroseconds FLOAT NULL,
        AvgCpuTimeMicroseconds FLOAT NULL,
        AvgLogicalIoReads FLOAT NULL,
        AvgLogicalIoWrites FLOAT NULL,
        AvgPhysicalIoReads FLOAT NULL,
        AvgRowCount FLOAT NULL,
        LastObservedAtUtc DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_QueryStoreRuntimeEvidence_Target FOREIGN KEY (TargetId)
            REFERENCES dbo.TargetDatabase(TargetId),
        CONSTRAINT UQ_QueryStoreRuntimeEvidence_Source
            UNIQUE (TargetId, RuntimeStatsIntervalId, RuntimeStatsId)
    );
    CREATE INDEX IX_QueryStoreRuntimeEvidence_Target_Interval
        ON dbo.QueryStoreRuntimeEvidence(TargetId, IntervalStartUtc, IntervalEndUtc);
    CREATE INDEX IX_QueryStoreRuntimeEvidence_Query
        ON dbo.QueryStoreRuntimeEvidence(TargetId, QueryId, PlanId);
END;
GO

IF OBJECT_ID(N'dbo.CollectionQueryStoreEvidence', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CollectionQueryStoreEvidence
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        EvidenceId BIGINT NOT NULL,
        CONSTRAINT PK_CollectionQueryStoreEvidence PRIMARY KEY (BatchId, EvidenceId),
        CONSTRAINT FK_CollectionQueryStoreEvidence_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE,
        CONSTRAINT FK_CollectionQueryStoreEvidence_Evidence FOREIGN KEY (EvidenceId)
            REFERENCES dbo.QueryStoreRuntimeEvidence(EvidenceId)
    );
    CREATE INDEX IX_CollectionQueryStoreEvidence_Evidence
        ON dbo.CollectionQueryStoreEvidence(EvidenceId, BatchId);
END;
GO

IF OBJECT_ID(N'dbo.IndexUsageObservation', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.IndexUsageObservation
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        IndexId INT NOT NULL,
        SchemaName SYSNAME NOT NULL,
        TableName SYSNAME NOT NULL,
        IndexName SYSNAME NULL,
        UserSeeks BIGINT NOT NULL,
        UserScans BIGINT NOT NULL,
        UserLookups BIGINT NOT NULL,
        UserUpdates BIGINT NOT NULL,
        LastUserSeekUtc DATETIME2(3) NULL,
        LastUserScanUtc DATETIME2(3) NULL,
        LastUserLookupUtc DATETIME2(3) NULL,
        LastUserUpdateUtc DATETIME2(3) NULL,
        SqlServerStartTimeUtc DATETIME2(3) NULL,
        ObservedAtUtc DATETIME2(3) NOT NULL,
        CONSTRAINT PK_IndexUsageObservation PRIMARY KEY (BatchId, ObjectId, IndexId),
        CONSTRAINT FK_IndexUsageObservation_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.IndexOperationalObservation', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.IndexOperationalObservation
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        IndexId INT NOT NULL,
        PartitionNumber INT NOT NULL,
        SchemaName SYSNAME NOT NULL,
        TableName SYSNAME NOT NULL,
        IndexName SYSNAME NULL,
        LeafInsertCount BIGINT NOT NULL,
        LeafDeleteCount BIGINT NOT NULL,
        LeafUpdateCount BIGINT NOT NULL,
        RowLockCount BIGINT NOT NULL,
        RowLockWaitCount BIGINT NOT NULL,
        RowLockWaitMs BIGINT NOT NULL,
        PageLockCount BIGINT NOT NULL,
        PageLockWaitCount BIGINT NOT NULL,
        PageLockWaitMs BIGINT NOT NULL,
        PageLatchWaitCount BIGINT NOT NULL,
        PageLatchWaitMs BIGINT NOT NULL,
        SqlServerStartTimeUtc DATETIME2(3) NULL,
        ObservedAtUtc DATETIME2(3) NOT NULL,
        CONSTRAINT PK_IndexOperationalObservation
            PRIMARY KEY (BatchId, ObjectId, IndexId, PartitionNumber),
        CONSTRAINT FK_IndexOperationalObservation_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.MissingIndexObservation', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.MissingIndexObservation
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        GroupHandle INT NOT NULL,
        IndexHandle INT NOT NULL,
        ObjectId INT NOT NULL,
        SchemaName SYSNAME NOT NULL,
        TableName SYSNAME NOT NULL,
        EqualityColumns NVARCHAR(4000) NULL,
        InequalityColumns NVARCHAR(4000) NULL,
        IncludedColumns NVARCHAR(4000) NULL,
        UserSeeks BIGINT NOT NULL,
        UserScans BIGINT NOT NULL,
        LastUserSeekUtc DATETIME2(3) NULL,
        LastUserScanUtc DATETIME2(3) NULL,
        AvgTotalUserCost FLOAT NOT NULL,
        AvgUserImpact FLOAT NOT NULL,
        SqlServerStartTimeUtc DATETIME2(3) NULL,
        ObservedAtUtc DATETIME2(3) NOT NULL,
        CONSTRAINT PK_MissingIndexObservation
            PRIMARY KEY (BatchId, GroupHandle, IndexHandle),
        CONSTRAINT FK_MissingIndexObservation_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.TableMetadataSnapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TableMetadataSnapshot
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        SchemaName SYSNAME NOT NULL,
        TableName SYSNAME NOT NULL,
        [RowCount] BIGINT NOT NULL,
        ReservedSizeMb DECIMAL(19,3) NOT NULL,
        UsedSizeMb DECIMAL(19,3) NOT NULL,
        DataSizeMb DECIMAL(19,3) NOT NULL,
        ObservedAtUtc DATETIME2(3) NOT NULL,
        CONSTRAINT PK_TableMetadataSnapshot PRIMARY KEY (BatchId, ObjectId),
        CONSTRAINT FK_TableMetadataSnapshot_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.ColumnMetadataSnapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ColumnMetadataSnapshot
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        ColumnId INT NOT NULL,
        ColumnName SYSNAME NOT NULL,
        DataType SYSNAME NOT NULL,
        MaxLength SMALLINT NOT NULL,
        NumericPrecision TINYINT NOT NULL,
        NumericScale TINYINT NOT NULL,
        IsNullable BIT NOT NULL,
        IsIdentity BIT NOT NULL,
        IsComputed BIT NOT NULL,
        CONSTRAINT PK_ColumnMetadataSnapshot PRIMARY KEY (BatchId, ObjectId, ColumnId),
        CONSTRAINT FK_ColumnMetadataSnapshot_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.IndexMetadataSnapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.IndexMetadataSnapshot
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        IndexId INT NOT NULL,
        IndexName SYSNAME NULL,
        IndexType TINYINT NOT NULL,
        IndexTypeDesc NVARCHAR(60) NOT NULL,
        IsUnique BIT NOT NULL,
        IsPrimaryKey BIT NOT NULL,
        IsUniqueConstraint BIT NOT NULL,
        IsDisabled BIT NOT NULL,
        HasFilter BIT NOT NULL,
        FilterDefinition NVARCHAR(MAX) NULL,
        CONSTRAINT PK_IndexMetadataSnapshot PRIMARY KEY (BatchId, ObjectId, IndexId),
        CONSTRAINT FK_IndexMetadataSnapshot_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.IndexColumnMetadataSnapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.IndexColumnMetadataSnapshot
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        IndexId INT NOT NULL,
        ColumnId INT NOT NULL,
        KeyOrdinal TINYINT NOT NULL,
        IndexColumnId INT NOT NULL,
        IsIncludedColumn BIT NOT NULL,
        IsDescendingKey BIT NOT NULL,
        CONSTRAINT PK_IndexColumnMetadataSnapshot
            PRIMARY KEY (BatchId, ObjectId, IndexId, IndexColumnId),
        CONSTRAINT FK_IndexColumnMetadataSnapshot_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO

IF OBJECT_ID(N'dbo.ConstraintMetadataSnapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ConstraintMetadataSnapshot
    (
        BatchId UNIQUEIDENTIFIER NOT NULL,
        TargetId UNIQUEIDENTIFIER NOT NULL,
        ObjectId INT NOT NULL,
        ConstraintObjectId INT NOT NULL,
        ConstraintName SYSNAME NOT NULL,
        ConstraintType NVARCHAR(30) NOT NULL,
        UniqueIndexId INT NULL,
        ReferencedObjectId INT NULL,
        IsDisabled BIT NULL,
        CONSTRAINT PK_ConstraintMetadataSnapshot PRIMARY KEY (BatchId, ConstraintObjectId),
        CONSTRAINT FK_ConstraintMetadataSnapshot_Batch FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId) ON DELETE CASCADE
    );
END;
GO
