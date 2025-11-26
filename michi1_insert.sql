-- SQL Insert Script for SeasPathDB
-- Generated from 3DMaker Export

-- Clear existing data (order: Curves, Lines, Points)
DELETE FROM SeasPathDB.dbo.Visualization_Curve;
DELETE FROM SeasPathDB.dbo.Visualization_Edge;
DELETE FROM SeasPathDB.dbo.Visualization_Coordinate;

-- Insert Visualization_Coordinate (Points)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (46, 85241.93, 52082.56, 187, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (47, 96208.64, 40696.25, 187, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (48, 85241.93, 52082.56, 250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (49, 96208.64, 40696.25, 250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (50, 85241.93, 52082.56, 500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (51, 96208.64, 40696.25, 500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (52, 85241.93, 52082.56, 750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (53, 96208.64, 40696.25, 750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (54, 85241.93, 52082.56, 1000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (55, 96208.64, 40696.25, 1000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (56, 85241.93, 52082.56, 1250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (57, 96208.64, 40696.25, 1250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (58, 85241.93, 52082.56, 1500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (59, 96208.64, 40696.25, 1500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (60, 85241.93, 52082.56, 1820.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (61, 96208.64, 40696.25, 1820.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (62, 85241.93, 52082.56, 2070.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (63, 96208.64, 40696.25, 2070.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (64, 85241.93, 52082.56, 2320.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (65, 96208.64, 40696.25, 2320.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (66, 85241.93, 52082.56, 2570.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (67, 96208.64, 40696.25, 2570.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (68, 85241.93, 52082.56, 2820.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (69, 96208.64, 40696.25, 2820.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (70, 85241.93, 52082.56, 3070.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (71, 96208.64, 40696.25, 3070.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (72, 85241.93, 52082.56, 3320.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (73, 96208.64, 40696.25, 3320.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (74, 99928.17, 37407.27, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (75, 101305.43, 37390.26, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (76, 100174.95, 37232.72, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (77, 100462.45, 37139.36, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (78, 100764.7, 37135.63, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (79, 101054.41, 37221.86, 800, '3D Visualisation');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

-- Insert Visualization_Edge (Lines)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (23, 46, 47);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (24, 48, 49);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (25, 50, 51);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (26, 52, 53);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (27, 54, 55);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (28, 56, 57);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (29, 58, 59);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (30, 60, 61);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (31, 62, 63);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (32, 64, 65);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (33, 66, 67);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (34, 68, 69);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (35, 70, 71);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (36, 72, 73);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (37, 74, 75);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

-- Insert Visualization_Curve (Curves)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (1, 0, 74, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (2, 1, 76, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (3, 2, 77, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (4, 3, 78, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (5, 4, 79, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES (6, 5, 75, 37);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
