/*
Read-heavy workload: filters, joins, sort, and aggregates.
Run multiple times / loop this script to generate Query Store history.
*/

SET NOCOUNT ON;

DECLARE @Dept INT = 3;

-- 1) Recent tickets for a department with status filter and sort
SELECT TOP (200)
  t.TicketId, t.Status, t.Priority, t.CreatedAt, u.DisplayName, d.Name
FROM dbo.Tickets t
JOIN dbo.Users u ON u.UserId = t.UserId
JOIN dbo.Departments d ON d.DepartmentId = t.DepartmentId
WHERE t.DepartmentId = @Dept
  AND t.Status IN ('Open', 'In Progress')
ORDER BY t.CreatedAt DESC;

-- 2) Priority distribution
SELECT
  t.Priority,
  COUNT(*) AS Cnt
FROM dbo.Tickets t
WHERE t.DepartmentId = @Dept
GROUP BY t.Priority
ORDER BY t.Priority;

-- 3) Search by CreatedAt range
DECLARE @Start DATETIME2 = DATEADD(DAY, -30, SYSUTCDATETIME());
DECLARE @End DATETIME2 = SYSUTCDATETIME();

SELECT TOP (500)
  t.TicketId, t.CreatedAt, t.Status, t.Priority
FROM dbo.Tickets t
WHERE t.CreatedAt BETWEEN @Start AND @End
  AND t.DepartmentId = @Dept
ORDER BY t.CreatedAt DESC;

-- 4) User leaderboard
SELECT TOP (50)
  u.UserId, u.DisplayName, COUNT(*) AS TicketCount
FROM dbo.Tickets t
JOIN dbo.Users u ON u.UserId = t.UserId
WHERE t.DepartmentId = @Dept
GROUP BY u.UserId, u.DisplayName
ORDER BY TicketCount DESC;
