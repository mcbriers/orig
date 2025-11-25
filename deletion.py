from tkinter import messagebox
from datetime import datetime


class DeletionMixin:
    def handle_deletion_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level

        selected = self.find_closest_item(pdf_x, pdf_y)
        if selected:
            item_type, item = selected
            if item_type == 'point':
                self.delete_point(item)
                self.update_status(f"Deleted point ID {item['id']}")
            elif item_type == 'line':
                self.delete_line(item)
                self.update_status(f"Deleted line ID {item['id']}")
            elif item_type == 'curve_arc':
                self.delete_curve(item)
                self.update_status(f"Deleted curve ID {item['id']}")
            else:
                self.update_status("No deletable item found")
            self.selected_item = None
            self.display_page()
            self.update_points_label()
        else:
            self.update_status("No item close enough to delete")

    def find_items_near(self, pdf_x, pdf_y):
        """Return a list of nearby candidates (kind, item, dist) without prompting.
        Same proximity rules as find_closest_item.
        """
        try:
            pixel_tolerance = 5
            pdf_tolerance_sq = (pixel_tolerance / float(self.zoom_level)) ** 2
        except Exception:
            pdf_tolerance_sq = 25.0

        candidates = []
        for point in self.user_points:
            if 'pdf_x' in point and 'pdf_y' in point:
                dist = (point['pdf_x'] - pdf_x) ** 2 + (point['pdf_y'] - pdf_y) ** 2
                if dist <= pdf_tolerance_sq:
                    candidates.append(('point', point, dist))

        for line in self.lines:
            try:
                start = next(p for p in self.user_points if p['id'] == line['start_id'])
                end = next(p for p in self.user_points if p['id'] == line['end_id'])
            except StopIteration:
                continue
            dist = self.point_to_line_distance(pdf_x, pdf_y, start, end)
            if dist <= pdf_tolerance_sq:
                candidates.append(('line', line, dist))

        for curve in self.curves:
            for arc_point in curve.get('arc_points_pdf', []):
                try:
                    ax = arc_point[self.A]
                    ay = arc_point[self.B]
                except Exception:
                    continue
                dist = (ax - pdf_x) ** 2 + (ay - pdf_y) ** 2
                if dist <= pdf_tolerance_sq:
                    candidates.append(('curve_arc', curve, dist))

        return candidates

    def find_closest_item(self, pdf_x, pdf_y):
        candidates = self.find_items_near(pdf_x, pdf_y)
        if not candidates:
            return None

        # If only one candidate, return it
        if len(candidates) == 1:
            kind, item, _ = candidates[0]
            return (kind, item)

        # Multiple candidates: ask user which to select. Present a simple numbered list with Z values where available.
        try:
            from tkinter import simpledialog, messagebox
            choices = []
            for idx, (kind, item, dist) in enumerate(candidates, start=1):
                if kind == 'point':
                    z = item.get('z', 0)
                    choices.append(f"{idx}: Point id={item.get('id')} z={z}")
                elif kind == 'line':
                    # Attempt to determine average Z of line endpoints
                    try:
                        s = next(p for p in self.user_points if p['id'] == item['start_id'])
                        e = next(p for p in self.user_points if p['id'] == item['end_id'])
                        z = (float(s.get('z', 0)) + float(e.get('z', 0))) / 2.0
                    except Exception:
                        z = 'n/a'
                    choices.append(f"{idx}: Line id={item.get('id')} z={z}")
                else:
                    z = item.get('z_level', item.get('z', 'n/a'))
                    choices.append(f"{idx}: Curve id={item.get('id')} z={z}")

            prompt = "Multiple items found near this location:\n" + "\n".join(choices) + "\nEnter number to select (or cancel):"
            ans = simpledialog.askstring("Select Item", prompt)
            if not ans:
                return None
            try:
                sel = int(ans.strip())
                if 1 <= sel <= len(candidates):
                    kind, item, _ = candidates[sel - 1]
                    return (kind, item)
            except Exception:
                messagebox.showinfo("Selection", "Invalid selection. No item selected.")
                return None
        except Exception:
            # If any GUI selection fails, fall back to returning the closest candidate (by distance)
            candidates.sort(key=lambda x: x[2])
            kind, item, _ = candidates[0]
            return (kind, item)

    def delete_point(self, point):
        pid = point.get('id')
        # Check if this point is part of any curve arc points
        curves_involving = [c for c in list(self.curves) if pid in c.get('arc_point_ids', [])]
        if curves_involving:
            # Warn the user: deleting this point will remove the entire curve (and its base line)
            names = ", ".join(str(c['id']) for c in curves_involving)
            resp = messagebox.askyesno("Delete Curve(s)", f"Point {pid} is part of curve(s) {names}.\nDelete the entire curve(s) and their base lines?")
            if not resp:
                self.update_status("Deletion cancelled by user.")
                return
            # User confirmed: delete each curve and its base line
            for c in curves_involving:
                try:
                    # delete_curve will remove arc points and markers
                    self.delete_curve(c)
                except Exception:
                    # best-effort removal
                    self.curves = [cc for cc in self.curves if cc['id'] != c['id']]
                # Delete base line if present
                base_line_id = c.get('base_line_id')
                if base_line_id:
                    bl = next((l for l in list(self.lines) if l.get('id') == base_line_id), None)
                    if bl:
                        try:
                            self.delete_line(bl)
                        except Exception:
                            self.lines = [ll for ll in self.lines if ll.get('id') != base_line_id]
                # Log deletion
                try:
                    self.deletion_log.append({'action': 'delete_curve_due_to_point', 'curve_id': c.get('id'), 'point_id': pid, 'time': datetime.now().isoformat()})
                except Exception:
                    pass

        # Proceed to remove the point itself
        self.user_points = [p for p in self.user_points if p.get('id') != pid]
        # remove any lines referencing this point
        self.lines = [l for l in self.lines if l.get('start_id') != pid and l.get('end_id') != pid]
        # remove any curves where start/end are this point
        self.curves = [c for c in self.curves if c.get('start_id') != pid and c.get('end_id') != pid]
        if pid in self.point_markers:
            try:
                self.canvas.delete(self.point_markers[pid])
            except Exception:
                pass
            try:
                del self.point_markers[pid]
            except Exception:
                pass
        # Log point deletion
        try:
            self.deletion_log.append({'action': 'delete_point', 'point_id': pid, 'time': datetime.now().isoformat()})
        except Exception:
            pass
        try:
            self.update_3d_plot()
        except Exception:
            pass

    def delete_line(self, line):
        lid = line.get('id')
        self.lines = [l for l in self.lines if l.get('id') != lid]
        if 'canvas_id' in line:
            try:
                self.canvas.delete(line['canvas_id'])
            except Exception:
                pass
        if 'text_id' in line:
            try:
                self.canvas.delete(line['text_id'])
            except Exception:
                pass
        # Log line deletion
        try:
            self.deletion_log.append({'action': 'delete_line', 'line_id': lid, 'time': datetime.now().isoformat()})
        except Exception:
            pass
        try:
            self.update_3d_plot()
        except Exception:
            pass

    def delete_curve(self, curve):
        cid = curve.get('id')
        # Delete arc points associated with this curve
        for arc_point_id in list(curve.get('arc_point_ids', [])):
            self.user_points = [p for p in self.user_points if p.get('id') != arc_point_id]
            # remove markers if present
            try:
                if arc_point_id in self.point_markers:
                    self.canvas.delete(self.point_markers[arc_point_id])
                    del self.point_markers[arc_point_id]
            except Exception:
                pass

        # Remove the curve entry
        self.curves = [c for c in self.curves if c.get('id') != cid]

        # Delete curve canvas items
        try:
            if 'canvas_id' in curve and curve.get('canvas_id'):
                self.canvas.delete(curve['canvas_id'])
        except Exception:
            pass
        for marker_id in curve.get('arc_point_marker_ids', []):
            try:
                self.canvas.delete(marker_id)
            except Exception:
                pass

        # Delete base line if present
        base_line_id = curve.get('base_line_id')
        if base_line_id:
            bl = next((l for l in list(self.lines) if l.get('id') == base_line_id), None)
            if bl:
                try:
                    self.delete_line(bl)
                except Exception:
                    self.lines = [ll for ll in self.lines if ll.get('id') != base_line_id]

        # Log curve deletion
        try:
            self.deletion_log.append({'action': 'delete_curve', 'curve_id': cid, 'time': datetime.now().isoformat()})
        except Exception:
            pass

        try:
            self.update_3d_plot()
        except Exception:
            pass

    def delete_selected(self):
        if not self.selected_item:
            return
        item_type, item = self.selected_item
        if item_type == 'point':
            self.delete_point(item)
        elif item_type == 'line':
            self.delete_line(item)
        elif item_type == 'curve_arc':
            self.delete_curve(item)
        self.selected_item = None
        self.display_page()
        self.update_points_label()
        self.update_status("Selected item deleted.")

    def point_to_line_distance(self, px, py, start, end):
        x1, y1 = start['pdf_x'], start['pdf_y']
        x2, y2 = end['pdf_x'], end['pdf_y']
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return (px - x1) ** 2 + (py - y1) ** 2
        t = ((px - x1) * dx + (py - y1) * dy) / (dx ** 2 + dy ** 2)
        t = max(0, min(1, t))
        x = x1 + t * dx
        y = y1 + t * dy
        return (px - x) ** 2 + (py - y) ** 2