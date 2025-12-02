"""
Geometry utilities for coordinate transformation and calculations.
"""
import numpy as np
from math import atan2, cos, sin, sqrt
from typing import Tuple, Optional


class GeometryEngine:
    """Handles coordinate transformations and geometric calculations."""
    
    def __init__(self):
        self.transformation_matrix: Optional[np.ndarray] = None
        self.A = 0  # X axis index
        self.B = 1  # Y axis index
    
    def calculate_transformation(self, 
                                pdf_points: list,
                                real_points: list) -> bool:
        """
        Compute similarity transform from two reference point pairs.
        Returns True if successful.
        """
        if len(pdf_points) < 2 or len(real_points) < 2:
            return False
        
        pdf_p1 = np.array(pdf_points[self.A])
        pdf_p2 = np.array(pdf_points[self.B])
        real_p1 = np.array(real_points[self.A])
        real_p2 = np.array(real_points[self.B])
        
        pdf_vec = pdf_p2 - pdf_p1
        real_vec = real_p2 - real_p1
        pdf_len = np.linalg.norm(pdf_vec)
        real_len = np.linalg.norm(real_vec)
        
        if pdf_len == 0 or real_len == 0:
            return False
        
        scale = real_len / pdf_len
        pdf_angle = atan2(pdf_vec[self.B], pdf_vec[self.A])
        real_angle = atan2(real_vec[self.B], real_vec[self.A])
        angle = real_angle - pdf_angle
        
        cos_a = cos(angle)
        sin_a = sin(angle)
        R = np.array([[cos_a, -sin_a], [sin_a, cos_a]]) * scale
        t = real_p1 - R @ pdf_p1
        
        M = np.eye(3, dtype=float)
        M[0:2, 0:2] = R
        M[0:2, 2] = t
        self.transformation_matrix = M
        
        return True
    
    def transform_point(self, pdf_x: float, pdf_y: float) -> Tuple[float, float]:
        """Transform PDF coordinates to real-world coordinates."""
        if self.transformation_matrix is None:
            return pdf_x, pdf_y
        
        pdf_point = np.array([pdf_x, pdf_y, 1.0])
        real_point = self.transformation_matrix @ pdf_point
        return float(real_point[self.A]), float(real_point[self.B])
    
    def angle_from_center(self, center: tuple, point: tuple) -> float:
        """Return angle in degrees from center to point in range [0,360)."""
        dx = point[self.A] - center[self.A]
        dy = point[self.B] - center[self.B]
        angle_rad = atan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
        return angle_deg
    
    def is_angle_between(self, angle: float, start: float, end: float) -> bool:
        """Return True if angle lies strictly between start and end on a circle."""
        angle = angle % 360
        start = start % 360
        end = end % 360
        if start <= end:
            return start < angle < end
        else:
            return angle > start or angle < end
    
    def distance_2d(self, p1: tuple, p2: tuple) -> float:
        """Calculate 2D distance between two points."""
        return sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def distance_3d(self, p1: tuple, p2: tuple) -> float:
        """Calculate 3D distance between two points (x,y,z)."""
        return sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)
