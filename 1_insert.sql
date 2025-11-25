-- SQL Insert Script for SeasPathDB
-- Generated from 3DMaker Export

-- Insert Visualization_Coordinate (Points)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 99857.94, 0.0, 37457.46, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 101305.54, 0.0, 37399.22, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (3, 100111.86, 0.0, 37265.44, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (4, 100411.57, 0.0, 37158.12, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (5, 100729.66, 0.0, 37145.33, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (6, 101037.02, 0.0, 37228.22, '3D Visualisation');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

-- Insert Visualization_Edge (Lines)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

-- Insert Visualization_Curve (Curves)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 3, 0);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 4, 0);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (3, 2, 5, 0);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (4, 3, 6, 0);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
