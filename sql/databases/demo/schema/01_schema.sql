/*
POC schema: Ticketing-style dataset with joins and search filters.
*/

IF OBJECT_ID('dbo.Tickets', 'U') IS NOT NULL DROP TABLE dbo.Tickets;
IF OBJECT_ID('dbo.Users', 'U') IS NOT NULL DROP TABLE dbo.Users;
IF OBJECT_ID('dbo.Departments', 'U') IS NOT NULL DROP TABLE dbo.Departments;
GO

CREATE TABLE dbo.Departments (
  DepartmentId INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  Name NVARCHAR(100) NOT NULL
);

CREATE TABLE dbo.Users (
  UserId INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  DepartmentId INT NOT NULL,
  DisplayName NVARCHAR(120) NOT NULL,
  Email NVARCHAR(200) NOT NULL,
  CONSTRAINT FK_Users_Department FOREIGN KEY (DepartmentId) REFERENCES dbo.Departments(DepartmentId)
);

CREATE TABLE dbo.Tickets (
  TicketId BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  DepartmentId INT NOT NULL,
  UserId INT NOT NULL,
  Status NVARCHAR(30) NOT NULL,
  Priority INT NOT NULL,
  CreatedAt DATETIME2 NOT NULL,
  UpdatedAt DATETIME2 NOT NULL,
  Title NVARCHAR(200) NOT NULL,
  Body NVARCHAR(MAX) NOT NULL,
  CONSTRAINT FK_Tickets_Department FOREIGN KEY (DepartmentId) REFERENCES dbo.Departments(DepartmentId),
  CONSTRAINT FK_Tickets_User FOREIGN KEY (UserId) REFERENCES dbo.Users(UserId)
);

-- Intentionally minimal indexing for baseline; the autotuner should propose useful nonclustered indexes.
-- You can add a couple basic indexes later if needed.
GO
