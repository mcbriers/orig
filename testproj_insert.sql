-- SQL Insert Script for SeasPathDB
-- Generated from Digitizer Export

-- Clear existing data (order: Curves, Lines, Points)
DELETE FROM SeasPathDB.dbo.Visualization_Curve;
DELETE FROM SeasPathDB.dbo.Visualization_Edge;
DELETE FROM SeasPathDB.dbo.Visualization_Coordinate;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 10, 20, '0', 'p1');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 30, 40, '0', 'p2');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (100, 1, 2);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 1, 100);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 2, 100);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
