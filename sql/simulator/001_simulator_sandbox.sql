/* Choose a disposable USER database in SSMS before running.
   Creates and seeds only TunerSim objects. Re-running does not reset existing data.
   INSERT/UPDATE simulation is confined to TunerSim.Orders. No secondary indexes
   are created, so read-pattern changes can produce missing-index evidence. */
IF DB_NAME() IN ('master','model','msdb','tempdb')
    THROW 50001, 'Choose a disposable user database first.', 1;
GO
IF SCHEMA_ID('TunerSim') IS NULL EXEC('CREATE SCHEMA TunerSim');
GO
IF OBJECT_ID('TunerSim.Configuration','U') IS NULL
BEGIN
    CREATE TABLE TunerSim.Configuration (Id int PRIMARY KEY CHECK(Id=1), SchemaVersion int NOT NULL, Enabled bit NOT NULL);
    INSERT TunerSim.Configuration VALUES(1,1,1);
END;
IF OBJECT_ID('TunerSim.Orders','U') IS NULL
BEGIN
    CREATE TABLE TunerSim.Orders (
        OrderId int IDENTITY PRIMARY KEY,
        CustomerId int NOT NULL, ProductId int NOT NULL,
        Status tinyint NOT NULL, Amount decimal(12,2) NOT NULL,
        Payload varchar(800) NOT NULL,
        CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    ;WITH n AS (SELECT TOP(20000) ROW_NUMBER() OVER(ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b)
    INSERT TunerSim.Orders(CustomerId,ProductId,Status,Amount,Payload)
        SELECT i%1000+1,i%500+1,i%4,10+i%1000,REPLICATE('x',800) FROM n;
END;
GO
/* Database-wide Query Store settings are optional. Review and run separately:
ALTER DATABASE CURRENT SET QUERY_STORE = ON;
ALTER DATABASE CURRENT SET QUERY_STORE
    (OPERATION_MODE=READ_WRITE, QUERY_CAPTURE_MODE=ALL, INTERVAL_LENGTH_MINUTES=1);
*/
/* Simulator login requires SELECT on the two objects and, for controlled writes,
   INSERT, UPDATE on TunerSim.Orders. Grant to your chosen test principal only.
   To disable future runs: UPDATE TunerSim.Configuration SET Enabled=0 WHERE Id=1.
*/
