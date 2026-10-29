/* Optional local SQL Server collector setup. REVIEW BEFORE RUNNING.
   Create a dedicated non-admin login in SSMS first; no passwords belong here.
   Set the login below. Run as an administrator on the monitored instance.
   This script grants telemetry visibility, not target DDL or user-table writes.
   Server-state visibility includes telemetry outside the selected database.
   Never use an existing administrator login as the collector account.

   References:
   https://learn.microsoft.com/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-sys-info-transact-sql
   https://learn.microsoft.com/sql/relational-databases/system-catalog-views/sys-query-store-runtime-stats-transact-sql
*/
USE [WideWorldImporters];
GO
DECLARE @CollectorLogin sysname = N'REPLACE_WITH_COLLECTOR_LOGIN';
IF @CollectorLogin = N'REPLACE_WITH_COLLECTOR_LOGIN'
    THROW 50001, 'Set CollectorLogin to a dedicated existing non-admin SQL Server login.', 1;
IF SUSER_ID(@CollectorLogin) IS NULL
    THROW 50002, 'Create the dedicated login in SSMS before running this script.', 1;
IF IS_SRVROLEMEMBER(N'sysadmin', @CollectorLogin) = 1
    THROW 50003, 'Collector login must not be a sysadmin.', 1;

DECLARE @sql nvarchar(max);
IF USER_ID(@CollectorLogin) IS NULL
BEGIN
    SET @sql = N'CREATE USER ' + QUOTENAME(@CollectorLogin) + N' FOR LOGIN ' + QUOTENAME(@CollectorLogin) + N';';
    EXEC sys.sp_executesql @sql;
END;
SET @sql = N'GRANT CONNECT TO ' + QUOTENAME(@CollectorLogin)
    + N'; GRANT VIEW DEFINITION TO ' + QUOTENAME(@CollectorLogin) + N';';
IF CAST(SERVERPROPERTY('ProductMajorVersion') AS int) >= 16
    SET @sql += N' GRANT VIEW DATABASE PERFORMANCE STATE TO ' + QUOTENAME(@CollectorLogin)
        + N'; GRANT VIEW SERVER PERFORMANCE STATE TO ' + QUOTENAME(@CollectorLogin) + N';';
ELSE
    SET @sql += N' GRANT VIEW DATABASE STATE TO ' + QUOTENAME(@CollectorLogin)
        + N'; GRANT VIEW SERVER STATE TO ' + QUOTENAME(@CollectorLogin) + N';';
EXEC sys.sp_executesql @sql;
PRINT 'Telemetry grants applied. Use the API capability check to verify access and absence of DDL permissions.';
GO
