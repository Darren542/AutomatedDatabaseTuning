USE [WideWorldImporters];
GO

CREATE OR ALTER PROCEDURE dbo.usp_POC_ReadHeavy_Workload
    @Iterations INT = 40
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @i INT = 1;

    DECLARE @MaxOrderDate DATE =
    (
        SELECT MAX(o.OrderDate)
        FROM Sales.Orders AS o
    );

    DECLARE @WindowStart DATE = DATEADD(DAY, -90, @MaxOrderDate);

    DECLARE @HotStockItemID INT =
    (
        SELECT TOP (1) ol.StockItemID
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY ol.StockItemID
        ORDER BY SUM(ol.Quantity) DESC, ol.StockItemID
    );

    DECLARE @HotCustomerID INT =
    (
        SELECT TOP (1) o.CustomerID
        FROM Sales.Orders AS o
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.CustomerID
        ORDER BY COUNT(*) DESC, o.CustomerID
    );

    DECLARE @HotSalespersonID INT =
    (
        SELECT TOP (1) o.SalespersonPersonID
        FROM Sales.Orders AS o
        WHERE o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.SalespersonPersonID
        ORDER BY COUNT(*) DESC, o.SalespersonPersonID
    );

    WHILE @i <= @Iterations
    BEGIN
        ----------------------------------------------------------------------
        -- Q1: Main demo query – strongly aligned to OrderLines(StockItemID)
        ----------------------------------------------------------------------
        SELECT TOP (300)
            /* POC_READ_Q1 */
            o.OrderID,
            o.OrderDate,
            c.CustomerName,
            ol.OrderLineID,
            ol.StockItemID,
            si.StockItemName,
            ol.Quantity,
            ol.UnitPrice
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        INNER JOIN Sales.Customers AS c
            ON c.CustomerID = o.CustomerID
        INNER JOIN Warehouse.StockItems AS si
            ON si.StockItemID = ol.StockItemID
        WHERE ol.StockItemID = @HotStockItemID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        ORDER BY o.OrderDate DESC, o.OrderID DESC, ol.OrderLineID DESC;

        ----------------------------------------------------------------------
        -- Q2: Aggregate by salesperson for same hot stock item
        ----------------------------------------------------------------------
        SELECT TOP (50)
            /* POC_READ_Q2 */
            o.SalespersonPersonID,
            p.FullName,
            COUNT(*) AS LineCount,
            SUM(ol.Quantity) AS TotalQty,
            SUM(CONVERT(DECIMAL(18,2), ol.Quantity) * ol.UnitPrice) AS Revenue
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        INNER JOIN Application.People AS p
            ON p.PersonID = o.SalespersonPersonID
        WHERE ol.StockItemID = @HotStockItemID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        GROUP BY o.SalespersonPersonID, p.FullName
        ORDER BY Revenue DESC, LineCount DESC;

        ----------------------------------------------------------------------
        -- Q3: Customer history for the same hot stock item
        ----------------------------------------------------------------------
        SELECT TOP (200)
            /* POC_READ_Q3 */
            o.OrderID,
            o.OrderDate,
            ol.OrderLineID,
            ol.Quantity,
            ol.UnitPrice
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        WHERE ol.StockItemID = @HotStockItemID
          AND o.CustomerID = @HotCustomerID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        ORDER BY o.OrderDate DESC, o.OrderID DESC;

        ----------------------------------------------------------------------
        -- Q4: Recent activity by salesperson, also aligned to OrderDate
        ----------------------------------------------------------------------
        SELECT TOP (200)
            /* POC_READ_Q4 */
            o.OrderID,
            o.OrderDate,
            o.SalespersonPersonID,
            ol.StockItemID,
            ol.Quantity,
            ol.UnitPrice
        FROM Sales.OrderLines AS ol
        INNER JOIN Sales.Orders AS o
            ON o.OrderID = ol.OrderID
        WHERE ol.StockItemID = @HotStockItemID
          AND o.SalespersonPersonID = @HotSalespersonID
          AND o.OrderDate BETWEEN @WindowStart AND @MaxOrderDate
        ORDER BY o.OrderDate DESC, o.OrderID DESC;

        SET @i += 1;
    END
END;
GO