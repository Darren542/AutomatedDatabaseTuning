/*
Enable Query Store and apply reasonable defaults for a POC.
Run this in the target database context (USE <db>;).
*/

-- Enable Query Store (if not already enabled)
ALTER DATABASE CURRENT SET QUERY_STORE = ON;
GO

-- Basic configuration (adjust as needed)
ALTER DATABASE CURRENT SET QUERY_STORE (
    OPERATION_MODE = READ_WRITE,
    CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 14),
    DATA_FLUSH_INTERVAL_SECONDS = 900,
    INTERVAL_LENGTH_MINUTES = 15,
    MAX_STORAGE_SIZE_MB = 512,
    QUERY_CAPTURE_MODE = AUTO
);
GO
