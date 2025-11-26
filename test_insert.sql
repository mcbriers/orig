-- SQL Insert Script for SeasPathDB
-- Generated from 3DMaker Export

-- Clear existing data (order: Curves, Lines, Points)
DELETE FROM SeasPathDB.dbo.Visualization_Curve;
DELETE FROM SeasPathDB.dbo.Visualization_Edge;
DELETE FROM SeasPathDB.dbo.Visualization_Coordinate;

-- Insert Visualization_Coordinate (Points)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (1, 98196.56, 39178.05, 0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (2, 98196.56, 39178.05, 800.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (3, 98196.56, 39178.05, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (4, 96398.8, 40978.7, 0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (5, 96398.8, 40978.7, 250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (6, 85623.63, 52031.76, 250, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (7, 99907.64, 37424.18, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (8, 101320.31, 37415.05, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (9, 102998.78, 39077.19, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (10, 104542.25, 40574.8, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (11, 105627.28, 41625.14, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (12, 105652.62, 43004.37, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (13, 93929.69, 55037.31, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (14, 100161.34, 37245.19, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (15, 100456.99, 37150.35, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (16, 100767.47, 37148.34, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (17, 101064.31, 37239.35, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (18, 105798.13, 41873.0, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (19, 105890.24, 42159.61, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (20, 105895.77, 42460.6, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (21, 105814.26, 42750.4, 800, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (22, 85623.63, 52031.76, 500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (23, 96398.8, 40978.7, 500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (24, 85623.63, 52031.76, 750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (25, 96398.8, 40978.7, 750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (26, 85623.63, 52031.76, 1000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (27, 96398.8, 40978.7, 1000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (28, 85623.63, 52031.76, 1250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (29, 96398.8, 40978.7, 1250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (30, 85623.63, 52031.76, 1500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (31, 96398.8, 40978.7, 1500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (32, 85623.63, 52031.76, 1750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (33, 96398.8, 40978.7, 1750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (34, 85623.63, 52031.76, 2000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (35, 96398.8, 40978.7, 2000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (36, 85623.63, 52031.76, 2250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (37, 96398.8, 40978.7, 2250.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (38, 85623.63, 52031.76, 2500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (39, 96398.8, 40978.7, 2500.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (40, 85623.63, 52031.76, 2750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (41, 96398.8, 40978.7, 2750.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (42, 85623.63, 52031.76, 3000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (43, 96398.8, 40978.7, 3000.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (44, 98196.56, 39178.05, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (45, 99907.64, 37424.18, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (46, 100161.34, 37245.19, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (47, 99907.64, 37424.18, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (48, 101320.31, 37415.05, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (49, 101320.31, 37415.05, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (50, 102998.78, 39077.19, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (51, 102998.78, 39077.19, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (52, 104542.25, 40574.8, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (53, 104542.25, 40574.8, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (54, 105627.28, 41625.14, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (55, 105890.24, 42159.61, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (56, 105627.28, 41625.14, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (57, 105652.62, 43004.37, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (58, 105652.62, 43004.37, 1600.0, '3D Visualisation');
INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES (59, 93929.69, 55037.31, 1600.0, '3D Visualisation');
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;

-- Insert Visualization_Edge (Lines)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (1, 6, 5);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (2, 4, 1);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (3, 2, 7);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (5, 8, 9);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (6, 9, 10);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (7, 10, 11);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (9, 12, 13);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (10, 22, 23);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (11, 24, 25);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (12, 26, 27);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (13, 28, 29);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (14, 30, 31);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (15, 32, 33);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (16, 34, 35);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (17, 36, 37);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (18, 38, 39);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (19, 40, 41);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (20, 42, 43);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (21, 44, 45);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (22, 47, 48);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (23, 49, 50);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (24, 51, 52);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (25, 53, 54);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (26, 56, 57);
INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES (27, 58, 59);
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;

-- Insert Visualization_Curve (Curves)
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;
SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;
