-- SQL Insert Script for SeasPathDB
-- Generated from 3DMaker Export

-- Insert Visualization_Coordinate (Points)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 99924.47, 0.0, 37398.34, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 99670.76, 0.0, 39365.45, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (3, 100162.15, 0.0, 39942.3, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (4, 100260.34, 0.0, 38815.61, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (5, 100692.28, 0.0, 39299.03, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (6, 101337.2, 0.0, 37421.25, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (7, 100180.76, 0.0, 37220.26, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (8, 100479.32, 0.0, 37129.37, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (9, 100791.37, 0.0, 37134.43, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (10, 101086.82, 0.0, 37234.95, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (11, 102918.21, 0.0, 40540.5, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (12, 104501.08, 0.0, 40543.37, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (13, 103197.99, 0.0, 40323.34, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (14, 103533.16, 0.0, 40208.88, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (15, 103887.33, 0.0, 40209.52, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (16, 104222.08, 0.0, 40325.2, '3D Visualisation');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

-- Insert Visualization_Edge (Lines)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (1, 2, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (2, 4, 5);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (3, 1, 6);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (4, 11, 12);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

-- Insert Visualization_Curve (Curves)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 1, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 7, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (3, 2, 8, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (4, 3, 9, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (5, 4, 10, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (6, 5, 6, 3);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (7, 0, 11, 4);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (8, 1, 13, 4);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (9, 2, 14, 4);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (10, 3, 15, 4);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (11, 4, 16, 4);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (12, 5, 12, 4);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
