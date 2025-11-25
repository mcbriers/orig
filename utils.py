import numpy as np
from math import atan2, cos, sin


class UtilsMixin:
    """Utility mixin providing coordinate transformation and angle helpers.

    Host class must provide:
      - integer indices `A` and `B` (usually 0 and 1)
      - lists `reference_points_pdf`, `reference_points_real`
      - attribute `transformation_matrix` (or None)
      - method `update_status(str)` for user messages (optional)
    """

    def transform_point(self, pdf_x, pdf_y):
        """Transform a point from PDF coordinates to real-world coordinates.

        If no transformation matrix is available, returns the input coordinates.
        """
        if getattr(self, "transformation_matrix", None) is None:
            return pdf_x, pdf_y
        pdf_point = np.array([pdf_x, pdf_y, 1.0])
        real_point = self.transformation_matrix @ pdf_point
        return float(real_point[self.A]), float(real_point[self.B])

    def angle_from_center(self, center, point):
        """Return angle in degrees from `center` to `point` in range [0,360)."""
        dx = point[self.A] - center[self.A]
        dy = point[self.B] - center[self.B]
        angle_rad = atan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
        return angle_deg

    def is_angle_between(self, angle, start, end):
        """Return True if `angle` lies strictly between `start` and `end` on a circle."""
        angle = angle % 360
        start = start % 360
        end = end % 360
        if start <= end:
            return start < angle < end
        else:
            return angle > start or angle < end

    def calculate_transformation(self):
        """Compute a similarity transform (scale+rotation+translation) from two reference pairs.

        Uses self.reference_points_pdf[self.A/self.B] and
        self.reference_points_real[self.A/self.B]. Sets self.transformation_matrix
        to a 3x3 homogeneous transform on success, otherwise None.
        """
        if len(getattr(self, "reference_points_pdf", [])) < 2 or len(getattr(self, "reference_points_real", [])) < 2:
            return

        pdf_p1 = np.array(self.reference_points_pdf[self.A])
        pdf_p2 = np.array(self.reference_points_pdf[self.B])
        real_p1 = np.array(self.reference_points_real[self.A])
        real_p2 = np.array(self.reference_points_real[self.B])

        pdf_vec = pdf_p2 - pdf_p1
        real_vec = real_p2 - real_p1
        pdf_len = np.linalg.norm(pdf_vec)
        real_len = np.linalg.norm(real_vec)

        if pdf_len == 0 or real_len == 0:
            # invalid reference points
            try:
                self.update_status("Calibration failed: reference points must be distinct.")
            except Exception:
                pass
            self.transformation_matrix = None
            return

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

        try:
            self.update_status(f"Transformation calculated: scale={scale:.3f}, angle={angle*180/np.pi:.1f}°")
        except Exception:
            pass