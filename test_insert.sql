-- SQL Insert Script for SeasPathDB
-- Generated from 3DMaker Export

-- Insert Visualization_Coordinate (Points)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 85634.62, 51963.85, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 87196.25, 53513.94, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (3, 88743.15, 54961.1, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (4, 97857.32, 42477.3, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (5, 96337.09, 41011.88, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (6, 99418.72, 44009.46, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (7, 99924.47, 37398.34, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (8, 101292.04, 37394.91, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (9, 100171.72, 37229.15, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (10, 100457.81, 37140.24, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (11, 100757.4, 37139.49, 0.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (12, 101043.94, 37226.96, 0.0, '3D Visualisation');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

-- Insert Visualization_Edge (Lines)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (1, 7, 8);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

-- Insert Visualization_Curve (Curves)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 7, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 9, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (3, 2, 10, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (4, 3, 11, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (5, 4, 12, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (6, 5, 8, 1);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
