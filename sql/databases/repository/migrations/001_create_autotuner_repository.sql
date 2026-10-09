USE [master];
GO

IF DB_ID(N'AutoTunerRepository') IS NULL
BEGIN
    CREATE DATABASE [AutoTunerRepository];
END;
GO

USE [AutoTunerRepository];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.TargetDatabase', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TargetDatabase
    (
        TargetId UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT PK_TargetDatabase PRIMARY KEY
            CONSTRAINT DF_TargetDatabase_TargetId DEFAULT NEWSEQUENTIALID(),

        Name NVARCHAR(200) NOT NULL,
        ServerName NVARCHAR(256) NOT NULL,
        DatabaseName SYSNAME NOT NULL,
        AuthenticationMode NVARCHAR(20) NOT NULL,
        DriverName NVARCHAR(100) NOT NULL,
        EncryptConnection BIT NOT NULL,
        TrustServerCertificate BIT NOT NULL,
        ConnectionTimeoutSeconds INT NOT NULL,
        QueryTimeoutSeconds INT NOT NULL,

        -- Reference to environment/secret-store configuration.
        -- Passwords are never stored in this database.
        CredentialReference NVARCHAR(200) NULL,

        IsEnabled BIT NOT NULL
            CONSTRAINT DF_TargetDatabase_IsEnabled DEFAULT (1),
        CreatedAtUtc DATETIME2(3) NOT NULL
            CONSTRAINT DF_TargetDatabase_CreatedAtUtc DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc DATETIME2(3) NOT NULL
            CONSTRAINT DF_TargetDatabase_UpdatedAtUtc DEFAULT SYSUTCDATETIME(),
        RowVersion ROWVERSION NOT NULL,

        CONSTRAINT UQ_TargetDatabase_Name UNIQUE (Name),
        CONSTRAINT CK_TargetDatabase_AuthenticationMode
            CHECK (AuthenticationMode IN (N'windows', N'sql')),
        CONSTRAINT CK_TargetDatabase_Timeouts
            CHECK
            (
                ConnectionTimeoutSeconds BETWEEN 1 AND 60
                AND QueryTimeoutSeconds BETWEEN 1 AND 60
            ),
        CONSTRAINT CK_TargetDatabase_CredentialReference
            CHECK
            (
                AuthenticationMode = N'windows'
                OR
                (
                    AuthenticationMode = N'sql'
                    AND CredentialReference IS NOT NULL
                    AND LEN(LTRIM(RTRIM(CredentialReference))) > 0
                )
            )
    );

    CREATE INDEX IX_TargetDatabase_Enabled_Name
        ON dbo.TargetDatabase(IsEnabled, Name);
END;
GO

IF OBJECT_ID(N'dbo.CollectionBatch', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CollectionBatch
    (
        BatchId UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT PK_CollectionBatch PRIMARY KEY
            CONSTRAINT DF_CollectionBatch_BatchId DEFAULT NEWSEQUENTIALID(),
        TargetId UNIQUEIDENTIFIER NOT NULL,
        Label NVARCHAR(200) NULL,
        RequestedWindowStartUtc DATETIME2(3) NULL,
        RequestedWindowEndUtc DATETIME2(3) NULL,
        CollectionStartedAtUtc DATETIME2(3) NULL,
        CollectionCompletedAtUtc DATETIME2(3) NULL,
        Status NVARCHAR(30) NOT NULL
            CONSTRAINT DF_CollectionBatch_Status DEFAULT N'Pending',
        CompletenessPercent DECIMAL(5,2) NOT NULL
            CONSTRAINT DF_CollectionBatch_CompletenessPercent DEFAULT (0),
        CollectorVersion NVARCHAR(50) NULL,
        FailureReason NVARCHAR(2000) NULL,
        CreatedAtUtc DATETIME2(3) NOT NULL
            CONSTRAINT DF_CollectionBatch_CreatedAtUtc DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc DATETIME2(3) NOT NULL
            CONSTRAINT DF_CollectionBatch_UpdatedAtUtc DEFAULT SYSUTCDATETIME(),
        RowVersion ROWVERSION NOT NULL,

        CONSTRAINT FK_CollectionBatch_TargetDatabase
            FOREIGN KEY (TargetId) REFERENCES dbo.TargetDatabase(TargetId),
        CONSTRAINT CK_CollectionBatch_Status
            CHECK
            (
                Status IN
                (
                    N'Pending', N'Collecting', N'Completed',
                    N'Partial', N'Failed', N'Cancelled'
                )
            ),
        CONSTRAINT CK_CollectionBatch_CompletenessPercent
            CHECK (CompletenessPercent BETWEEN 0 AND 100),
        CONSTRAINT CK_CollectionBatch_RequestedWindow
            CHECK
            (
                RequestedWindowStartUtc IS NULL
                OR RequestedWindowEndUtc IS NULL
                OR RequestedWindowStartUtc <= RequestedWindowEndUtc
            )
    );

    CREATE INDEX IX_CollectionBatch_Target_CreatedAtUtc
        ON dbo.CollectionBatch(TargetId, CreatedAtUtc DESC);
    CREATE INDEX IX_CollectionBatch_Status_CreatedAtUtc
        ON dbo.CollectionBatch(Status, CreatedAtUtc DESC);
END;
GO

IF OBJECT_ID(N'dbo.CollectionComponentResult', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CollectionComponentResult
    (
        ComponentResultId BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_CollectionComponentResult PRIMARY KEY,
        BatchId UNIQUEIDENTIFIER NOT NULL,
        ComponentName NVARCHAR(100) NOT NULL,
        Status NVARCHAR(30) NOT NULL,
        RowsCollected BIGINT NULL,
        StartedAtUtc DATETIME2(3) NULL,
        CompletedAtUtc DATETIME2(3) NULL,
        ErrorCode NVARCHAR(100) NULL,
        ErrorMessage NVARCHAR(2000) NULL,

        CONSTRAINT FK_CollectionComponentResult_CollectionBatch
            FOREIGN KEY (BatchId)
            REFERENCES dbo.CollectionBatch(BatchId)
            ON DELETE CASCADE,
        CONSTRAINT CK_CollectionComponentResult_Status
            CHECK
            (
                Status IN
                (
                    N'Pending', N'Collecting', N'Completed',
                    N'Partial', N'Failed', N'Skipped'
                )
            ),
        CONSTRAINT UQ_CollectionComponentResult_Batch_Component
            UNIQUE (BatchId, ComponentName)
    );
END;
GO
