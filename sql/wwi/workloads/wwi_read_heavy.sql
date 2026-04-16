USE [WideWorldImporters];
GO

CREATE OR ALTER PROCEDURE dbo.usp_POC_ReadHeavy_Workload
    @Iterations INT = 25
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @i INT = 1;

    DECLARE @MaxOrderDate DATE =
    (
        SELECT MAX(o.OrderDate)
        FROM Sales.Orders AS o
    );

    DECLARE @WindowStart DATE = DATEADD(DAY, -60, @MaxOrderDate);

    DECLARE @CustomerID INT =
    (
        SELECT TOP (1) o.CustomerID
        FROM Sales.Orders AS o
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.CustomerID
        ORDER BY COUNT(*) DESC, o.CustomerID
    );

    DECLARE @SalespersonPersonID INT =
    (
        SELECT TOP (1) o.SalespersonPersonID
        FROM Sales.Orders AS o
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.SalespersonPersonID
        ORDER BY COUNT(*) DESC, o.SalespersonPersonID
    );

    DECLARE @StockItemID INT =
    (
        SELECT TOP (1) ol.StockItemID
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY ol.StockItemID
        ORDER BY SUM(ol.Quantity) DESC, ol.StockItemID
    );

    WHILE @i <= @Iterations
    BEGIN
        ----------------------------------------------------------------------
        -- Query 1: Recent orders for busiest customer in recent date window
        ----------------------------------------------------------------------
        SELECT TOP (200)
            o.OrderID,
            o.OrderDate,
            o.ExpectedDeliveryDate,
            c.CustomerName,
            p.FullName AS SalespersonName
        FROM Sales.Orders AS o
        INNER JOIN Sales.Customers AS c
            ON c.CustomerID = o.CustomerID
        INNER JOIN Application.People AS p
            ON p.PersonID = o.SalespersonPersonID
        WHERE o.CustomerID = @CustomerID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        ORDER BY o.OrderDate DESC, o.OrderID DESC;

        ----------------------------------------------------------------------
        -- Query 2: Salesperson summary over recent time window
        ----------------------------------------------------------------------
        SELECT TOP (25)
            o.SalespersonPersonID,
            p.FullName,
            COUNT(DISTINCT o.OrderID) AS OrderCount,
            SUM(ol.Quantity) AS TotalUnits,
            SUM(CONVERT(DECIMAL(18,2), ol.Quantity) * ol.UnitPrice) AS EstimatedRevenue
        FROM Sales.Orders AS o
        INNER JOIN Sales.OrderLines AS ol
            ON ol.OrderID = o.OrderID
        INNER JOIN Application.People AS p
            ON p.PersonID = o.SalespersonPersonID
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.SalespersonPersonID, p.FullName
        ORDER BY EstimatedRevenue DESC, OrderCount DESC;

        ----------------------------------------------------------------------
        -- Query 3: Customer + item focused query
        ----------------------------------------------------------------------
        SELECT TOP (200)
            o.OrderID,
            o.OrderDate,
            c.CustomerName,
            ol.OrderLineID,
            ol.StockItemID,
            si.StockItemName,
            ol.Quantity,
            ol.UnitPrice
        FROM Sales.Orders AS o
        INNER JOIN Sales.Customers AS c
            ON c.CustomerID = o.CustomerID
        INNER JOIN Sales.OrderLines AS ol
            ON ol.OrderID = o.OrderID
        INNER JOIN Warehouse.StockItems AS si
            ON si.StockItemID = ol.StockItemID
        WHERE o.CustomerID = @CustomerID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
          AND ol.StockItemID = @StockItemID
        ORDER BY o.OrderDate DESC, o.OrderID DESC, ol.OrderLineID DESC;

        ----------------------------------------------------------------------
        -- Query 4: Unpicked/open work by expected delivery date
        ----------------------------------------------------------------------
        SELECT TOP (100)
            o.ExpectedDeliveryDate,
            o.CustomerID,
            c.CustomerName,
            COUNT(*) AS OpenLineCount
        FROM Sales.Orders AS o
        INNER JOIN Sales.Customers AS c
            ON c.CustomerID = o.CustomerID
        INNER JOIN Sales.OrderLines AS ol
            ON ol.OrderID = o.OrderID
        WHERE o.ExpectedDeliveryDate BETWEEN @WindowStart AND @MaxOrderDate
          AND ol.PickingCompletedWhen IS NULL
        GROUP BY
            o.ExpectedDeliveryDate,
            o.CustomerID,
            c.CustomerName
        ORDER BY
            o.ExpectedDeliveryDate DESC,
            OpenLineCount DESC,
            o.CustomerID;

        ----------------------------------------------------------------------
        -- Query 5: Hot stock item summary for one salesperson
        ----------------------------------------------------------------------
        SELECT TOP (50)
            ol.StockItemID,
            si.StockItemName,
            COUNT(*) AS LineCount,
            SUM(ol.Quantity) AS TotalQty,
            SUM(CONVERT(DECIMAL(18,2), ol.Quantity) * ol.UnitPrice) AS Revenue
        FROM Sales.Orders AS o
        INNER JOIN Sales.OrderLines AS ol
            ON ol.OrderID = o.OrderID
        INNER JOIN Warehouse.StockItems AS si
            ON si.StockItemID = ol.StockItemID
        WHERE o.SalespersonPersonID = @SalespersonPersonID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY
            ol.StockItemID,
            si.StockItemName
        ORDER BY Revenue DESC, TotalQty DESC, ol.StockItemID;

        SET @i += 1;
    END
END;
GO