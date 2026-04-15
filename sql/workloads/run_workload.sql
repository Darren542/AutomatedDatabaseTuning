USE [WideWorldImporters];
GO

/*
Run this after:
1) sql/workloads/wwi_read_heavy.sql
2) sql/workloads/wwi_write_heavy.sql

Change the variables below before running.
*/

DECLARE @WorkloadName SYSNAME = N'read';   -- read | write | mixed
DECLARE @ReadIterations INT = 25;
DECLARE @WriteIterations INT = 10;
DECLARE @OrdersPerIteration INT = 25;
DECLARE @RollbackChanges BIT = 1;          -- keep 1 for safe repeatable demos

PRINT CONCAT(N'Running workload mode: ', @WorkloadName);

IF @WorkloadName = N'read'
BEGIN
    EXEC dbo.usp_POC_ReadHeavy_Workload
        @Iterations = @ReadIterations;
END
ELSE IF @WorkloadName = N'write'
BEGIN
    EXEC dbo.usp_POC_WriteHeavy_Workload
        @Iterations = @WriteIterations,
        @OrdersPerIteration = @OrdersPerIteration,
        @RollbackChanges = @RollbackChanges;
END
ELSE IF @WorkloadName = N'mixed'
BEGIN
    EXEC dbo.usp_POC_ReadHeavy_Workload
        @Iterations = @ReadIterations;

    EXEC dbo.usp_POC_WriteHeavy_Workload
        @Iterations = @WriteIterations,
        @OrdersPerIteration = @OrdersPerIteration,
        @RollbackChanges = @RollbackChanges;
END
ELSE
BEGIN
    THROW 50001, 'Unknown workload name. Use read, write, or mixed.', 1;
END;
GO