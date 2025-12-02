"""
Business logic operations for points, lines, and curves.
Separated from UI for testability and reusability.
"""
from typing import List, Optional, Tuple
from .models import ProjectData, Point, Line, Curve
from .geometry import GeometryEngine
import numpy as np


class Operations:
    """Handles creation, duplication, and deletion of entities."""
    
    def __init__(self, project: ProjectData, geometry: GeometryEngine):
        self.project = project
        self.geometry = geometry
    
    # ==================== POINT OPERATIONS ====================
    
    def create_point(self, pdf_x: float, pdf_y: float, z: float, 
                    description: str = "3D Visualisation") -> Point:
        """Create a new point from PDF coordinates."""
        real_x, real_y = self.geometry.transform_point(pdf_x, pdf_y)
        point_id = self.project.allocate_point_id()
        
        point = Point(
            id=point_id,
            real_x=int(round(real_x)),
            real_y=int(round(real_y)),
            z=int(round(z)),
            pdf_x=pdf_x,
            pdf_y=pdf_y,
            description=description
        )
        self.project.points.append(point)
        self.project.modified = True
        return point
    
    def duplicate_point(self, source_point: Point, new_z: float) -> Point:
        """Duplicate a point with a new Z value."""
        return self.create_point(
            source_point.pdf_x,
            source_point.pdf_y,
            new_z,
            source_point.description
        )
    
    def delete_point(self, point_id: int, force: bool = False) -> Tuple[bool, str]:
        """
        Delete a point. Returns (success, message).
        If force=False, prevents deletion if point is referenced.
        """
        point = self.project.get_point(point_id)
        if not point:
            return False, "Point not found"
        
        if not force:
            refs = self.project.count_point_references(point_id)
            if refs > 0:
                return False, f"Point is referenced by {refs} line(s)/curve(s)"
        
        self.project.points.remove(point)
        self.project.deletion_log.append({
            'type': 'point',
            'id': point_id,
            'data': point.to_dict()
        })
        self.project.modified = True
        return True, "Point deleted"
    
    # ==================== LINE OPERATIONS ====================
    
    def create_line(self, start_id: int, end_id: int, 
                   description: str = "") -> Optional[Line]:
        """Create a new line between two points."""
        # Validate points exist
        if not self.project.get_point(start_id):
            return None
        if not self.project.get_point(end_id):
            return None
        
        # Prevent zero-length lines
        if start_id == end_id:
            return None
        
        line_id = self.project.allocate_line_id()
        line = Line(
            id=line_id,
            start_id=start_id,
            end_id=end_id,
            description=description
        )
        self.project.lines.append(line)
        self.project.modified = True
        return line
    
    def duplicate_line(self, source_line: Line, point_id_map: dict) -> Optional[Line]:
        """
        Duplicate a line using a mapping of old point IDs to new point IDs.
        point_id_map: {old_point_id: new_point_id}
        """
        new_start = point_id_map.get(source_line.start_id)
        new_end = point_id_map.get(source_line.end_id)
        
        if not new_start or not new_end:
            return None
        
        return self.create_line(new_start, new_end, source_line.description)
    
    def delete_line(self, line_id: int) -> Tuple[bool, str]:
        """Delete a line."""
        line = self.project.get_line(line_id)
        if not line:
            return False, "Line not found"
        
        self.project.lines.remove(line)
        self.project.deletion_log.append({
            'type': 'line',
            'id': line_id,
            'data': line.to_dict()
        })
        self.project.modified = True
        return True, "Line deleted"
    
    # ==================== CURVE OPERATIONS ====================
    
    def create_curve(self, start_id: int, end_id: int, center_id: int,
                    num_interior_points: int = 4) -> Optional[Curve]:
        """
        Create a curve from start -> center -> end with interpolated points.
        """
        start_pt = self.project.get_point(start_id)
        center_pt = self.project.get_point(center_id)
        end_pt = self.project.get_point(end_id)
        
        if not all([start_pt, center_pt, end_pt]):
            return None
        
        # Calculate arc points
        arc_points_real = self._calculate_arc_points(
            start_pt, center_pt, end_pt, num_interior_points
        )
        
        if not arc_points_real:
            return None
        
        curve_id = self.project.allocate_curve_id()
        curve = Curve(
            id=curve_id,
            start_id=start_id,
            end_id=end_id,
            arc_point_ids=[center_id],  # Store center point for reference
            arc_points_real=arc_points_real
        )
        self.project.curves.append(curve)
        self.project.modified = True
        return curve
    
    def _calculate_arc_points(self, start: Point, center: Point, end: Point,
                             num_interior: int) -> List[Tuple[float, float, float]]:
        """Calculate interpolated points along a circular arc."""
        # Get real coordinates
        start_pos = (start.real_x, start.real_y, start.z)
        center_pos = (center.real_x, center.real_y, center.z)
        end_pos = (end.real_x, end.real_y, end.z)
        
        # Calculate angles
        start_angle = self.geometry.angle_from_center(center_pos, start_pos)
        end_angle = self.geometry.angle_from_center(center_pos, end_pos)
        
        # Calculate radius (use 2D distance)
        radius = self.geometry.distance_2d(center_pos[:2], start_pos[:2])
        
        # Determine arc direction
        angle_diff = (end_angle - start_angle) % 360
        if angle_diff > 180:
            angle_diff -= 360
        
        # Generate points
        arc_points = [start_pos]
        
        for i in range(1, num_interior + 2):
            t = i / (num_interior + 2)
            angle = start_angle + t * angle_diff
            angle_rad = np.radians(angle)
            
            x = center_pos[0] + radius * np.cos(angle_rad)
            y = center_pos[1] + radius * np.sin(angle_rad)
            z = start_pos[2] + t * (end_pos[2] - start_pos[2])  # Linear Z interpolation
            
            arc_points.append((int(round(x)), int(round(y)), int(round(z))))
        
        arc_points.append(end_pos)
        return arc_points
    
    def duplicate_curve(self, source_curve: Curve, point_id_map: dict) -> Optional[Curve]:
        """
        Duplicate a curve using a mapping of old point IDs to new point IDs.
        Recalculates arc_points_real from the new points.
        """
        new_start_id = point_id_map.get(source_curve.start_id)
        new_end_id = point_id_map.get(source_curve.end_id)
        
        if not new_start_id or not new_end_id:
            return None
        
        # Find center point (first in arc_point_ids)
        if not source_curve.arc_point_ids:
            return None
        
        old_center_id = source_curve.arc_point_ids[0]
        new_center_id = point_id_map.get(old_center_id)
        
        if not new_center_id:
            return None
        
        # Recreate curve with recalculated arc
        num_interior = len(source_curve.arc_points_real) - 2  # Subtract start and end
        return self.create_curve(new_start_id, new_end_id, new_center_id, num_interior)
    
    def delete_curve(self, curve_id: int, remove_orphans: bool = True) -> Tuple[bool, str]:
        """
        Delete a curve. If remove_orphans=True, deletes unreferenced arc points.
        """
        curve = self.project.get_curve(curve_id)
        if not curve:
            return False, "Curve not found"
        
        # Track arc points for orphan cleanup
        arc_point_ids = curve.arc_point_ids.copy()
        
        self.project.curves.remove(curve)
        self.project.deletion_log.append({
            'type': 'curve',
            'id': curve_id,
            'data': curve.to_dict()
        })
        
        # Remove orphan arc points
        if remove_orphans:
            orphans_removed = 0
            for point_id in arc_point_ids:
                if self.project.count_point_references(point_id) == 0:
                    success, _ = self.delete_point(point_id, force=True)
                    if success:
                        orphans_removed += 1
            
            msg = f"Curve deleted ({orphans_removed} orphan points removed)"
        else:
            msg = "Curve deleted"
        
        self.project.modified = True
        return True, msg

    def delete_points_bulk(self, point_ids: List[int]) -> Tuple[int, List[str]]:
        """
        Optimized bulk deletion of multiple points with cascade cleanup.
        Returns (deleted_points_count, summary_list_of_deleted_items).
        This avoids repeated full scans by building maps once and performing
        a closure calculation.
        """
        # Normalize input
        initial = set(pid for pid in point_ids if self.project.get_point(pid))
        if not initial:
            return 0, []

        # Build maps
        point_lines = {}
        point_curves = {}
        for p in self.project.points:
            point_lines[p.id] = []
            point_curves[p.id] = []

        for line in self.project.lines:
            if line.hidden:
                continue
            point_lines.setdefault(line.start_id, []).append(line)
            point_lines.setdefault(line.end_id, []).append(line)

        for curve in self.project.curves:
            if curve.hidden:
                continue
            # Count arc point references and endpoint refs
            for pid in curve.arc_point_ids:
                point_curves.setdefault(pid, []).append(curve)
            point_curves.setdefault(curve.start_id, []).append(curve)
            point_curves.setdefault(curve.end_id, []).append(curve)

        # Initial reference counts (mirrors count_point_references semantics)
        ref_count = {p.id: 0 for p in self.project.points}
        for line in self.project.lines:
            if line.hidden:
                continue
            ref_count[line.start_id] = ref_count.get(line.start_id, 0) + 1
            ref_count[line.end_id] = ref_count.get(line.end_id, 0) + 1
        for curve in self.project.curves:
            if curve.hidden:
                continue
            for pid in curve.arc_point_ids:
                ref_count[pid] = ref_count.get(pid, 0) + 1
            # If not in arc_point_ids, count start/end once each
            if curve.start_id not in curve.arc_point_ids:
                ref_count[curve.start_id] = ref_count.get(curve.start_id, 0) + 1
            if curve.end_id not in curve.arc_point_ids:
                ref_count[curve.end_id] = ref_count.get(curve.end_id, 0) + 1

        # Work queue for deletion closure
        from collections import deque
        queue = deque(initial)
        to_delete_points = set()
        to_delete_lines = set()
        to_delete_curves = set()

        while queue:
            pid = queue.popleft()
            if pid in to_delete_points:
                continue
            to_delete_points.add(pid)

            # Schedule connected lines for deletion
            for line in point_lines.get(pid, []):
                if line.id in to_delete_lines:
                    continue
                to_delete_lines.add(line.id)
                # decrement ref count for the other endpoint
                other = line.start_id if line.end_id == pid else line.end_id
                ref_count[other] = max(0, ref_count.get(other, 0) - 1)
                if ref_count.get(other, 0) == 0 and other not in to_delete_points:
                    queue.append(other)

            # Schedule connected curves for deletion
            for curve in point_curves.get(pid, []):
                if curve.id in to_delete_curves:
                    continue
                to_delete_curves.add(curve.id)
                # decrement ref counts for points referenced by this curve
                # arc_point_ids counted once per curve
                for rid in set(curve.arc_point_ids):
                    ref_count[rid] = max(0, ref_count.get(rid, 0) - 1)
                    if ref_count.get(rid, 0) == 0 and rid not in to_delete_points:
                        queue.append(rid)
                # start/end also counted unless already in arc_point_ids
                for rid in (curve.start_id, curve.end_id):
                    if rid not in curve.arc_point_ids:
                        ref_count[rid] = max(0, ref_count.get(rid, 0) - 1)
                        if ref_count.get(rid, 0) == 0 and rid not in to_delete_points:
                            queue.append(rid)

        # Perform deletions on project lists and record summary
        deleted_items = []

        # Remove lines
        remaining_lines = []
        for line in self.project.lines:
            if line.id in to_delete_lines:
                self.project.deletion_log.append({'type': 'line', 'id': line.id, 'data': line.to_dict()})
                deleted_items.append(f"Line {line.id}")
            else:
                remaining_lines.append(line)
        self.project.lines = remaining_lines

        # Remove curves
        remaining_curves = []
        for curve in self.project.curves:
            if curve.id in to_delete_curves:
                self.project.deletion_log.append({'type': 'curve', 'id': curve.id, 'data': curve.to_dict()})
                deleted_items.append(f"Curve {curve.id}")
            else:
                remaining_curves.append(curve)
        self.project.curves = remaining_curves

        # Remove points
        remaining_points = []
        for point in self.project.points:
            if point.id in to_delete_points:
                self.project.deletion_log.append({'type': 'point', 'id': point.id, 'data': point.to_dict()})
                deleted_items.append(f"Point {point.id}")
            else:
                remaining_points.append(point)
        self.project.points = remaining_points

        self.project.modified = True
        return len(to_delete_points), deleted_items
