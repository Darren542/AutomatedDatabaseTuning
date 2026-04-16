USE [WideWorldImporters];
GO

CREATE OR ALTER PROCEDURE dbo.usp_POC_WriteHeavy_Workload
    @Iterations INT = 10,
    @OrdersPerIteration INT = 25,
    @RollbackChanges BIT = 1
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @i INT = 1;

    DECLARE @LastEditedBy INT =
    (
        SELECT TOP (1) p.PersonID
        FROM Application.People AS p
        WHERE p.IsEmployee = 1
        ORDER BY p.PersonID
    );

    DECLARE @SalespersonPersonID INT =
    (
        SELECT TOP (1) p.PersonID
        FROM Application.People AS p
        WHERE p.IsSalesperson = 1
        ORDER BY p.PersonID
    );

    DECLARE @CustomerID INT =
    (
        SELECT TOP (1) c.CustomerID
        FROM Sales.Customers AS c
        ORDER BY c.CustomerID
    );

    DECLARE @ContactPersonID INT =
    (
        SELECT c.PrimaryContactPersonID
        FROM Sales.Customers AS c
        WHERE c.CustomerID = @CustomerID
    );

    DECLARE @BaseOrderDate DATE =
    (
        SELECT MAX(o.OrderDate)
        FROM Sales.Orders AS o
    );

    WHILE @i <= @Iterations
    BEGIN
        BEGIN TRAN;

        DECLARE @NewOrders TABLE
        (
            OrderID INT PRIMARY KEY
        );

        ;WITH n AS
        (
            SELECT TOP (@OrdersPerIteration)
                ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn
            FROM sys.all_objects
        )
        INSERT INTO Sales.Orders
        (
            CustomerID,
            SalespersonPersonID,
            PickedByPersonID,
            ContactPersonID,
            BackorderOrderID,
            OrderDate,
            ExpectedDeliveryDate,
            CustomerPurchaseOrderNumber,
            IsUndersupplyBackordered,
            Comments,
            DeliveryInstructions,
            InternalComments,
            PickingCompletedWhen,
            LastEditedBy
        )
        OUTPUT inserted.OrderID INTO @NewOrders(OrderID)
        SELECT
            @CustomerID,
            @SalespersonPersonID,
            NULL,
            @ContactPersonID,
            NULL,
            DATEADD(DAY, -(rn % 7), @BaseOrderDate),
            DATEADD(DAY, 1 + (rn % 7), @BaseOrderDate),
            CONCAT(N'POC-', @i, N'-', rn),
            0,
            N'POC write-heavy workload order',
            N'POC delivery instructions',
            N'POC internal comments',
            NULL,
            @LastEditedBy
        FROM n;

        ;WITH StockSample AS
        (
            SELECT TOP (3)
                si.StockItemID,
                si.StockItemName,
                si.UnitPackageID,
                si.TaxRate,
                si.UnitPrice,
                ROW_NUMBER() OVER (ORDER BY si.StockItemID) AS rn
            FROM Warehouse.StockItems AS si
            WHERE si.UnitPrice IS NOT NULL
            ORDER BY si.StockItemID
        )
        INSERT INTO Sales.OrderLines
        (
            OrderID,
            StockItemID,
            Description,
            PackageTypeID,
            Quantity,
            UnitPrice,
            TaxRate,
            PickedQuantity,
            PickingCompletedWhen,
            LastEditedBy
        )
        SELECT
            o.OrderID,
            s.StockItemID,
            s.StockItemName,
            s.UnitPackageID,
            1 + ((o.OrderID + s.rn) % 10),
            s.UnitPrice,
            s.TaxRate,
            0,
            NULL,
            @LastEditedBy
        FROM @NewOrders AS o
        CROSS JOIN StockSample AS s;

        ----------------------------------------------------------------------
        -- Update a subset of the newly inserted orders
        ----------------------------------------------------------------------
        ;WITH TargetOrders AS
        (
            SELECT TOP (10) n.OrderID
            FROM @NewOrders AS n
            ORDER BY n.OrderID
        )
        UPDATE o
        SET
            o.Comments = CONCAT(ISNULL(o.Comments, N''), N' [updated]'),
            o.ExpectedDeliveryDate = DATEADD(DAY, 1, o.ExpectedDeliveryDate),
            o.LastEditedBy = @LastEditedBy
        FROM Sales.Orders AS o
        INNER JOIN TargetOrders AS t
            ON t.OrderID = o.OrderID;

        ----------------------------------------------------------------------
        -- Update a subset of the newly inserted order lines
        ----------------------------------------------------------------------
        ;WITH TargetLines AS
        (
            SELECT TOP (30) ol.OrderLineID
            FROM Sales.OrderLines AS ol
            INNER JOIN @NewOrders AS n
                ON n.OrderID = ol.OrderID
            ORDER BY ol.OrderLineID
        )
        UPDATE ol
        SET
            ol.PickedQuantity =
                CASE
                    WHEN ol.PickedQuantity < ol.Quantity THEN ol.PickedQuantity + 1
                    ELSE ol.PickedQuantity
                END,
            ol.PickingCompletedWhen =
                CASE
                    WHEN ol.PickedQuantity + 1 >= ol.Quantity THEN SYSUTCDATETIME()
                    ELSE ol.PickingCompletedWhen
                END,
            ol.LastEditedBy = @LastEditedBy
        FROM Sales.OrderLines AS ol
        INNER JOIN TargetLines AS t
            ON t.OrderLineID = ol.OrderLineID;

        ----------------------------------------------------------------------
        -- Delete a small subset to create delete pressure
        ----------------------------------------------------------------------
        ;WITH DoomedOrders AS
        (
            SELECT TOP (5) n.OrderID
            FROM @NewOrders AS n
            ORDER BY n.OrderID DESC
        )
        DELETE ol
        FROM Sales.OrderLines AS ol
        INNER JOIN DoomedOrders AS d
            ON d.OrderID = ol.OrderID;

        ;WITH DoomedOrders AS
        (
            SELECT TOP (5) n.OrderID
            FROM @NewOrders AS n
            ORDER BY n.OrderID DESC
        )
        DELETE o
        FROM Sales.Orders AS o
        INNER JOIN DoomedOrders AS d
            ON d.OrderID = o.OrderID;

        IF @RollbackChanges = 1
            ROLLBACK TRAN;
        ELSE
            COMMIT TRAN;

        SET @i += 1;
    END
END;
GO