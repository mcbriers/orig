"""
Business logic operations for points, lines, and curves.
Separated from UI for testability and reusability.
"""
from typing import List, Optional, Tuple
from .models import ProjectData, Point, Line, Curve
from .geometry import GeometryEngine
import math
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
        duplicate = self.create_point(
            source_point.pdf_x,
            source_point.pdf_y,
            new_z,
            source_point.description
        )
        duplicate.hidden = source_point.hidden
        return duplicate
    
    def delete_point(self, point_id: int, force: bool = False, cascade: bool = True) -> Tuple[bool, str]:
        """
        Delete a point. Returns (success, message).
        
        Args:
            point_id: ID of point to delete
            force: If False, prevents deletion if point is referenced (unless cascade=True)
            cascade: If True, cascade delete dependent lines/curves as units to avoid orphans
        """
        point = self.project.get_point(point_id)
        if not point:
            return False, "Point not found"
        
        if not force and not cascade:
            refs = self.project.count_point_references(point_id)
            if refs > 0:
                return False, f"Point is referenced by {refs} line(s)/curve(s)"
        
        # If cascade, delete all dependent lines and curves as units
        if cascade and not force:
            deleted_items = []
            
            # Find and delete lines that use this point
            lines_to_delete = [line for line in self.project.lines 
                             if line.start_id == point_id or line.end_id == point_id]
            for line in lines_to_delete:
                self.project.lines.remove(line)
                self.project.deletion_log.append({
                    'type': 'line',
                    'id': line.id,
                    'data': line.to_dict()
                })
                deleted_items.append(f"Line {line.id}")
            
            # Find and delete curves that use this point as start/end
            curves_to_delete = [curve for curve in self.project.curves 
                              if curve.start_id == point_id or curve.end_id == point_id]
            for curve in curves_to_delete:
                # Also delete orphaned arc points
                arc_point_ids = curve.arc_point_ids.copy()
                self.project.curves.remove(curve)
                self.project.deletion_log.append({
                    'type': 'curve',
                    'id': curve.id,
                    'data': curve.to_dict()
                })
                deleted_items.append(f"Curve {curve.id}")
                
                # Remove orphan arc points that are no longer referenced
                for arc_pid in arc_point_ids:
                    if arc_pid != point_id and self.project.count_point_references(arc_pid) == 0:
                        arc_point = self.project.get_point(arc_pid)
                        if arc_point:
                            self.project.points.remove(arc_point)
                            self.project.deletion_log.append({
                                'type': 'point',
                                'id': arc_pid,
                                'data': arc_point.to_dict()
                            })
            
            message = f"Point deleted (cascaded: {', '.join(deleted_items)})" if deleted_items else "Point deleted"
        else:
            message = "Point deleted"
        
        self.project.points.remove(point)
        self.project.deletion_log.append({
            'type': 'point',
            'id': point_id,
            'data': point.to_dict()
        })
        self.project.modified = True
        return True, message
    
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
    
    def create_curve(
        self,
        start_id: int,
        end_id: int,
        arc_point_id: int,
        num_interior_points: int = 4,
        base_line_id: Optional[int] = None,
        arc_point_ids_override: Optional[List[int]] = None,
        arc_points_real_override: Optional[List[Tuple[float, float, float]]] = None
    ) -> Optional[Curve]:
        """Create a curve and ensure its base line and arc sample points exist."""

        start_pt = self.project.get_point(start_id)
        arc_pt = self.project.get_point(arc_point_id)
        end_pt = self.project.get_point(end_id)

        if not all([start_pt, arc_pt, end_pt]):
            return None

        if arc_point_ids_override is not None:
            num_interior_points = max(len(arc_point_ids_override), 1)

        arc_points_real = arc_points_real_override or self._calculate_arc_points(
            start_pt, arc_pt, end_pt, num_interior_points
        )

        if not arc_points_real or len(arc_points_real) < 3:
            return None

        interior_real = arc_points_real[1:-1]

        if arc_point_ids_override is None:
            arc_point_ids = self._generate_arc_sample_points(interior_real, arc_pt)
        else:
            arc_point_ids = arc_point_ids_override
            for pid in arc_point_ids:
                point = self.project.get_point(pid)
                if point:
                    point.hidden = False

        if not arc_point_ids:
            return None

        if len(arc_point_ids) != len(interior_real):
            return None

        base_line = None
        if base_line_id is not None:
            base_line = self.project.get_line(base_line_id)
        else:
            base_line = self._create_base_line(start_id, end_id)
            base_line_id = base_line.id if base_line else None

        curve_id = self.project.allocate_curve_id()
        curve = Curve(
            id=curve_id,
            start_id=start_id,
            end_id=end_id,
            arc_point_ids=arc_point_ids,
            arc_points_real=arc_points_real,
            base_line_id=base_line_id
        )

        self.project.curves.append(curve)
        self.project.modified = True

        self._ensure_curve_metadata(curve)
        return curve
    
    def _calculate_arc_points(self, start: Point, via: Point, end: Point,
                             num_interior: int) -> List[Tuple[float, float, float]]:
        """Calculate interpolated points for the arc defined by start, via, end."""
        start_pos = np.array([start.real_x, start.real_y, start.z], dtype=float)
        via_pos = np.array([via.real_x, via.real_y, via.z], dtype=float)
        end_pos = np.array([end.real_x, end.real_y, end.z], dtype=float)

        start_xy = start_pos[:2]
        via_xy = via_pos[:2]
        end_xy = end_pos[:2]

        # Ensure the three points are not colinear
        det = (start_xy[0] * (via_xy[1] - end_xy[1]) +
               via_xy[0] * (end_xy[1] - start_xy[1]) +
               end_xy[0] * (start_xy[1] - via_xy[1]))
        if abs(det) < 1e-6:
            return []

        temp_via = np.dot(via_xy, via_xy)
        bc = (np.dot(start_xy, start_xy) - temp_via) / 2.0
        cd = (temp_via - np.dot(end_xy, end_xy)) / 2.0

        denom = ((start_xy[0] - via_xy[0]) * (via_xy[1] - end_xy[1]) -
             (via_xy[0] - end_xy[0]) * (start_xy[1] - via_xy[1]))
        if abs(denom) < 1e-6:
            return []

        center_x = (bc * (via_xy[1] - end_xy[1]) - cd * (start_xy[1] - via_xy[1])) / denom
        center_y = ((start_xy[0] - via_xy[0]) * cd - (via_xy[0] - end_xy[0]) * bc) / denom
        radius = math.hypot(start_xy[0] - center_x, start_xy[1] - center_y)
        if radius < 1e-6:
            return []

        start_angle = math.atan2(start_xy[1] - center_y, start_xy[0] - center_x)
        via_angle = math.atan2(via_xy[1] - center_y, via_xy[0] - center_x)
        end_angle = math.atan2(end_xy[1] - center_y, end_xy[0] - center_x)

        two_pi = 2.0 * math.pi
        start_angle_n = start_angle % two_pi
        via_angle_n = via_angle % two_pi
        end_angle_n = end_angle % two_pi

        ccw_delta = (end_angle_n - start_angle_n) % two_pi
        via_delta = (via_angle_n - start_angle_n) % two_pi

        if via_delta <= ccw_delta + 1e-6:
            total_angle = ccw_delta
            via_progress = via_delta
        else:
            total_angle = ccw_delta - two_pi  # Negative => clockwise traversal
            via_progress = -((start_angle_n - via_angle_n) % two_pi)

        if abs(total_angle) < 1e-6:
            return []

        # Normalise via progress onto [0,1]
        via_fraction = max(1e-6, min(1.0 - 1e-6, via_progress / total_angle))

        samples = max(num_interior, 1)
        
        # Generate perfectly evenly-spaced fractions along the arc
        # The via point has already defined the arc's shape and direction,
        # so we don't need to force one sample point to match it exactly
        fractions = [i / (samples + 1) for i in range(1, samples + 1)]

        arc_points = [(int(round(start_pos[0])),
                   int(round(start_pos[1])),
                   int(round(start_pos[2])))]

        for fraction in fractions:
            angle = start_angle + fraction * total_angle
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            z = start_pos[2] + fraction * (end_pos[2] - start_pos[2])
            arc_points.append((int(round(x)), int(round(y)), int(round(z))))

        arc_points.append((int(round(end_pos[0])),
                   int(round(end_pos[1])),
                   int(round(end_pos[2]))))
        return arc_points
    
    def duplicate_curve(self, source_curve: Curve, point_id_map: dict) -> Optional[Curve]:
        """Duplicate a curve using a mapping of old point IDs to new point IDs."""

        new_start_id = point_id_map.get(source_curve.start_id)
        new_end_id = point_id_map.get(source_curve.end_id)

        if not new_start_id or not new_end_id:
            return None

        if not source_curve.arc_point_ids:
            return None

        new_arc_ids = []
        for pid in source_curve.arc_point_ids:
            mapped = point_id_map.get(pid)
            if not mapped:
                return None
            new_arc_ids.append(mapped)

        primary_arc_id = new_arc_ids[0]
        num_interior = max(len(source_curve.arc_points_real) - 2, len(new_arc_ids))

        source_base_hidden = False
        source_base_description = ""
        if source_curve.base_line_id:
            original_base_line = self.project.get_line(source_curve.base_line_id)
            if original_base_line:
                source_base_hidden = original_base_line.hidden
                source_base_description = original_base_line.description

        new_curve = self.create_curve(
            new_start_id,
            new_end_id,
            primary_arc_id,
            num_interior_points=num_interior,
            arc_point_ids_override=new_arc_ids
        )

        if new_curve:
            new_curve.hidden = source_curve.hidden
            new_curve.description = source_curve.description
            if new_curve.base_line_id:
                base_line = self.project.get_line(new_curve.base_line_id)
                if base_line:
                    base_line.hidden = source_base_hidden
                    if source_base_description:
                        base_line.description = source_base_description

            for pid in new_curve.arc_point_ids:
                point = self.project.get_point(pid)
                if point:
                    point.description = f"Curve {new_curve.id} arc sample"

        return new_curve

    def _create_base_line(self, start_id: int, end_id: int) -> Optional[Line]:
        """Create (or reuse) the base line for a curve."""
        line = self.create_line(start_id, end_id)
        if line:
            line.hidden = False
            return line

        existing = self._find_line_between(start_id, end_id)
        if existing:
            changed = False
            if existing.start_id != start_id or existing.end_id != end_id:
                existing.start_id = start_id
                existing.end_id = end_id
                changed = True
            if existing.hidden:
                existing.hidden = False
                changed = True
            if changed:
                self.project.modified = True
        return existing

    def _find_line_between(self, start_id: int, end_id: int) -> Optional[Line]:
        for line in self.project.lines:
            if ((line.start_id == start_id and line.end_id == end_id) or
                (line.start_id == end_id and line.end_id == start_id)):
                return line
        return None

    def _generate_arc_sample_points(self, interior_real: List[Tuple[float, float, float]], via_point: Point) -> List[int]:
        """
        Create point objects for the calculated arc interior positions.
        
        Note: via_point is not used here - it was only needed to calculate the arc geometry.
        Once the arc center/radius/direction are determined, the via point is redundant.
        We create new points at the calculated evenly-spaced positions.
        """
        arc_point_ids: List[int] = []
        created_point_ids: List[int] = []

        for real_x, real_y, real_z in interior_real:
            # Check if a point already exists at this location
            existing = self._find_point_by_real(real_x, real_y, real_z)
            if existing:
                existing.hidden = False
                arc_point_ids.append(existing.id)
                continue

            # Create new point at the calculated position
            created = self._create_point_from_real(real_x, real_y, real_z)
            if not created:
                self._remove_points(created_point_ids)
                return []
            created_point_ids.append(created.id)
            arc_point_ids.append(created.id)

        return arc_point_ids

    def _find_point_by_real(self, real_x: float, real_y: float, z: float, tolerance: float = 1.0) -> Optional[Point]:
        for point in self.project.points:
            if (abs(point.real_x - real_x) <= tolerance and
                abs(point.real_y - real_y) <= tolerance and
                abs(point.z - z) <= tolerance):
                return point
        return None

    def _create_point_from_real(self, real_x: float, real_y: float, z: float) -> Optional[Point]:
        pdf_coords = self.geometry.real_to_pdf(real_x, real_y)
        if pdf_coords is None:
            return None

        point_id = self.project.allocate_point_id()
        point = Point(
            id=point_id,
            real_x=int(round(real_x)),
            real_y=int(round(real_y)),
            z=int(round(z)),
            pdf_x=pdf_coords[0],
            pdf_y=pdf_coords[1],
            hidden=False,
            description="Curve Arc Sample"
        )
        self.project.points.append(point)
        self.project.modified = True
        return point

    def _remove_points(self, point_ids: List[int]) -> None:
        if not point_ids:
            return
        before = len(self.project.points)
        self.project.points = [p for p in self.project.points if p.id not in point_ids]
        if len(self.project.points) != before:
            self.project.modified = True

    def _coords_match(self, lhs: Tuple[float, float, float], rhs: Tuple[float, float, float], tolerance: float = 1.0) -> bool:
        return (abs(lhs[0] - rhs[0]) <= tolerance and
                abs(lhs[1] - rhs[1]) <= tolerance and
                abs(lhs[2] - rhs[2]) <= tolerance)

    def _ensure_curve_metadata(self, curve: Curve) -> None:
        if curve.base_line_id:
            base_line = self.project.get_line(curve.base_line_id)
            if base_line:
                base_line.hidden = False
                if not base_line.description:
                    base_line.description = f"Curve {curve.id} base line"

        for pid in curve.arc_point_ids:
            point = self.project.get_point(pid)
            if not point:
                continue
            point.hidden = False
            if point.description in ("", "3D Visualisation", "Curve Arc Point", "Curve Arc Sample"):
                point.description = f"Curve {curve.id} arc sample"
    
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
