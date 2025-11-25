"""
Exporter utility to write Points, Lines and Curves to CSV and an SQL file matching required formats.
Assumes the project data is canonical (migration/validation already applied).
- Points CSV: header `ID,X,Y,Z,Description` (X,Y exported as integers)
- Lines CSV: header `LineID,StartPointID,EndPointID`
- Curves CSV: header `Position,PointID,LineID` (exactly N positions per curve)
- SQL: writes inserts in order: points, lines, curves
"""
import os
import csv
from typing import Dict, Any


def export_project(project: Dict[str, Any], export_dir: str, project_name: str):
    os.makedirs(export_dir, exist_ok=True)
    points_file = os.path.join(export_dir, f"{project_name}_points.txt")
    lines_file = os.path.join(export_dir, f"{project_name}_lines.txt")
    curves_file = os.path.join(export_dir, f"{project_name}_curves.txt")
    sql_file = os.path.join(export_dir, f"{project_name}_insert.sql")

    points = project.get('points', [])
    lines = project.get('lines', [])
    curves = project.get('curves', [])
    # Total positions per curve
    interior = int(project.get('curve_interior_points', 4))
    total_positions = interior + 2

    # Points CSV
    with open(points_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'X', 'Y', 'Z', 'Description'])
        for p in points:
            # X/Y exported as integers (round)
            rx = int(round(float(p.get('real_x', 0.0))))
            ry = int(round(float(p.get('real_y', 0.0))))
            z = p.get('z', '')
            desc = p.get('description', '')
            writer.writerow([p['id'], rx, ry, z, desc])

    # Lines CSV
    with open(lines_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['LineID', 'StartPointID', 'EndPointID'])
        for l in lines:
            writer.writerow([l['id'], l['start_id'], l['end_id']])

    # Curves CSV
    with open(curves_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Position', 'PointID', 'LineID'])
        for c in curves:
            base_line = c.get('base_line_id', 0)
            ids = c.get('arc_point_ids', [])
            # Ensure exactly total_positions rows
            for pos in range(total_positions):
                pid = ids[pos] if pos < len(ids) else (ids[-1] if ids else 0)
                writer.writerow([pos, pid, base_line])

    # SQL file
    with open(sql_file, 'w', newline='') as f:
        f.write("-- SQL Insert Script for SeasPathDB\n")
        f.write("-- Generated from Digitizer Export\n\n")

        # Points
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;\n")
        for p in points:
            rx = int(round(float(p.get('real_x', 0.0))))
            ry = int(round(float(p.get('real_y', 0.0))))
            z = p.get('z', '')
            f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) VALUES ({p['id']}, {rx}, {ry}, '{z}', '{p.get('description','')}');\n")
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;\n\n")

        # Lines
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;\n")
        for l in lines:
            f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) VALUES ({l['id']}, {l['start_id']}, {l['end_id']});\n")
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;\n\n")

        # Curves
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;\n")
        row_id = 1
        for c in curves:
            base_line = c.get('base_line_id', 0)
            ids = c.get('arc_point_ids', [])
            for pos in range(total_positions):
                pid = ids[pos] if pos < len(ids) else (ids[-1] if ids else 0)
                f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) VALUES ({row_id}, {pos}, {pid}, {base_line});\n")
                row_id += 1
        f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;\n")

    return {'points_file': points_file, 'lines_file': lines_file, 'curves_file': curves_file, 'sql_file': sql_file}
