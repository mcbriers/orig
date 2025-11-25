import numpy as np
from math import atan2, cos, sin, sqrt

class CurvesMixin:
    # Removed older/buggy handlers; keep the working `handle_curves_click`



    def handle_curves_click(self, canvas_x, canvas_y):
        if not self.user_points:
            self.update_status("No points available — add coordinates first.")
            return
        if not self.current_curve_points:
            self.current_curve_points = []
        if len(self.current_curve_points) < 2:
            # Find candidates within a small pixel tolerance (like line selection)
            tolerance = 5
            clicked_pdf_x = canvas_x / self.zoom_level
            clicked_pdf_y = canvas_y / self.zoom_level
            candidates = [
                p for p in self.user_points
                if abs(p['pdf_x'] - clicked_pdf_x) * self.zoom_level < tolerance
                and abs(p['pdf_y'] - clicked_pdf_y) * self.zoom_level < tolerance
            ]

            if not candidates:
                self.update_status("No points found at this location.")
                return

            if len(candidates) > 1:
                # Use the existing dialog from PointsLinesMixin if available
                try:
                    selected_point = self.show_point_selection_dialog(candidates)
                except Exception:
                    selected_point = candidates[0]
                if not selected_point:
                    self.update_status("No point selected.")
                    return
            else:
                selected_point = candidates[0]

            closest_canvas_x = selected_point['pdf_x'] * self.zoom_level
            closest_canvas_y = selected_point['pdf_y'] * self.zoom_level
            size = 7
            self.canvas.create_oval(
                closest_canvas_x - size, closest_canvas_y - size,
                closest_canvas_x + size, closest_canvas_y + size,
                outline="green", width=2, tags="temp_curve_point"
            )
            if selected_point['id'] in self.current_curve_points:
                self.update_status(f"Point {selected_point['id']} already selected. Choose a different point.")
                return
            self.current_curve_points.append(selected_point['id'])
            self.update_status(f"Selected point {selected_point['id']} for curve ({len(self.current_curve_points)}/3)")
        else:
            size = 7
            self.canvas.create_oval(
                canvas_x - size, canvas_y - size,
                canvas_x + size, canvas_y + size,
                outline="green", width=2, tags="temp_curve_point"
            )
            curvature_pdf_x = canvas_x / self.zoom_level
            curvature_pdf_y = canvas_y / self.zoom_level
            p_ids = self.current_curve_points
            start_point = next(p for p in self.user_points if p['id'] == p_ids[self.A])
            end_point = next(p for p in self.user_points if p['id'] == p_ids[self.B])
            p_start = (start_point['pdf_x'], start_point['pdf_y'])
            p_end = (end_point['pdf_x'], end_point['pdf_y'])
            p_curve = (curvature_pdf_x, curvature_pdf_y)
            center, radius = self.circle_from_three_points(p_start, p_end, p_curve)
            if center is None:
                self.update_status("Invalid curve: points are colinear. Select 3 non-colinear points.")
                self.current_curve_points.clear()
                self.canvas.delete("temp_curve_point")
                return
            cx, cy = center[self.A], center[self.B]
            v_start = (p_start[self.A] - cx, p_start[self.B] - cy)
            v_end = (p_end[self.A] - cx, p_end[self.B] - cy)
            v_curve = (p_curve[self.A] - cx, p_curve[self.B] - cy)
            cross1 = v_start[self.A] * v_end[self.B] - v_start[self.B] * v_end[self.A]
            cross2 = v_start[self.A] * v_curve[self.B] - v_start[self.B] * v_curve[self.A]
            start_angle = self.angle_from_center(center, p_start) % 360
            end_angle = self.angle_from_center(center, p_end) % 360
            if end_angle < start_angle:
                end_angle += 360
            if cross1 * cross2 > 0:
                if not self.is_angle_between(self.angle_from_center(center, p_curve), start_angle, end_angle):
                    start_angle, end_angle = end_angle, start_angle + 360
            else:
                if self.is_angle_between(self.angle_from_center(center, p_curve), start_angle, end_angle):
                    start_angle, end_angle = end_angle, start_angle + 360
            extent_angle = end_angle - start_angle
            # Number of interior arc points is configurable via the app setting
            num_points = getattr(self, 'curve_interior_points', 4)
            # angles vector includes endpoints; we then exclude them to get interior points
            angles = np.linspace(start_angle, end_angle, num_points + 2)  # +2 for endpoints
            angles = angles[1:-1]  # Exclude the endpoint angles
            arc_points_pdf = []
            for angle in angles:
                rad = np.radians(angle % 360)
                x = cx + radius * cos(rad)
                y = cy + radius * sin(rad)
                arc_points_pdf.append((x, y))
            # Prepend first clicked point and append second clicked point
            arc_points_pdf = [p_start] + arc_points_pdf + [p_end]
            arc_points_real = []
            arc_point_ids = []
            z_level = self.elevation_var.get()
            for px, py in arc_points_pdf:
                real_x, real_y = self.transform_point(px, py)
                # store Z with real coordinates so 3D plotting can use the correct elevation
                arc_points_real.append((np.round(real_x, 2), np.round(real_y, 2), float(z_level)))
                if (px, py) == p_start:
                    # Reuse start point ID
                    arc_point_ids.append(start_point['id'])
                elif (px, py) == p_end:
                    # Reuse end point ID
                    arc_point_ids.append(end_point['id'])
                else:
                    # New intermediate point: allocate id via allocator when available
                    # Allocate intermediate point id via centralized helper
                    new_pid = self.next_point_id()
                    point = {
                        'id': new_pid,
                        'pdf_x': px,
                        'pdf_y': py,
                        'real_x': np.round(real_x, 2),
                        'real_y': np.round(real_y, 2),
                        'z': z_level
                    }
                    self.user_points.append(point)
                    arc_point_ids.append(new_pid)
            curve_marker_size = 3
            for px, py in arc_points_pdf:
                px_canvas = px * self.zoom_level
                py_canvas = py * self.zoom_level
                self.canvas.create_oval(
                    px_canvas - curve_marker_size, py_canvas - curve_marker_size,
                    px_canvas + curve_marker_size, py_canvas + curve_marker_size,
                    outline="blue", fill="blue", tags="curve_point", width=1
                )
            # Determine if there's a base line connecting start and end (useful metadata)
            # Ensure a base line exists in the same direction (start -> end). Create one if missing.
            base_line_id = next((l['id'] for l in self.lines if (l.get('start_id') == start_point['id'] and l.get('end_id') == end_point['id'])), None)
            if base_line_id is None:
                try:
                    # allocate a new line id via centralized helper
                    new_lid = self.next_line_id()
                    x1 = start_point['pdf_x'] * self.zoom_level
                    y1 = start_point['pdf_y'] * self.zoom_level
                    x2 = end_point['pdf_x'] * self.zoom_level
                    y2 = end_point['pdf_y'] * self.zoom_level
                    canvas_line_id = self.canvas.create_line(x1, y1, x2, y2, fill="orange", width=4, tags="user_line")
                    line_entry = {'id': new_lid, 'start_id': start_point['id'], 'end_id': end_point['id'], 'canvas_id': canvas_line_id, 'hidden': False}
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    text_offset = 15
                    text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
                    text_id = self.canvas.create_text(mid_x, text_y, text=str(new_lid), fill="orange", tags="line_label", font=("Helvetica", 16))
                    line_entry['text_id'] = text_id
                    self.lines.append(line_entry)
                    base_line_id = new_lid
                except Exception:
                    base_line_id = 0

            curve_data = {
                'id': self.next_curve_id(),
                'start_id': start_point['id'],
                'end_id': end_point['id'],
                'base_line_id': base_line_id,
                'curvature_point_pdf': (curvature_pdf_x, curvature_pdf_y),
                'arc_points_pdf': arc_points_pdf,
                'arc_points_real': arc_points_real,
                'arc_point_ids': arc_point_ids,
                'canvas_id': None,
                'arc_point_marker_ids': [],
                'z_level': z_level,
                'hidden': False
            }
            self.curves.append(curve_data)
            self.update_status(f"Curve {curve_data['id']} created with radius {radius:.2f}. Total points: {len(self.user_points)}")
            self.update_points_label()
            # Ensure editor lists and 2D markers reflect the new curve immediately
            try:
                self.redraw_markers()
            except Exception:
                pass
            try:
                self.refresh_editor_lists()
            except Exception:
                pass
            try:
                if hasattr(self, 'update_curves_label'):
                    self.update_curves_label()
            except Exception:
                pass
            try:
                if hasattr(self, 'update_lines_label'):
                    self.update_lines_label()
            except Exception:
                pass
            self.current_curve_points.clear()
            self.canvas.delete("temp_curve_point")
            # Update 3D view after creating curve
            try:
                self.update_3d_plot()
            except Exception:
                pass
        
    # removed older duplicate handlers to keep implementation concise

    def circle_from_three_points(self, p1, p2, p3):
        x1, y1 = p1[self.A], p1[self.B]
        x2, y2 = p2[self.A], p2[self.B]
        x3, y3 = p3[self.A], p3[self.B]
        A = np.array([            [x2 - x1, y2 - y1],
            [x3 - x1, y3 - y1]
        ])
        b = 0.5 * np.array([            x2 ** 2 + y2 ** 2 - x1 ** 2 - y1 ** 2,
            x3 ** 2 + y3 ** 2 - x1 ** 2 - y1 ** 2
        ])
        try:
            center = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            return None, None
        h, k = center[self.A], center[self.B]
        r = sqrt((h - x1) ** 2 + (k - y1) ** 2)
        return (h, k), r
