/*
POC seed data.
For a stronger POC, scale @TicketCount up (e.g., 200000+).
*/

SET NOCOUNT ON;

DECLARE @DeptCount INT = 10;
DECLARE @UsersPerDept INT = 50;
DECLARE @TicketCount INT = 50000;

-- Departments
;WITH n AS (
  SELECT TOP (@DeptCount) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
  FROM sys.all_objects
)
INSERT INTO dbo.Departments(Name)
SELECT CONCAT('Dept ', i) FROM n;

-- Users
DECLARE @d INT = 1;
WHILE @d <= @DeptCount
BEGIN
  ;WITH n AS (
    SELECT TOP (@UsersPerDept) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects
  )
  INSERT INTO dbo.Users(DepartmentId, DisplayName, Email)
  SELECT @d,
         CONCAT('User ', @d, '-', i),
         CONCAT('user', @d, '_', i, '@example.com')
  FROM n;

  SET @d += 1;
END

-- Tickets
;WITH n AS (
  SELECT TOP (@TicketCount) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
  FROM sys.all_objects a
  CROSS JOIN sys.all_objects b
)
INSERT INTO dbo.Tickets(DepartmentId, UserId, Status, Priority, CreatedAt, UpdatedAt, Title, Body)
SELECT
  1 + (ABS(CHECKSUM(NEWID())) % @DeptCount) AS DepartmentId,
  1 + (ABS(CHECKSUM(NEWID())) % (@DeptCount * @UsersPerDept)) AS UserId,
  CASE (ABS(CHECKSUM(NEWID())) % 4)
    WHEN 0 THEN 'Open'
    WHEN 1 THEN 'In Progress'
    WHEN 2 THEN 'Resolved'
    ELSE 'Closed'
  END AS Status,
  1 + (ABS(CHECKSUM(NEWID())) % 5) AS Priority,
  DATEADD(DAY, -1 * (ABS(CHECKSUM(NEWID())) % 365), SYSUTCDATETIME()) AS CreatedAt,
  SYSUTCDATETIME() AS UpdatedAt,
  CONCAT('Ticket ', i, ' issue') AS Title,
  REPLICATE(CONVERT(NVARCHAR(MAX), 'lorem ipsum '), 20) AS Body
FROM n;

PRINT 'Seed complete.';
