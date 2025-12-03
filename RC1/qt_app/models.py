"""
Data models for the 3D digitizer application.
Separates business logic from UI concerns.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np


@dataclass
class Point:
    """Represents a 3D point in the digitizer."""
    id: int
    real_x: float
    real_y: float
    z: float
    pdf_x: float
    pdf_y: float
    hidden: bool = False
    description: str = "3D Visualisation"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'real_x': self.real_x,
            'real_y': self.real_y,
            'z': self.z,
            'pdf_x': self.pdf_x,
            'pdf_y': self.pdf_y,
            'hidden': self.hidden,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Point':
        """Create from dictionary."""
        # Handle z as string or float
        z_value = data.get('z', 0)
        if isinstance(z_value, str):
            try:
                z_value = float(z_value)
            except (ValueError, TypeError):
                z_value = 0.0
        
        return cls(
            id=data['id'],
            real_x=data.get('real_x', data.get('pdf_x', 0)),
            real_y=data.get('real_y', data.get('pdf_y', 0)),
            z=z_value,
            pdf_x=data['pdf_x'],
            pdf_y=data['pdf_y'],
            hidden=data.get('hidden', False),
            description=data.get('description', '3D Visualisation')
        )


@dataclass
class Line:
    """Represents a line between two points."""
    id: int
    start_id: int
    end_id: int
    hidden: bool = False
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'start_id': self.start_id,
            'end_id': self.end_id,
            'hidden': self.hidden,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Line':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            start_id=data['start_id'],
            end_id=data['end_id'],
            hidden=data.get('hidden', False),
            description=data.get('description', '')
        )


@dataclass
class Curve:
    """Represents a curve with start, end, and interior points."""
    id: int
    start_id: int
    end_id: int
    arc_point_ids: List[int] = field(default_factory=list)
    arc_points_real: List[tuple] = field(default_factory=list)  # [(x,y,z), ...]
    base_line_id: Optional[int] = None
    hidden: bool = False
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'start_id': self.start_id,
            'end_id': self.end_id,
            'arc_point_ids': self.arc_point_ids,
            'arc_points_real': self.arc_points_real,
            'base_line_id': self.base_line_id,
            'hidden': self.hidden,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Curve':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            start_id=data['start_id'],
            end_id=data['end_id'],
            arc_point_ids=data.get('arc_point_ids', []),
            arc_points_real=data.get('arc_points_real', []),
            base_line_id=data.get('base_line_id'),
            hidden=data.get('hidden', False),
            description=data.get('description', '')
        )


class ProjectData:
    """Central data store for the digitizer project."""
    
    def __init__(self):
        self.points: List[Point] = []
        self.lines: List[Line] = []
        self.curves: List[Curve] = []
        # Transponder/RFID records (list of dicts)
        self.transponders: List[Dict[str, Any]] = []
        self.reference_points_pdf: List[tuple] = []  # [(x,y), ...]
        self.reference_points_real: List[tuple] = []  # [(x,y), ...]
        self.transformation_matrix: Optional[np.ndarray] = None
        self.deletion_log: List[Dict[str, Any]] = []
        self.pdf_path: Optional[str] = None
        self.project_path: Optional[str] = None
        self.modified: bool = False
        
        # ID allocation
        self._next_point_id = 1
        self._next_line_id = 1
        self._next_curve_id = 1
    
    def allocate_point_id(self) -> int:
        """Get next available point ID."""
        max_id = max((p.id for p in self.points), default=0)
        self._next_point_id = max(self._next_point_id, max_id + 1)
        result = self._next_point_id
        self._next_point_id += 1
        return result
    
    def allocate_line_id(self) -> int:
        """Get next available line ID."""
        max_id = max((l.id for l in self.lines), default=0)
        self._next_line_id = max(self._next_line_id, max_id + 1)
        result = self._next_line_id
        self._next_line_id += 1
        return result
    
    def allocate_curve_id(self) -> int:
        """Get next available curve ID."""
        max_id = max((c.id for c in self.curves), default=0)
        self._next_curve_id = max(self._next_curve_id, max_id + 1)
        result = self._next_curve_id
        self._next_curve_id += 1
        return result
    
    def get_point(self, point_id: int) -> Optional[Point]:
        """Find point by ID."""
        return next((p for p in self.points if p.id == point_id), None)
    
    def get_line(self, line_id: int) -> Optional[Line]:
        """Find line by ID."""
        return next((l for l in self.lines if l.id == line_id), None)
    
    def get_curve(self, curve_id: int) -> Optional[Curve]:
        """Find curve by ID."""
        return next((c for c in self.curves if c.id == curve_id), None)
    
    def count_point_references(self, point_id: int) -> int:
        """Count how many lines/curves reference this point."""
        count = 0
        # Count lines
        for line in self.lines:
            if not line.hidden:
                if line.start_id == point_id:
                    count += 1
                if line.end_id == point_id:
                    count += 1
        # Count curves (start/end OR arc_point_ids, not both)
        for curve in self.curves:
            if not curve.hidden:
                if point_id in curve.arc_point_ids:
                    count += 1
                elif point_id == curve.start_id or point_id == curve.end_id:
                    count += 1
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire project to dictionary for serialization."""
        result = {
            'user_points': [p.to_dict() for p in self.points],
            'lines': [l.to_dict() for l in self.lines],
            'curves': [c.to_dict() for c in self.curves],
            'transponders': self.transponders,
            'reference_points_pdf': self.reference_points_pdf,
            'reference_points_real': self.reference_points_real,
            'deletion_log': self.deletion_log
        }
        if self.transformation_matrix is not None:
            result['transformation_matrix'] = self.transformation_matrix.tolist()
        return result
    
    def from_dict(self, data: Dict[str, Any]):
        """Load entire project from dictionary."""
        # Handle both 'points' and 'user_points' for compatibility
        points_data = data.get('user_points') or data.get('points', [])
        self.points = [Point.from_dict(p) for p in points_data]
        
        self.lines = [Line.from_dict(l) for l in data.get('lines', [])]
        self.curves = [Curve.from_dict(c) for c in data.get('curves', [])]
        
        # Handle both old and new calibration point formats
        self.reference_points_pdf = data.get('reference_points_pdf') or data.get('calibration_pdf_points', [])
        self.reference_points_real = data.get('reference_points_real') or data.get('calibration_real_points', [])
        
        self.deletion_log = data.get('deletion_log', [])
        # Load transponders if present and normalize records
        raw_trans = data.get('transponders', [])
        normalized = []
        for r in raw_trans:
            try:
                tid = int(r.get('id')) if r.get('id') not in (None, '') else None
            except Exception:
                tid = None
            desc = r.get('description', '')
            magnet = bool(r.get('magnet_only', False))
            trans_id = r.get('transponder_id', '')
            # Additional storage columns
            line_id = r.get('line_id', None)
            try:
                if line_id in (None, ''):
                    line_id = None
                else:
                    line_id = int(line_id)
            except Exception:
                line_id = None
            try:
                distance = float(r.get('distance', 0.0))
            except Exception:
                distance = 0.0
            assigned = bool(r.get('assigned', False))
            normalized.append({
                'id': tid,
                'description': desc,
                'magnet_only': magnet,
                'transponder_id': trans_id,
                'line_id': line_id,
                'distance': distance,
                'assigned': assigned
            })
        self.transponders = normalized
        
        if 'transformation_matrix' in data:
            self.transformation_matrix = np.array(data['transformation_matrix'])
        else:
            self.transformation_matrix = None
        
        self.modified = False
    
    def clear(self):
        """Clear all data."""
        self.points.clear()
        self.lines.clear()
        self.curves.clear()
        self.reference_points_pdf.clear()
        self.reference_points_real.clear()
        self.transformation_matrix = None
        self.deletion_log.clear()
        self.pdf_path = None
        self.project_path = None
        self.modified = False
        self._next_point_id = 1
        self._next_line_id = 1
        self._next_curve_id = 1
