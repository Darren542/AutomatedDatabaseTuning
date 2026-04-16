USE [WideWorldImporters];
GO

/*
Generate candidate CREATE INDEX statements from a captured run.

How to use:
- Set @RunID
- Review the output
- Copy the statement you want into a new script and test it
*/

SET NOCOUNT ON;
GO

DECLARE @RunID INT = 1;

;WITH RankedCandidates AS
(
    SELECT
        mis.RunID,
        mis.SchemaName,
        mis.TableName,
        mis.EqualityColumns,
        mis.InequalityColumns,
        mis.IncludedColumns,
        mis.UserSeeks,
        mis.UserScans,
        mis.AvgTotalUserCost,
        mis.AvgUserImpact,
        mis.ImprovementMeasure,
        ROW_NUMBER() OVER
        (
            PARTITION BY mis.SchemaName, mis.TableName
            ORDER BY mis.ImprovementMeasure DESC
        ) AS TableRank
    FROM dbo.POC_MissingIndexSnapshot AS mis
    WHERE mis.RunID = @RunID
)
SELECT
    rc.SchemaName,
    rc.TableName,
    rc.EqualityColumns,
    rc.InequalityColumns,
    rc.IncludedColumns,
    rc.ImprovementMeasure,
    '/* RunID ' + CAST(@RunID AS NVARCHAR(20))
        + ' | ImprovementMeasure=' + CAST(CAST(rc.ImprovementMeasure AS DECIMAL(18,2)) AS NVARCHAR(50))
        + ' */' + CHAR(13) + CHAR(10)
        + 'CREATE NONCLUSTERED INDEX IX_POC_'
        + rc.TableName + '_'
        + CAST(rc.TableRank AS NVARCHAR(10))
        + CHAR(13) + CHAR(10)
        + 'ON ' + QUOTENAME(rc.SchemaName) + '.' + QUOTENAME(rc.TableName) + ' ('
        + LTRIM(RTRIM(
            COALESCE(rc.EqualityColumns, '')
            + CASE
                WHEN rc.EqualityColumns IS NOT NULL AND rc.InequalityColumns IS NOT NULL THEN ', '
                ELSE ''
              END
            + COALESCE(rc.InequalityColumns, '')
          ))
        + ')'
        + CASE
            WHEN rc.IncludedColumns IS NOT NULL AND LTRIM(RTRIM(rc.IncludedColumns)) <> ''
                THEN CHAR(13) + CHAR(10) + 'INCLUDE (' + rc.IncludedColumns + ')'
            ELSE ''
          END
        + ';' AS SuggestedCreateIndexSql
FROM RankedCandidates AS rc
ORDER BY rc.ImprovementMeasure DESC;
GO