-- SQL Insert Script for SeasPathDB
-- Generated from 3D Maker Digitizer

-- Clear existing data (order: Curves, Lines, Points)
DELETE FROM SeasPathDB.dbo.Visualization_Curve;
DELETE FROM SeasPathDB.dbo.Visualization_Edge;
DELETE FROM SeasPathDB.dbo.Visualization_Coordinate;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 100, 200, 0, 'p1');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 300, 400, 50, 'p2');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (10, 1, 2);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

INSERT INTO SeasPathDB.dbo.Visualization_Curve (PositionNumber, CoordinateId, EdgeId) VALUES (0, 1, 10); -- Z:0\n