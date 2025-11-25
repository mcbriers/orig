-- SQL Insert Script for SeasPathDB
-- Generated from Digitizer Export

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 10, 20, '0', 'A');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 100, 200, '0', 'B');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (3, 30, 50, '0', 'auto-created arc point');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (4, 60, 80, '0', 'auto-created arc point');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (5, 90, 120, '0', 'auto-created arc point');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (1, 1, 2);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 1, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 3, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (3, 2, 4, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (4, 3, 5, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (5, 4, 2, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (6, 5, 2, 1);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
