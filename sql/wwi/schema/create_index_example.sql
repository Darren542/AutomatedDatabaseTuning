CREATE NONCLUSTERED INDEX IX_POC_Orders_OrderDate
ON Sales.Orders (OrderDate)
INCLUDE (CustomerID, SalespersonPersonID, ExpectedDeliveryDate);
GO

CREATE NONCLUSTERED INDEX IX_POC_OrderLines_1  
ON [Sales].[OrderLines] ([StockItemID])  
INCLUDE ([OrderID], [Quantity], [UnitPrice]);
GO