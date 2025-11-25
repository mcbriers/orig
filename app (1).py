import tkinter as tk
from tkinter import filedialog, messagebox
import fitz
from PIL import Image, ImageTk
import io
import configparser
import os
import numpy as np
import json
import csv
from calibration import CalibrationMixin
from points_lines import PointsLinesMixin
from curves import CurvesMixin
from deletion import DeletionMixin
from utils import UtilsMixin


class PDFViewerApp(tk.Tk, CalibrationMixin, PointsLinesMixin, CurvesMixin, DeletionMixin, UtilsMixin):
    def __init__(self, root):
        self.master = root
        self.master.title("PDF Viewer - Track Definition")
        self.master.geometry("1400x900")
        Image.MAX_IMAGE_PIXELS = None

        self.A, self.B = 0, 1

        self.pdf_doc = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.photo_image = None
        self.canvas_image = None

        self.reference_points_pdf = []
        self.reference_points_real = []
        self.user_points = []

        self._drag_data = {"x": 0, "y": 0}
        self.calibration_mode = False
        self.calibration_step = 0
        self.transformation_matrix = None

        self.config_file = "config.ini"
        self.config = configparser.ConfigParser()
        self.load_config()

        self.lines = []
        self.current_line_points = []
        self.curves = []
        self.current_curve_points = []

        self.elevation_var = tk.StringVar(value="0.0")
        self.mode_var = tk.StringVar(value="calibration")
        self.point_id_counter = 1

        self.point_markers = {}
        self.calibration_markers = {}
        self.zoom_entry = None
        self.points_label = None
        self.calib_status = None
        self.status_label = None
        self.canvas = None
        self.vscroll = None
        self.hscroll = None

        self.selected_item = None

        self.build_ui()

    def build_ui(self):
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open PDF...", command=self.open_file)
        file_menu.add_command(label="Open Project...", command=self.open_project)
        file_menu.add_command(label="Save Project...", command=self.save_project)
        file_menu.add_command(label="Close PDF", command=self.close_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Clear Points", command=self.clear_points)
        edit_menu.add_command(label="Clear Calibration", command=self.clear_calibration)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        main_frame = tk.Frame(self.master)
        main_frame.pack(fill="both", expand=True)

        outer = tk.Frame(main_frame)
        outer.pack(side="left", fill="both", expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(outer, bg="grey", cursor="crosshair")
        self.vscroll = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.hscroll = tk.Scrollbar(outer, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="ew")

        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Button-3>", self.on_right_button_press)
        self.canvas.bind("<B3-Motion>", self.on_right_button_move)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_button_release)
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        self.master.bind("<Control-z>", lambda e: self.zoom_in())
        self.master.bind("<Control-x>", lambda e: self.zoom_out())
        self.master.bind("<Delete>", lambda e: self.delete_selected())

        control_panel = tk.Frame(main_frame, width=250, bg="lightgrey")
        control_panel.pack(side="right", fill="both", padx=5, pady=5)
        control_panel.pack_propagate(False)

        zoom_frame = tk.LabelFrame(control_panel, text="Zoom", padx=5, pady=5)
        zoom_frame.pack(fill='x', padx=5, pady=5)
        tk.Button(zoom_frame, text="Zoom In (Ctrl+Z)", command=self.zoom_in, bg="#4CAF50", fg="white").pack(fill='x', padx=2, pady=2)
        tk.Button(zoom_frame, text="Zoom Out (Ctrl+X)", command=self.zoom_out, bg="#2196F3", fg="white").pack(fill='x', padx=2, pady=2)
        tk.Button(zoom_frame, text="Fit Page", command=self.fit_page).pack(fill='x', padx=2, pady=2)

        zoom_input_frame = tk.Frame(zoom_frame)
        zoom_input_frame.pack(fill='x', padx=2, pady=2)
        tk.Label(zoom_input_frame, text="Zoom %:").pack(side="left")
        self.zoom_entry = tk.Entry(zoom_input_frame, width=6)
        self.zoom_entry.insert(0, "100")
        self.zoom_entry.pack(side="left", padx=2)
        tk.Button(zoom_input_frame, text="Set", command=self.set_zoom_from_entry).pack(side="left", padx=2)

        calib_frame = tk.LabelFrame(control_panel, text="Calibration", padx=5, pady=5)
        calib_frame.pack(fill='x', padx=5, pady=5)
        self.calib_status = tk.Label(calib_frame, text="Ready", bg="white", relief="sunken", wraplength=200)
        self.calib_status.pack(fill='x', padx=2, pady=2)

        point_frame = tk.LabelFrame(control_panel, text="Point Collection", padx=5, pady=5)
        point_frame.pack(fill='x', padx=5, pady=5)

        tk.Label(point_frame, text="Mode:").pack(anchor='w')
        mode_frame = tk.Frame(point_frame)
        mode_frame.pack(fill='x', pady=5)
        tk.Radiobutton(mode_frame, text="Calibration", variable=self.mode_var, value="calibration").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Coordinates", variable=self.mode_var, value="coordinates").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Lines", variable=self.mode_var, value="lines").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Curves", variable=self.mode_var, value="curves").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Duplication", variable=self.mode_var, value="duplication").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Deletion", variable=self.mode_var, value="deletion").pack(anchor="w", padx=10)

        tk.Label(point_frame, text="Level Name:").pack(pady=(10, 0))
        tk.Entry(point_frame, width=20, textvariable=self.elevation_var).pack(padx=5, pady=2)

        self.points_label = tk.Label(point_frame, text="Points: 0", bg="white", relief="sunken")
        self.points_label.pack(fill='x', padx=2, pady=2)

        tk.Button(point_frame, text="Save Project", command=self.save_project, bg="#4CAF50", fg="white").pack(fill='x', padx=2, pady=2)
        tk.Button(point_frame, text="Clear Points", command=self.clear_points).pack(fill='x', padx=2, pady=2)
        tk.Button(point_frame, text="Hide All", command=self.hide_all_elements, bg="#FF9800", fg="white").pack(fill='x', padx=2, pady=2)
        tk.Button(point_frame, text="Show All", command=self.show_all_elements, bg="#4CAF50", fg="white").pack(fill='x', padx=2, pady=2)

        status_frame = tk.Frame(self.master, bg="white", relief="sunken", bd=1)
        status_frame.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status_frame, text="Ready | Ctrl+Z/X: Zoom | Click: Add Point", bg="white", anchor="w")
        self.status_label.pack(fill="x", padx=5, pady=2)

    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['General'] = {}
            self.config['View'] = {}
            self.config['Calibration'] = {}
            self.config['Points'] = {}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        self.update_status("Configuration saved")

    def update_status(self, message):
        self.status_label.config(text=message)
        self.master.update_idletasks()

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            try:
                self.close_file()
                self.pdf_doc = fitz.open(file_path)
                self.current_page = 0
                self.total_pages = len(self.pdf_doc)
                self.zoom_level = 1.0
                self.clear_points()
                self.clear_calibration()
                self.display_page()
                self.update_status(f"Loaded: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open PDF: {e}")

    def close_file(self):
        if self.pdf_doc:
            self.pdf_doc.close()
            self.pdf_doc = None
            self.current_page = 0
            self.total_pages = 0
            self.canvas.delete("all")
            self.point_markers.clear()
            self.calibration_markers.clear()
            self.update_status("PDF closed")

    def display_page(self):
        if not self.pdf_doc:
            return
        try:
            page = self.pdf_doc[self.current_page]
            mat = fitz.Matrix(self.zoom_level, self.zoom_level)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            self.photo_image = ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))
            self.canvas.delete("all")
            self.canvas_image = self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)
            self.redraw_markers()
            img_width = self.photo_image.width()
            img_height = self.photo_image.height()
            self.canvas.config(scrollregion=(0, 0, img_width, img_height))
            self.canvas.tag_raise("calibration_point")
            self.canvas.tag_raise("user_point")
            self.canvas.tag_raise("user_line")
            self.canvas.tag_raise("line_label")
            self.canvas.tag_raise("user_curve")
            self.canvas.tag_raise("arc_point")
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, f"{self.zoom_level*100:.0f}")
        except Exception as e:
            self.update_status(f"Error displaying page: {e}")

    def zoom_with_focus(self, zoom_factor, x, y):
        if not self.pdf_doc:
            return
        old_zoom = self.zoom_level
        x_scroll = self.canvas.canvasx(x)
        y_scroll = self.canvas.canvasy(y)
        x_pdf = x_scroll / old_zoom
        y_pdf = y_scroll / old_zoom
        self.zoom_level *= zoom_factor
        self.display_page()
        img_width = self.photo_image.width()
        img_height = self.photo_image.height()
        x_scroll_new = x_pdf * self.zoom_level
        y_scroll_new = y_pdf * self.zoom_level
        frac_x = (x_scroll_new - x) / img_width if img_width > 0 else 0
        frac_y = (y_scroll_new - y) / img_height if img_height > 0 else 0
        frac_x = max(0, min(1, frac_x))
        frac_y = max(0, min(1, frac_y))
        self.canvas.xview_moveto(frac_x)
        self.canvas.yview_moveto(frac_y)

    def redraw_markers(self):
        self.point_markers.clear()
        self.calibration_markers.clear()
        size = 5

        for i, (px, py) in enumerate(self.reference_points_pdf):
            x = px * self.zoom_level
            y = py * self.zoom_level
            m_id = self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                          outline="red", fill="red", tags="calibration_point", width=2)
            self.calibration_markers[i] = m_id

        for point in self.user_points:
            if 'pdf_x' in point and 'pdf_y' in point:
                x = point['pdf_x'] * self.zoom_level
                y = point['pdf_y'] * self.zoom_level
                m_id = self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                              outline="blue", fill="blue", tags="user_point", width=2)
                self.point_markers[point['id']] = m_id

        for line in self.lines:
            start = next(p for p in self.user_points if p['id'] == line['start_id'])
            end = next(p for p in self.user_points if p['id'] == line['end_id'])
            x1 = start['pdf_x'] * self.zoom_level
            y1 = start['pdf_y'] * self.zoom_level
            x2 = end['pdf_x'] * self.zoom_level
            y2 = end['pdf_y'] * self.zoom_level
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill="orange", width=4, tags="user_line")
            if 'canvas_id' in line:
                try:
                    self.canvas.delete(line['canvas_id'])
                except:
                    pass
            line['canvas_id'] = line_id
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_offset = 15
            text_y = mid_y - text_offset if y1 < y2 else mid_y + text_offset
            if 'text_id' in line:
                self.canvas.coords(line['text_id'], mid_x, text_y)
            else:
                text_id = self.canvas.create_text(mid_x, text_y, text=str(line['id']), fill="orange", tags="line_label")
                line['text_id'] = text_id

        for curve in self.curves:
            coords = []
            for px, py in curve['arc_points_pdf']:
                coords.extend([px * self.zoom_level, py * self.zoom_level])
            curve_id = self.canvas.create_line(*coords, fill="purple", width=2, smooth=True, splinesteps=36, tags="user_curve")
            if 'canvas_id' in curve:
                try:
                    self.canvas.delete(curve['canvas_id'])
                except:
                    pass
            curve['canvas_id'] = curve_id
            size = 4
            curve['arc_point_marker_ids'] = []
            for px, py in curve['arc_points_pdf']:
                x = px * self.zoom_level
                y = py * self.zoom_level
                marker_id = self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                                   outline="green", fill="green", tags="arc_point", width=2)
                curve['arc_point_marker_ids'].append(marker_id)

        self.canvas.tag_raise("calibration_point")
        self.canvas.tag_raise("user_point")
        self.canvas.tag_raise("user_line")
        self.canvas.tag_raise("line_label")
        self.canvas.tag_raise("user_curve")
        self.canvas.tag_raise("arc_point")

    def set_mode(self, mode_name):
        self.mode_var.set(mode_name)
        if mode_name == "calibration":
            self.calibration_mode = True
            self.calibration_step = 0
            self.reference_points_pdf.clear()
            self.reference_points_real.clear()
            self.calibration_markers.clear()
            self.current_line_points.clear()
            self.current_curve_points.clear()
            self.calib_status.config(text="Calibration started: click 2 reference points")
            self.update_status("Calibration mode activated")
        else:
            self.calibration_mode = False
            self.calib_status.config(text="Ready")
            self.canvas.delete("calibration_point")
            self.update_status(f"Mode changed to {mode_name}")

    def set_zoom_from_entry(self):
        try:
            zoom_percent = float(self.zoom_entry.get())
            if zoom_percent < 10 or zoom_percent > 1000:
                raise ValueError("Zoom must be between 10 and 1000")
            self.zoom_level = zoom_percent / 100.0
            self.display_page()
            self.update_status(f"Zoom set to {zoom_percent:.1f}%")
        except ValueError as e:
            messagebox.showerror("Invalid Zoom", f"Invalid zoom value: {e}")
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, f"{self.zoom_level*100:.0f}")

    def zoom_in(self):
        if self.pdf_doc:
            self.zoom_with_focus(1.2, self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)

    def zoom_out(self):
        if self.pdf_doc:
            self.zoom_with_focus(1 / 1.2, self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)

    def fit_page(self):
        if not self.pdf_doc:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        page = self.pdf_doc[self.current_page]
        page_rect = page.bound()
        page_width = page_rect.width
        page_height = page_rect.height
        zoom_x = canvas_width / page_width
        zoom_y = canvas_height / page_height
        self.zoom_level = min(zoom_x, zoom_y) * 0.95
        self.display_page()

    def on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            delta = -1
            zoom_factor = 0.8
        else:
            delta = 1
            zoom_factor = 1.2
        if event.state & 0x1:
            self.canvas.xview_scroll(delta, "units")
        elif event.state & 0x4:
            self.zoom_with_focus(zoom_factor, event.x, event.y)
        else:
            self.canvas.yview_scroll(delta, "units")

    def on_right_button_press(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_right_button_move(self, event):
        delta_x = (self._drag_data["x"] - event.x)
        delta_y = (self._drag_data["y"] - event.y)
        self.canvas.xview_scroll(delta_x // 6, "units")
        self.canvas.yview_scroll(delta_y // 6, "units")
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_right_button_release(self, event):
        pass

    def on_mouse_move(self, event):
        if not self.pdf_doc:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level
        if self.calibration_mode:
            self.calib_status.config(text=f"Pos: ({pdf_x:.1f}, {pdf_y:.1f})\nStep: {self.calibration_step}")

    def on_left_click(self, event):
        if not self.pdf_doc:
            return
        mode = self.mode_var.get()
        if mode == "deletion":
            self.handle_deletion_click(event)
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level

        if mode == "calibration":
            self.handle_calibration_click(canvas_x, canvas_y, pdf_x, pdf_y)
        elif mode == "coordinates":
            self.handle_coordinates_click(canvas_x, canvas_y, pdf_x, pdf_y)
        elif mode == "lines":
            self.handle_lines_click(canvas_x, canvas_y)
        elif mode == "curves":
            self.handle_curves_click(canvas_x, canvas_y)
        elif mode == "duplication":
            self.handle_duplication_click(event)
        else:
            self.update_status(f"Unknown mode: {mode}")

    def save_project(self):
        if not self.user_points:
            messagebox.showwarning("No Data", "No points have been collected yet.")
            return
        project_path = filedialog.asksaveasfilename(defaultextension=".dig",
                                                    filetypes=[("DIG Project Files", "*.dig")],
                                                    title="Save Project As")
        if not project_path:
            return
        project_data = {
            "pdf_path": self.pdf_doc.name if self.pdf_doc else "",
            "calibration_pdf_points": self.reference_points_pdf,
            "calibration_real_points": self.reference_points_real,
            "transformation_matrix": self.transformation_matrix.tolist() if self.transformation_matrix is not None else None,
            "points": self.user_points,
            "lines": self.lines,
            "curves": self.curves,
            "zoom_level": self.zoom_level,
            "last_mode": self.mode_var.get()
        }
        try:
            with open(project_path, 'w') as f:
                json.dump(project_data, f, indent=4)
            messagebox.showinfo("Saved", f"Project saved to {project_path}")
            self.update_status(f"Project saved to {project_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving project: {e}")

    def open_project(self):
        project_path = filedialog.askopenfilename(filetypes=[("DIG Project Files", "*.dig")])
        if not project_path:
            return
        try:
            with open(project_path, 'r') as f:
                project_data = json.load(f)
            pdf_path = project_data.get("pdf_path", "")
            if not os.path.exists(pdf_path):
                messagebox.showwarning("PDF Missing", f"PDF file not found: {pdf_path}")
                return
            self.close_file()
            self.pdf_doc = fitz.open(pdf_path)
            self.current_page = 0
            self.total_pages = len(self.pdf_doc)
            self.reference_points_pdf = project_data.get("calibration_pdf_points", [])
            self.reference_points_real = project_data.get("calibration_real_points", [])
            tmatrix = project_data.get("transformation_matrix")
            if tmatrix:
                self.transformation_matrix = np.array(tmatrix)
            else:
                self.transformation_matrix = None
            self.user_points = project_data.get("points", [])
            self.lines = project_data.get("lines", [])
            self.curves = project_data.get("curves", [])
            self.zoom_level = project_data.get("zoom_level", 1.0)
            if self.zoom_entry:
                self.zoom_entry.delete(0, tk.END)
                self.zoom_entry.insert(0, f"{self.zoom_level*100:.0f}")
            self.display_page()
            self.update_points_label()
            self.update_status(f"Project loaded: {project_path}")
            last_mode = project_data.get("last_mode", "coordinates")
            self.mode_var.set(last_mode)
            self.set_mode(last_mode)
        except Exception as e:
            messagebox.showerror("Load Error", f"Error loading project: {e}")

    def export_data(self):  
        if self.transformation_matrix is None:  
            messagebox.showwarning("Export Error", "Calibration required before export.")  
            return  
        from tkinter import simpledialog  
        project_name = simpledialog.askstring("Project Name", "Enter project name for export:")  
        if not project_name:  
            return  
        export_dir = os.path.dirname(self.config_file)  
        if not export_dir:  
            export_dir = os.getcwd()  
        
        points_file = os.path.join(export_dir, f"{project_name}_points.txt")  
        lines_file = os.path.join(export_dir, f"{project_name}_lines.txt")  
        curves_file = os.path.join(export_dir, f"{project_name}_curves.txt")  
        sql_file = os.path.join(export_dir, f"{project_name}_insert.sql")  
        
        # Export CSV files
        with open(points_file, 'w') as f:  
            f.write("ID,X,Y,Z\n")  
            for point in self.user_points:  
                f.write(f"{point['id']},{point['real_x']},{point['real_y']},{point['z']}\n")  
        
        with open(lines_file, 'w') as f:  
            writer = csv.writer(f)
            writer.writerow(['LineID', 'StartPointID', 'EndPointID', 'StartPointZ', 'EndPointZ'])  #f.write("ID,StartID,EndID\n")  
            for line in self.lines:  
                start_id = line['start_id']
                end_id = line['end_id']
                # Find Z values for start and end points
                start_z = next((p['z'] for p in self.user_points if p['id'] == start_id), None)
                end_z = next((p['z'] for p in self.user_points if p['id'] == end_id), None)
                writer.writerow([line['id'], start_id, end_id, start_z, end_z]) #              f.write(f"{line['id']},{line['start_id']},{line['end_id']}\n")  
        
        with open(curves_file, 'w') as f:  
            f.write("Position,PointID,LineID\n")  
            for curve in self.curves:  
                line_id = next((l['id'] for l in self.lines if  
                    (l['start_id'] == curve['start_id'] and l['end_id'] == curve['end_id']) or  
                    (l['start_id'] == curve['end_id'] and l['end_id'] == curve['start_id'])  
                ), 0)  
                for i, arc_point_id in enumerate(curve['arc_point_ids']):  
                    f.write(f"{i},{arc_point_id},{line_id}\n")  
        
        # Generate SQL file with IDENTITY_INSERT
        with open(sql_file, 'w') as f:
            f.write("-- SQL Insert Script for SeasPathDB\n")
            f.write("-- Generated from 3DMaker Export\n\n")
            
            # Points table
            f.write("-- Insert Visualization_Coordinate (Points)\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;\n")
            for point in self.user_points:
                f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) ")
                f.write(f"VALUES ({point['id']}, {point['real_x']}, {point['z']}, {point['real_y']}, '3D Visualisation');\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate OFF;\n\n")
            
            # Lines table
            f.write("-- Insert Visualization_Edge (Lines)\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge ON;\n")
            for line in self.lines:
                f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Edge (Id, TailCoordenate, HeadCoordenate) ")
                f.write(f"VALUES ({line['id']}, {line['start_id']}, {line['end_id']});\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Edge OFF;\n\n")
            
            # Curves table
            f.write("-- Insert Visualization_Curve (Curves)\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;\n")
            curve_id = 1
            for curve in self.curves:
                line_id = next((l['id'] for l in self.lines if  
                    (l['start_id'] == curve['start_id'] and l['end_id'] == curve['end_id']) or  
                    (l['start_id'] == curve['end_id'] and l['end_id'] == curve['start_id'])  
                ), 0)
                for position, arc_point_id in enumerate(curve['arc_point_ids']):
                    f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) ")
                    f.write(f"VALUES ({curve_id}, {position}, {arc_point_id}, {line_id});\n")
                    curve_id += 1
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;\n")
        
        messagebox.showinfo("Export Success", f"Exported data to {export_dir}\nFiles: {project_name}_points.txt, {project_name}_lines.txt, {project_name}_curves.txt, {project_name}_insert.sql")

    def handle_duplication_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level

        # Find closest entity
        selected = self.find_closest_item(pdf_x, pdf_y)
        if selected is None:
            self.update_status("No entity close enough to duplicate.")
            return

        entity_type, entity = selected

        # Ask for Z values
        from tkinter import simpledialog
        z_input = simpledialog.askstring(
            "Duplicate Entity",
            "Enter Z values (comma-delimited):\nExample: 1,2,3"
        )
        if not z_input:
            return

        try:
            z_values = [float(z.strip()) for z in z_input.split(',')]
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid Z values.")
            return

        # Duplicate based on entity type
        if entity_type == 'point':
            self.duplicate_point(entity, z_values)
        elif entity_type == 'line':
            self.duplicate_line(entity, z_values)
        elif entity_type == 'curve_arc':
            self.duplicate_curve(entity, z_values)

        self.redraw_markers()
        self.update_points_label()
        self.update_status(f"Duplicated {entity_type} at {len(z_values)} Z levels.")

    def duplicate_point(self, point, z_values):
        for z in z_values:
            new_point = point.copy()
            new_point['id'] = self.point_id_counter
            new_point['z'] = z
            self.user_points.append(new_point)
            self.point_id_counter += 1

    def duplicate_line(self, line, z_values):
        for z in z_values:
            # Get start and end points
            start = next(p for p in self.user_points if p['id'] == line['start_id'])
            end = next(p for p in self.user_points if p['id'] == line['end_id'])

            # Create new points at new Z level
            new_start = start.copy()
            new_start['id'] = self.point_id_counter
            new_start['z'] = z
            self.user_points.append(new_start)
            start_id = self.point_id_counter
            self.point_id_counter += 1

            new_end = end.copy()
            new_end['id'] = self.point_id_counter
            new_end['z'] = z
            self.user_points.append(new_end)
            end_id = self.point_id_counter
            self.point_id_counter += 1

            # Create new line
            new_line = line.copy()
            new_line['id'] = len(self.lines) + 1
            new_line['start_id'] = start_id
            new_line['end_id'] = end_id
            self.lines.append(new_line)

    def duplicate_curve(self, curve, z_values):
        for z in z_values:
            # Duplicate all arc points at new Z level
            new_arc_point_ids = []
            for arc_point_id in curve['arc_point_ids']:
                orig_point = next(p for p in self.user_points if p['id'] == arc_point_id)
                new_point = orig_point.copy()
                new_point['id'] = self.point_id_counter
                new_point['z'] = z
                self.user_points.append(new_point)
                new_arc_point_ids.append(self.point_id_counter)
                self.point_id_counter += 1

            # Create new curve
            new_curve = curve.copy()
            new_curve['id'] = len(self.curves) + 1
            new_curve['arc_point_ids'] = new_arc_point_ids
            new_curve['z_level'] = z
            self.curves.append(new_curve)


    def hide_all_elements(self):
        # Hide existing points
        for marker_id in self.point_markers.values():
            self.canvas.itemconfig(marker_id, state='hidden')
        # Hide existing lines
        for line in self.lines:
            if 'canvas_id' in line:
                self.canvas.itemconfig(line['canvas_id'], state='hidden')
            if 'text_id' in line:
                self.canvas.itemconfig(line['text_id'], state='hidden')
        # Hide existing curves and their markers
        for curve in self.curves:
            if 'canvas_id' in curve:
                self.canvas.itemconfig(curve['canvas_id'], state='hidden')
            for marker_id in curve.get('arc_point_marker_ids', []):
                self.canvas.itemconfig(marker_id, state='hidden')
        self.elements_hidden = True
        self.update_status("All existing elements hidden. New elements will be visible.")

    def show_all_elements(self):
        # Show all points
        for marker_id in self.point_markers.values():
            self.canvas.itemconfig(marker_id, state='normal')
        # Show all lines
        for line in self.lines:
            if 'canvas_id' in line:
                self.canvas.itemconfig(line['canvas_id'], state='normal')
            if 'text_id' in line:
                self.canvas.itemconfig(line['text_id'], state='normal')
        # Show all curves and their markers
        for curve in self.curves:
            if 'canvas_id' in curve:
                self.canvas.itemconfig(curve['canvas_id'], state='normal')
            for marker_id in curve.get('arc_point_marker_ids', []):
                self.canvas.itemconfig(marker_id, state='normal')
        self.elements_hidden = False
        self.update_status("All elements shown.")


    def run(self):
        self.master.mainloop()