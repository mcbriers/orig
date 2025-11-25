import numpy as np


class PointsLinesMixin:
    def handle_coordinates_click(self, canvas_x, canvas_y, pdf_x, pdf_y):
        z_level = self.elevation_var.get()
        real_x, real_y = self.transform_point(pdf_x, pdf_y)
        # Allocate a new point id using centralized helper
        pid = self.next_point_id()

        point = {
            'id': pid,
            'real_x': np.round(real_x, 2),
            'real_y': np.round(real_y, 2),
            'z': z_level,
            'hidden': False,
            'pdf_x': pdf_x,
            'pdf_y': pdf_y,
        }
        self.user_points.append(point)
        size = 5
        marker_id = self.canvas.create_oval(canvas_x - size, canvas_y - size, canvas_x + size, canvas_y + size,
                                            outline="blue", fill="blue", tags="user_point", width=2)
        self.point_markers[point['id']] = marker_id
        self.label_all_elements()
        # Update 3D view if available
        try:
            self.update_3d_plot()
        except Exception:
            pass

    def handle_lines_click(self, canvas_x, canvas_y):
        if not self.user_points:
            self.update_status("No points available — add coordinates first.")
            return

        # Find all points at the clicked canvas location (within tolerance)
        tolerance = 5  # pixels
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

        # If multiple points at same x,y, show selection dialog
        if len(candidates) > 1:
            selected_point = self.show_point_selection_dialog(candidates)
            if not selected_point:
                self.update_status("No point selected.")
                return
        else:
            # single-candidate -> pick first dict
            selected_point = candidates[0]

        # Draw selection marker
        closest_canvas_x = selected_point['pdf_x'] * self.zoom_level
        closest_canvas_y = selected_point['pdf_y'] * self.zoom_level
        size = 7
        self.canvas.create_oval(
            closest_canvas_x - size, closest_canvas_y - size,
            closest_canvas_x + size, closest_canvas_y + size,
            outline="green", width=2, tags="temp_line_point"
        )

        self.current_line_points.append(selected_point['id'])
        self.update_status(f"Selected point {selected_point['id']} for line ({len(self.current_line_points)}/2)")

        if len(self.current_line_points) == 2:
            start_id, end_id = self.current_line_points
            start_point = next(p for p in self.user_points if p['id'] == start_id)
            end_point = next(p for p in self.user_points if p['id'] == end_id)
            x1 = start_point['pdf_x'] * self.zoom_level
            y1 = start_point['pdf_y'] * self.zoom_level
            x2 = end_point['pdf_x'] * self.zoom_level
            y2 = end_point['pdf_y'] * self.zoom_level
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill="orange", width=4, tags="user_line")
            # Allocate a consistent line id via centralized helper
            line_data = {
                'id': self.next_line_id(),
                'start_id': start_id,
                'end_id': end_id,
                'canvas_id': line_id
            }
            # default visibility in 3D
            line_data['hidden'] = False
            self.lines.append(line_data)
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_offset = 15
            text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
            text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill="orange", tags="line_label", font=("Helvetica", 16))
            line_data['text_id'] = text_id
            self.update_status(f"Line {line_data['id']} created between points {start_id} and {end_id}")
            self.current_line_points.clear()
            self.canvas.delete("temp_line_point")
            # Update 3D view after creating a line
            try:
                self.update_3d_plot()
            except Exception:
                pass

    def show_point_selection_dialog(self, candidates):
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()  # Hide main window
        options = [f"ID: {p['id']}, Z: {p['z']}" for p in candidates]
        selected = simpledialog.askinteger(
            "Select Point",
            "Choose a point index (0..%d):\n" % (len(candidates) - 1) + "\n".join(options),
            parent=root,
            minvalue=0,
            maxvalue=len(candidates) - 1
        )
        root.destroy()
        if selected is not None:
            return candidates[selected]
        return None
















    def old_handle_lines_click(self, canvas_x, canvas_y):
        if not self.user_points:
            self.update_status("No points available — add coordinates first.")
            return
        closest_point = min(
            self.user_points,
            key=lambda p: (p['pdf_x'] * self.zoom_level - canvas_x) ** 2 + (p['pdf_y'] * self.zoom_level - canvas_y) ** 2
        )
        closest_canvas_x = closest_point['pdf_x'] * self.zoom_level
        closest_canvas_y = closest_point['pdf_y'] * self.zoom_level
        size = 7
        self.canvas.create_oval(closest_canvas_x - size, closest_canvas_y - size, closest_canvas_x + size, closest_canvas_y + size,
                                outline="green", width=2, tags="temp_line_point")
        self.current_line_points.append(closest_point['id'])
        self.update_status(f"Selected point {closest_point['id']} for line ({len(self.current_line_points)}/2)")
        if len(self.current_line_points) == 2:
            start_id, end_id = self.current_line_points
            start_point = next(p for p in self.user_points if p['id'] == start_id)
            end_point = next(p for p in self.user_points if p['id'] == end_id)
            x1 = start_point['pdf_x'] * self.zoom_level
            y1 = start_point['pdf_y'] * self.zoom_level
            x2 = end_point['pdf_x'] * self.zoom_level
            y2 = end_point['pdf_y'] * self.zoom_level
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill="orange", width=4, tags="user_line")
            line_data = {
                'id': self.next_line_id(),
                'start_id': start_id,
                'end_id': end_id,
                'canvas_id': line_id
            }
            self.lines.append(line_data)
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_offset = 15
            text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
            text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill="orange", tags="line_label",font=("Helvetica", 16))
            line_data['text_id'] = text_id
            self.update_status(f"Line {line_data['id']} created between points {start_id} and {end_id}")
            self.current_line_points.clear()
            self.canvas.delete("temp_line_point")

    def clear_points(self):
        self.user_points.clear()
        self.point_markers.clear()
        self.lines.clear()
        self.curves.clear()
        self.points_label.config(text="Points: 0")
        if self.pdf_doc:
            self.display_page()
        self.update_status("Points cleared")


    def label_all_elements(self):
        # Recreate textual labels for points (keep graphical markers intact)
        try:
            # remove old point labels
            self.canvas.delete("point_label")
        except Exception:
            pass

        for point in self.user_points:
            x = point['pdf_x'] * self.zoom_level
            y = point['pdf_y'] * self.zoom_level
            # Create text label for point ID near point location
            self.canvas.create_text(x + 5, y - 5, text=str(point['id']), fill="red",
                                    tags="point_label", font=("Helvetica", 12))

        # Refresh lines/curves and their labels (redraw_markers handles line labels and curve markers)
        try:
            self.redraw_markers()
        except Exception:
            # If redraw not available in host, silently continue
            pass

    def update_points_label(self):
        self.points_label.config(text=f"Points: {len(self.user_points)}")
