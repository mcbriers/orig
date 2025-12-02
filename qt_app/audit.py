"""
Line audit and validation tools.
"""
from typing import List, Set, Dict, Optional, Tuple
from .models import ProjectData, Point, Line, Curve


class LineAudit:
    """Provides line connectivity analysis and validation."""
    
    def __init__(self, project: ProjectData):
        self.project = project
    
    def trace_from_point(self, start_point_id: int, 
                        max_depth: int = 100) -> Dict[str, any]:
        """
        Trace lines and curves from a starting point using DFS.
        Returns dict with visited points, lines, curves, and endpoints.
        """
        visited_points: Set[int] = set()
        visited_lines: Set[int] = set()
        visited_curves: Set[int] = set()
        endpoints: Set[int] = set()
        
        def dfs(point_id: int, depth: int = 0):
            if depth > max_depth or point_id in visited_points:
                return
            
            visited_points.add(point_id)
            
            # Find connected lines
            for line in self.project.lines:
                if line.hidden or line.id in visited_lines:
                    continue
                
                next_point = None
                if line.start_id == point_id:
                    next_point = line.end_id
                elif line.end_id == point_id:
                    next_point = line.start_id
                
                if next_point:
                    visited_lines.add(line.id)
                    dfs(next_point, depth + 1)
            
            # Find connected curves
            for curve in self.project.curves:
                if curve.hidden or curve.id in visited_curves:
                    continue
                
                next_point = None
                if curve.start_id == point_id:
                    next_point = curve.end_id
                elif curve.end_id == point_id:
                    next_point = curve.start_id
                
                if next_point:
                    visited_curves.add(curve.id)
                    dfs(next_point, depth + 1)
        
        # Start DFS
        dfs(start_point_id)
        
        # Identify endpoints (points with only one connection)
        for point_id in visited_points:
            connection_count = 0
            
            for line_id in visited_lines:
                line = self.project.get_line(line_id)
                if line and (line.start_id == point_id or line.end_id == point_id):
                    connection_count += 1
            
            for curve_id in visited_curves:
                curve = self.project.get_curve(curve_id)
                if curve and (curve.start_id == point_id or curve.end_id == point_id):
                    connection_count += 1
            
            if connection_count == 1:
                endpoints.add(point_id)
        
        return {
            'points': visited_points,
            'lines': visited_lines,
            'curves': visited_curves,
            'endpoints': endpoints,
            'total_connections': len(visited_lines) + len(visited_curves)
        }
    
    def trace_directional(self, start_point_id: int, 
                          max_depth: int = 100) -> Dict[str, any]:
        """
        Trace lines and curves from a starting point following only start->end direction.
        Returns dict with visited points, lines, curves, and endpoints.
        """
        visited_points: Set[int] = set()
        visited_lines: Set[int] = set()
        visited_curves: Set[int] = set()
        endpoints: Set[int] = set()
        
        def dfs(point_id: int, depth: int = 0):
            if depth > max_depth or point_id in visited_points:
                return
            
            visited_points.add(point_id)
            
            # Find connected lines (only follow start->end direction)
            for line in self.project.lines:
                if line.hidden or line.id in visited_lines:
                    continue
                
                # Only follow if this point is the start of the line
                if line.start_id == point_id:
                    visited_lines.add(line.id)
                    dfs(line.end_id, depth + 1)
            
            # Find connected curves (only follow start->end direction)
            for curve in self.project.curves:
                if curve.hidden or curve.id in visited_curves:
                    continue
                
                # Only follow if this point is the start of the curve
                if curve.start_id == point_id:
                    visited_curves.add(curve.id)
                    dfs(curve.end_id, depth + 1)
        
        # Start DFS
        dfs(start_point_id)
        
        # Identify endpoints (points with no outgoing connections)
        for point_id in visited_points:
            has_outgoing = False
            
            for line_id in visited_lines:
                line = self.project.get_line(line_id)
                if line and line.start_id == point_id:
                    has_outgoing = True
                    break
            
            if not has_outgoing:
                for curve_id in visited_curves:
                    curve = self.project.get_curve(curve_id)
                    if curve and curve.start_id == point_id:
                        has_outgoing = True
                        break
            
            if not has_outgoing:
                endpoints.add(point_id)
        
        return {
            'points': visited_points,
            'lines': visited_lines,
            'curves': visited_curves,
            'endpoints': endpoints,
            'total_connections': len(visited_lines) + len(visited_curves)
        }
    
    def find_isolated_points(self) -> List[Point]:
        """Find points with no line/curve connections."""
        isolated = []
        for point in self.project.points:
            if not point.hidden and self.project.count_point_references(point.id) == 0:
                isolated.append(point)
        return isolated
    
    def find_zero_length_lines(self) -> List[Line]:
        """Find lines where start_id == end_id."""
        zero_length = []
        for line in self.project.lines:
            if not line.hidden and line.start_id == line.end_id:
                zero_length.append(line)
        return zero_length
    
    def find_duplicate_lines(self) -> List[Tuple[Line, Line]]:
        """Find lines that connect the same two points (in either direction)."""
        duplicates = []
        seen = set()
        
        for i, line1 in enumerate(self.project.lines):
            if line1.hidden:
                continue
            
            key = tuple(sorted([line1.start_id, line1.end_id]))
            if key in seen:
                # Find the original
                for line2 in self.project.lines[:i]:
                    if not line2.hidden:
                        key2 = tuple(sorted([line2.start_id, line2.end_id]))
                        if key == key2:
                            duplicates.append((line2, line1))
                            break
            else:
                seen.add(key)
        
        return duplicates
    
    def find_overlapping_points(self, tolerance: float = 0.1) -> List[Tuple[Point, Point]]:
        """Find points at the same location (within tolerance)."""
        overlapping = []
        points = [p for p in self.project.points if not p.hidden]
        
        for i, p1 in enumerate(points):
            for p2 in points[i+1:]:
                if (abs(p1.real_x - p2.real_x) < tolerance and
                    abs(p1.real_y - p2.real_y) < tolerance and
                    abs(p1.z - p2.z) < tolerance):
                    overlapping.append((p1, p2))
        
        return overlapping
    
    def validate_project(self) -> Dict[str, any]:
        """Run all validation checks and return a report."""
        report = {
            'isolated_points': self.find_isolated_points(),
            'zero_length_lines': self.find_zero_length_lines(),
            'duplicate_lines': self.find_duplicate_lines(),
            'overlapping_points': self.find_overlapping_points(),
            'total_points': len([p for p in self.project.points if not p.hidden]),
            'total_lines': len([l for l in self.project.lines if not l.hidden]),
            'total_curves': len([c for c in self.project.curves if not c.hidden]),
        }
        
        report['issues_found'] = (
            len(report['isolated_points']) +
            len(report['zero_length_lines']) +
            len(report['duplicate_lines']) +
            len(report['overlapping_points'])
        )
        
        return report
    
    def get_point_references(self, point_id: int) -> Dict[str, List]:
        """Get detailed list of all lines and curves referencing a point."""
        refs = {
            'lines_start': [],
            'lines_end': [],
            'curves_start': [],
            'curves_end': [],
            'curves_arc': []
        }
        
        for line in self.project.lines:
            if not line.hidden:
                if line.start_id == point_id:
                    refs['lines_start'].append(line)
                if line.end_id == point_id:
                    refs['lines_end'].append(line)
        
        for curve in self.project.curves:
            if not curve.hidden:
                if curve.start_id == point_id:
                    refs['curves_start'].append(curve)
                elif curve.end_id == point_id:
                    refs['curves_end'].append(curve)
                elif point_id in curve.arc_point_ids:
                    refs['curves_arc'].append(curve)
        
        return refs
