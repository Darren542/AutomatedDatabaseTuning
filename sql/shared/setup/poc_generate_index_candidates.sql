
USE [WideWorldImporters];
GO

/*
POC Generate Index Candidates (v5)

Simplified:
- No disabled-index restore options
- Only CREATE_MISSING_INDEX recommendations
- Excludes dbo.POC_* internals
*/

SET NOCOUNT ON;
GO

DECLARE @RunID INT = 1;

;WITH MissingIndexCandidates AS
(
    SELECT
        'CREATE_MISSING_INDEX' AS CandidateType,
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
        ) AS LocalRank
    FROM dbo.POC_MissingIndexSnapshot AS mis
    WHERE mis.RunID = @RunID
      AND NOT (mis.SchemaName = 'dbo' AND mis.TableName LIKE 'POC[_]%')
)
SELECT
    ROW_NUMBER() OVER
    (
        ORDER BY ImprovementMeasure DESC, SchemaName, TableName, LocalRank
    ) AS CandidateNumber,
    CandidateType,
    SchemaName,
    TableName,
    EqualityColumns,
    InequalityColumns,
    IncludedColumns,
    UserSeeks,
    UserScans,
    AvgTotalUserCost,
    AvgUserImpact,
    ImprovementMeasure,
    '/* RunID ' + CAST(@RunID AS NVARCHAR(20)) +
    ' | ImprovementMeasure=' + CAST(CAST(ISNULL(ImprovementMeasure, 0) AS DECIMAL(18,2)) AS NVARCHAR(50)) + ' */' +
    CHAR(13) + CHAR(10) +
    'CREATE NONCLUSTERED INDEX IX_POC_' + TableName + '_' + CAST(LocalRank AS NVARCHAR(10)) + CHAR(13) + CHAR(10) +
    'ON [' + SchemaName + '].[' + TableName + '] (' +
    LTRIM(RTRIM(
        COALESCE(EqualityColumns, '') +
        CASE
            WHEN EqualityColumns IS NOT NULL AND InequalityColumns IS NOT NULL THEN ', '
            ELSE ''
        END +
        COALESCE(InequalityColumns, '')
    )) + ')' +
    CASE
        WHEN IncludedColumns IS NOT NULL AND LTRIM(RTRIM(IncludedColumns)) <> ''
            THEN CHAR(13) + CHAR(10) + 'INCLUDE (' + IncludedColumns + ')'
        ELSE ''
    END + ';' AS SuggestedSql
FROM MissingIndexCandidates
ORDER BY CandidateNumber;
GO
