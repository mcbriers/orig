import numpy as np
from tkinter import messagebox


class PointsLinesMixin:
    def handle_coordinates_click(self, canvas_x, canvas_y, pdf_x, pdf_y):
        z_level = self.elevation_var.get()
        real_x, real_y = self.transform_point(pdf_x, pdf_y)
        # Allocate a new point id using centralized helper
        pid = self.next_point_id()

        point = {
            'id': pid,
            'real_x': int(round(real_x)),
            'real_y': int(round(real_y)),
            'z': int(round(float(z_level))) if str(z_level).strip() != '' else 0,
            'hidden': False,
            'pdf_x': pdf_x,
            'pdf_y': pdf_y,
            'description': '3D Visualisation',
        }
        self.user_points.append(point)
        self.mark_modified()
        size = getattr(self, 'point_marker_size', 5)
        clr = getattr(self, 'point_color_2d', 'blue')
        marker_id = self.canvas.create_oval(canvas_x - size, canvas_y - size, canvas_x + size, canvas_y + size,
                            outline=clr, fill=clr, tags="user_point", width=2)
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
            
            # Validate: prevent zero-length lines (same start and end point)
            if start_id == end_id:
                self.update_status("⚠️ Cannot create line: start and end points are the same!")
                self.canvas.delete("temp_line_point")
                self.current_line_points.clear()
                return
            
            start_point = next(p for p in self.user_points if p['id'] == start_id)
            end_point = next(p for p in self.user_points if p['id'] == end_id)
            x1 = start_point['pdf_x'] * self.zoom_level
            y1 = start_point['pdf_y'] * self.zoom_level
            x2 = end_point['pdf_x'] * self.zoom_level
            y2 = end_point['pdf_y'] * self.zoom_level
            # Use configured display params for new lines
            lw = getattr(self, 'line_width_2d', 4)
            lclr = getattr(self, 'line_color_2d', 'orange')
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill=lclr, width=lw, tags="user_line")
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
            self.mark_modified()
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_offset = 15
            text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
            lbl_size = getattr(self, 'label_font_size', 12)
            try:
                text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill=lclr, tags="line_label", font=("Helvetica", lbl_size))
            except Exception:
                text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill=lclr, tags="line_label")
            line_data['text_id'] = text_id
            self.update_status(f"Line {line_data['id']} created between points {start_id} and {end_id}")
            self.current_line_points.clear()
            self.canvas.delete("temp_line_point")
            # Update 3D view after creating a line
            try:
                self.update_3d_plot()
            except Exception:
                pass
            try:
                # update line counter in UI if present
                if hasattr(self, 'update_lines_label'):
                    try:
                        self.update_lines_label()
                    except Exception:
                        pass
            except Exception:
                pass

    def show_point_selection_dialog(self, candidates):
        import tkinter as tk
        from tkinter import Toplevel, Listbox, Button, Label, Scrollbar

        dlg = Toplevel(self.master)
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.title('Select Point')

        Label(dlg, text='Select a point (click or double-click)').grid(row=0, column=0, columnspan=2, padx=8, pady=(8,4))
        # listbox with scrollbar
        sb = Scrollbar(dlg)
        lb = Listbox(dlg, yscrollcommand=sb.set, selectmode='browse', width=50)
        sb.config(command=lb.yview)
        sb.grid(row=1, column=1, sticky='ns', padx=(0,8), pady=4)
        lb.grid(row=1, column=0, sticky='nsew', padx=(8,0), pady=4)

        options = [f"ID: {p['id']}, Z: {p.get('z', 0)}" for p in candidates]
        for opt in options:
            lb.insert('end', opt)

        result = {'idx': None}

        def on_ok():
            sel = lb.curselection()
            if not sel:
                return
            result['idx'] = int(sel[0])
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        def on_double(event=None):
            on_ok()

        btn_frame = tk.Frame(dlg)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(6,8))
        Button_ok = Button(btn_frame, text='OK', command=on_ok)
        Button_ok.pack(side='left', padx=6)
        Button_cancel = Button(btn_frame, text='Cancel', command=on_cancel)
        Button_cancel.pack(side='left')

        lb.bind('<Double-1>', on_double)

        # center dialog
        dlg.update_idletasks()
        try:
            x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
            y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
            dlg.geometry(f'+{x}+{y}')
        except Exception:
            pass

        self.master.wait_window(dlg)
        if result['idx'] is not None:
            return candidates[result['idx']]
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
            lw = getattr(self, 'line_width_2d', 4)
            lclr = getattr(self, 'line_color_2d', 'orange')
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill=lclr, width=lw, tags="user_line")
            line_data = {
                'id': self.next_line_id(),
                'start_id': start_id,
                'end_id': end_id,
                'canvas_id': line_id
            }
            self.lines.append(line_data)
            self.mark_modified()
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_offset = 15
            text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
            lbl_size = getattr(self, 'label_font_size', 12)
            try:
                text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill=lclr, tags="line_label", font=("Helvetica", lbl_size))
            except Exception:
                text_id = self.canvas.create_text(mid_x, text_y, text=str(line_data['id']), fill=lclr, tags="line_label")
            line_data['text_id'] = text_id
            self.update_status(f"Line {line_data['id']} created between points {start_id} and {end_id}")
            self.current_line_points.clear()
            self.canvas.delete("temp_line_point")

    def clear_points(self):
        # Confirmation dialog
        if not messagebox.askyesno("Clear All Data", 
                                   "This will clear all points, lines, and curves.\n\nAre you sure?",
                                   icon='warning'):
            return
        
        # Store undo snapshot
        try:
            self._undo_snapshot = {
                'points': [p.copy() for p in self.user_points],
                'lines': [l.copy() for l in self.lines],
                'curves': [c.copy() for c in self.curves],
                'operation': 'clear_all'
            }
        except Exception:
            pass
        
        self.user_points.clear()
        self.point_markers.clear()
        self.lines.clear()
        self.curves.clear()
        # Reset ID allocator/counters so new items start from 1
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                self.allocator.reset()
        except Exception:
            pass
        try:
            self.update_points_label()
        except Exception:
            if hasattr(self, 'points_label') and self.points_label is not None:
                self.points_label.config(text="Points: 0")
        try:
            self.update_lines_label()
        except Exception:
            if hasattr(self, 'lines_label') and self.lines_label is not None:
                self.lines_label.config(text=f"Lines: {len(self.lines)}")
        try:
            self.update_curves_label()
        except Exception:
            if hasattr(self, 'curves_label') and self.curves_label is not None:
                self.curves_label.config(text=f"Curves: {len(self.curves)}")
        if self.pdf_doc:
            self.display_page()
        
        # Refresh editor to keep treeviews in sync
        try:
            if hasattr(self, 'refresh_editor_lists'):
                self.refresh_editor_lists()
        except Exception:
            pass
        
        # Update 3D view
        try:
            if hasattr(self, 'update_3d_plot'):
                self.update_3d_plot()
        except Exception:
            pass
        
        self.update_status("All data cleared (use Edit → Undo Clear to restore)")

    def clear_lines_only(self):
        """Clear only lines, keeping points and curves intact."""
        if not self.lines:
            messagebox.showinfo("No Lines", "There are no lines to clear.")
            return
        
        if not messagebox.askyesno("Clear Lines", 
                                   f"This will clear all {len(self.lines)} lines.\n\nPoints and curves will remain.\n\nAre you sure?",
                                   icon='warning'):
            return
        
        # Store undo snapshot
        try:
            self._undo_snapshot = {
                'lines': [l.copy() for l in self.lines],
                'operation': 'clear_lines'
            }
        except Exception:
            pass
        
        self.lines.clear()
        
        try:
            self.lines_label.config(text=f"Lines: {len(self.lines)}")
        except Exception:
            pass
        
        if self.pdf_doc:
            try:
                self.redraw_markers()
            except Exception:
                self.display_page()
        
        try:
            if hasattr(self, 'refresh_editor_lists'):
                self.refresh_editor_lists()
        except Exception:
            pass
        
        try:
            if hasattr(self, 'update_3d_plot'):
                self.update_3d_plot()
        except Exception:
            pass
        
        self.update_status("Lines cleared (use Edit → Undo Clear to restore)")

    def clear_curves_only(self):
        """Clear only curves, keeping points and lines intact."""
        if not self.curves:
            messagebox.showinfo("No Curves", "There are no curves to clear.")
            return
        
        if not messagebox.askyesno("Clear Curves", 
                                   f"This will clear all {len(self.curves)} curves and their base lines.\n\nPoints and other lines will remain.\n\nAre you sure?",
                                   icon='warning'):
            return
        
        # Collect base line IDs from curves before clearing
        base_line_ids = set()
        for c in self.curves:
            base_line_id = c.get('base_line_id')
            if base_line_id and base_line_id != 0:
                base_line_ids.add(base_line_id)
        
        # Store undo snapshot (include both curves and their base lines)
        try:
            base_lines = [l.copy() for l in self.lines if l.get('id') in base_line_ids]
            self._undo_snapshot = {
                'curves': [c.copy() for c in self.curves],
                'base_lines': base_lines,
                'operation': 'clear_curves'
            }
        except Exception:
            pass
        
        # Clear curves first
        self.curves.clear()
        
        # Remove base lines
        if base_line_ids:
            self.lines = [l for l in self.lines if l.get('id') not in base_line_ids]
        
        try:
            self.curves_label.config(text=f"Curves: {len(self.curves)}")
        except Exception:
            pass
        try:
            self.lines_label.config(text=f"Lines: {len(self.lines)}")
        except Exception:
            pass
        
        if self.pdf_doc:
            try:
                self.redraw_markers()
            except Exception:
                self.display_page()
        
        try:
            if hasattr(self, 'refresh_editor_lists'):
                self.refresh_editor_lists()
        except Exception:
            pass
        
        try:
            if hasattr(self, 'update_3d_plot'):
                self.update_3d_plot()
        except Exception:
            pass
        
        msg = f"Curves cleared"
        if base_line_ids:
            msg += f" (and {len(base_line_ids)} base line(s))"
        msg += " (use Edit → Undo Clear to restore)"
        self.update_status(msg)

    def undo_clear(self):
        """Restore data from the last clear operation."""
        if not hasattr(self, '_undo_snapshot') or not self._undo_snapshot:
            messagebox.showinfo("Nothing to Undo", "No clear operation to undo.")
            return
        
        snapshot = self._undo_snapshot
        op = snapshot.get('operation', 'unknown')
        
        # Restore data based on operation type
        if op == 'clear_all':
            self.user_points = snapshot.get('points', [])
            self.lines = snapshot.get('lines', [])
            self.curves = snapshot.get('curves', [])
            msg = "Restored all points, lines, and curves"
        elif op == 'clear_lines':
            self.lines = snapshot.get('lines', [])
            msg = "Restored all lines"
        elif op == 'clear_curves':
            # Restore curves and their base lines
            self.curves = snapshot.get('curves', [])
            base_lines = snapshot.get('base_lines', [])
            if base_lines:
                # Add back the base lines that were removed
                self.lines.extend(base_lines)
                msg = f"Restored all curves and {len(base_lines)} base line(s)"
            else:
                msg = "Restored all curves"
        else:
            messagebox.showerror("Undo Failed", "Unknown clear operation type.")
            return
        
        # Clear the undo buffer (single-level undo only)
        self._undo_snapshot = None
        
        # Update UI
        try:
            self.update_points_label()
        except Exception:
            pass
        try:
            if hasattr(self, 'update_lines_label'):
                self.update_lines_label()
        except Exception:
            pass
        try:
            if hasattr(self, 'update_curves_label'):
                self.update_curves_label()
        except Exception:
            pass
        
        if self.pdf_doc:
            try:
                self.redraw_markers()
            except Exception:
                self.display_page()
        
        try:
            if hasattr(self, 'refresh_editor_lists'):
                self.refresh_editor_lists()
        except Exception:
            pass
        
        try:
            if hasattr(self, 'update_3d_plot'):
                self.update_3d_plot()
        except Exception:
            pass
        
        self.update_status(msg)
        messagebox.showinfo("Undo Complete", msg)


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

    def update_lines_label(self):
        try:
            if hasattr(self, 'lines_label') and self.lines_label is not None:
                self.lines_label.config(text=f"Lines: {len(self.lines)}")
        except Exception:
            pass

    def update_curves_label(self):
        try:
            if hasattr(self, 'curves_label') and self.curves_label is not None:
                self.curves_label.config(text=f"Curves: {len(self.curves)}")
        except Exception:
            pass
