"""
Calibration management for PDF-to-real coordinate transformations.
Each PDF has its own calibration file storing reference points.
"""
import json
import math
import os
from typing import Tuple, Optional, List
from datetime import datetime


class Calibration:
    """Handles coordinate transformation between PDF and real-world coordinates."""
    
    def __init__(self, pdf_filename: str = ""):
        self.pdf_filename = pdf_filename
        self.reference_points_pdf = []  # [(x_pdf, y_pdf), (x_pdf, y_pdf)]
        self.reference_points_real = []  # [(x_real, y_real), (x_real, y_real)]
        self.calibrated_date = None
        self.notes = ""
        
        # Cached transformation parameters
        self._scale = None
        self._rotation = None
        self._offset_x = None
        self._offset_y = None
        self._valid = False
    
    def set_reference_points(self, pdf_points: List[Tuple[float, float]], 
                           real_points: List[Tuple[float, float]]):
        """Set reference points and calculate transformation parameters."""
        if len(pdf_points) != 2 or len(real_points) != 2:
            raise ValueError("Exactly 2 reference points required")
        
        self.reference_points_pdf = pdf_points
        self.reference_points_real = real_points
        self.calibrated_date = datetime.now().isoformat()
        self._calculate_transformation()
    
    def _calculate_transformation(self):
        """Calculate scale, rotation, and offset from reference points."""
        if len(self.reference_points_pdf) != 2 or len(self.reference_points_real) != 2:
            self._valid = False
            return
        
        # PDF points
        p1_pdf = self.reference_points_pdf[0]
        p2_pdf = self.reference_points_pdf[1]
        
        # Real points
        p1_real = self.reference_points_real[0]
        p2_real = self.reference_points_real[1]
        
        # Calculate vectors
        dx_pdf = p2_pdf[0] - p1_pdf[0]
        dy_pdf = p2_pdf[1] - p1_pdf[1]
        dx_real = p2_real[0] - p1_real[0]
        dy_real = p2_real[1] - p1_real[1]
        
        # Calculate distances
        dist_pdf = math.sqrt(dx_pdf**2 + dy_pdf**2)
        dist_real = math.sqrt(dx_real**2 + dy_real**2)
        
        if dist_pdf < 0.001:
            self._valid = False
            return
        
        # Calculate scale
        self._scale = dist_real / dist_pdf
        
        # Calculate rotation (angle difference between vectors)
        angle_pdf = math.atan2(dy_pdf, dx_pdf)
        angle_real = math.atan2(dy_real, dx_real)
        self._rotation = angle_real - angle_pdf
        
        # Calculate offset using first point
        # Transform p1_pdf to real coords and compare with p1_real
        cos_r = math.cos(self._rotation)
        sin_r = math.sin(self._rotation)
        
        x_transformed = p1_pdf[0] * self._scale * cos_r - p1_pdf[1] * self._scale * sin_r
        y_transformed = p1_pdf[0] * self._scale * sin_r + p1_pdf[1] * self._scale * cos_r
        
        self._offset_x = p1_real[0] - x_transformed
        self._offset_y = p1_real[1] - y_transformed
        
        self._valid = True
    
    def pdf_to_real(self, x_pdf: float, y_pdf: float) -> Tuple[float, float]:
        """Transform PDF coordinates to real-world coordinates."""
        if not self._valid:
            return (0.0, 0.0)
        
        # Apply rotation and scale
        cos_r = math.cos(self._rotation)
        sin_r = math.sin(self._rotation)
        
        x_real = x_pdf * self._scale * cos_r - y_pdf * self._scale * sin_r + self._offset_x
        y_real = x_pdf * self._scale * sin_r + y_pdf * self._scale * cos_r + self._offset_y
        
        return (x_real, y_real)
    
    def real_to_pdf(self, x_real: float, y_real: float) -> Tuple[float, float]:
        """Transform real-world coordinates to PDF coordinates."""
        if not self._valid:
            return (0.0, 0.0)
        
        # Remove offset
        x_shifted = x_real - self._offset_x
        y_shifted = y_real - self._offset_y
        
        # Apply inverse rotation and scale
        cos_r = math.cos(-self._rotation)
        sin_r = math.sin(-self._rotation)
        
        x_pdf = (x_shifted * cos_r - y_shifted * sin_r) / self._scale
        y_pdf = (x_shifted * sin_r + y_shifted * cos_r) / self._scale
        
        return (x_pdf, y_pdf)
    
    def is_valid(self) -> bool:
        """Check if calibration has valid transformation parameters."""
        return self._valid
    
    def save(self, filepath: str):
        """Save calibration to a .cal file."""
        data = {
            "pdf_filename": self.pdf_filename,
            "reference_points_pdf": self.reference_points_pdf,
            "reference_points_real": self.reference_points_real,
            "calibrated_date": self.calibrated_date,
            "notes": self.notes
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'Calibration':
        """Load calibration from a .cal file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        cal = cls(data.get("pdf_filename", ""))
        cal.reference_points_pdf = [tuple(p) for p in data.get("reference_points_pdf", [])]
        cal.reference_points_real = [tuple(p) for p in data.get("reference_points_real", [])]
        cal.calibrated_date = data.get("calibrated_date")
        cal.notes = data.get("notes", "")
        
        if cal.reference_points_pdf and cal.reference_points_real:
            cal._calculate_transformation()
        
        return cal
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pdf_filename": self.pdf_filename,
            "reference_points_pdf": self.reference_points_pdf,
            "reference_points_real": self.reference_points_real,
            "calibrated_date": self.calibrated_date,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Calibration':
        """Create from dictionary."""
        cal = cls(data.get("pdf_filename", ""))
        cal.reference_points_pdf = [tuple(p) for p in data.get("reference_points_pdf", [])]
        cal.reference_points_real = [tuple(p) for p in data.get("reference_points_real", [])]
        cal.calibrated_date = data.get("calibrated_date")
        cal.notes = data.get("notes", "")
        
        if cal.reference_points_pdf and cal.reference_points_real:
            cal._calculate_transformation()
        
        return cal


class PDFDocument:
    """Represents a PDF document in the project with its calibration."""
    
    def __init__(self, filename: str, calibration: Optional[Calibration] = None,
                 display_name: str = "", order: int = 0):
        self.filename = filename
        self.calibration = calibration or Calibration(filename)
        self.active = False
        self.display_name = display_name or os.path.basename(filename)
        self.order = order
    
    def get_calibration_filename(self) -> str:
        """Get the expected calibration filename for this PDF."""
        base = os.path.splitext(self.filename)[0]
        return f"{base}.cal"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "filename": self.filename,
            "calibration_file": self.get_calibration_filename(),
            "active": self.active,
            "display_name": self.display_name,
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data: dict, project_dir: str = "") -> 'PDFDocument':
        """Create from dictionary, loading calibration if available."""
        filename = data.get("filename", "")
        display_name = data.get("display_name", "")
        order = data.get("order", 0)
        
        # Try to load calibration file
        cal_file = data.get("calibration_file", "")
        calibration = None
        
        if cal_file:
            cal_path = os.path.join(project_dir, cal_file)
            if os.path.exists(cal_path):
                try:
                    calibration = Calibration.load(cal_path)
                except Exception as e:
                    print(f"Warning: Could not load calibration from {cal_path}: {e}")
        
        doc = cls(filename, calibration, display_name, order)
        doc.active = data.get("active", False)
        
        return doc
