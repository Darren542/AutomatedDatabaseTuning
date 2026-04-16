/*
Write-heavy workload: inserts + updates + deletes.
Run repeatedly to create write pressure and validate write amplification penalties.
*/

SET NOCOUNT ON;

DECLARE @Dept INT = 2;
DECLARE @User INT = 10;

-- Insert burst
DECLARE @i INT = 0;
WHILE @i < 200
BEGIN
  INSERT INTO dbo.Tickets(DepartmentId, UserId, Status, Priority, CreatedAt, UpdatedAt, Title, Body)
  VALUES (@Dept, @User, 'Open', 3, SYSUTCDATETIME(), SYSUTCDATETIME(), 'POC Insert', REPLICATE(CONVERT(NVARCHAR(MAX), 'x'), 2000));

  SET @i += 1;
END

-- Update burst: flip status for recent tickets
UPDATE TOP (500) dbo.Tickets
SET Status = CASE WHEN Status = 'Open' THEN 'In Progress' ELSE 'Open' END,
    UpdatedAt = SYSUTCDATETIME()
WHERE DepartmentId = @Dept
  AND CreatedAt > DATEADD(DAY, -60, SYSUTCDATETIME());

-- Delete burst: remove a small number of closed tickets
DELETE TOP (50)
FROM dbo.Tickets
WHERE Status = 'Closed'
  AND CreatedAt < DATEADD(DAY, -180, SYSUTCDATETIME());
