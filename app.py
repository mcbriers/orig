import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import fitz
from PIL import Image, ImageTk
import io
import configparser
import shutil
import datetime
import os
import numpy as np
import json
import csv
from calibration import CalibrationMixin
from points_lines import PointsLinesMixin
from curves import CurvesMixin
from deletion import DeletionMixin
from utils import UtilsMixin

# digitizer helpers (migration, id allocation, schema validation)
try:
    from digitizer.id_alloc import IDAllocator
    from digitizer.migrate import migrate_project
    from digitizer.schema import validate_project
except Exception:
    IDAllocator = None
    migrate_project = None
    validate_project = None


class PDFViewerApp(CalibrationMixin, PointsLinesMixin, CurvesMixin, DeletionMixin, UtilsMixin):
    def __init__(self, root):
        # This class composes behavior via mixins and uses an external root window.
        # Do not subclass tk.Tk directly when a root is provided.
        self.master = root
        self.master.title("PDF Viewer - Track Definition")
        # Start maximized for better workspace
        try:
            self.master.state('zoomed')
        except Exception:
            # fallback to a sensible default size
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
        # Configurable number of interior points for curves (default 4 -> total 6 points per curve)
        try:
            self.curve_interior_points = int(self.config['General'].get('curve_interior_points', '4'))
        except Exception:
            self.curve_interior_points = 4

        # Centralized allocator (falls back to simple counter if digitizer package absent)
        if IDAllocator is not None:
            self.allocator = IDAllocator()
        else:
            self.allocator = None

        # Deletion log to track removed items
        self.deletion_log = []

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

    # Centralized ID helpers to keep legacy counters synchronized with allocator
    def next_point_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                nid = self.allocator.next_point_id()
                # keep legacy counter at least in sync
                try:
                    self.point_id_counter = max(self.point_id_counter, int(getattr(self.allocator, 'point_counter', self.point_id_counter)))
                except Exception:
                    pass
                return nid
        except Exception:
            pass
        nid = self.point_id_counter
        self.point_id_counter += 1
        return nid

    def next_line_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                lid = self.allocator.next_line_id()
                try:
                    # if allocator tracks line counter, keep in sync
                    self.line_id_counter = max(getattr(self, 'line_id_counter', 0), int(getattr(self.allocator, 'line_counter', getattr(self, 'line_id_counter', 0))))
                except Exception:
                    pass
                return lid
        except Exception:
            pass
        # fallback: use len(self.lines)+1 for historical behavior
        lid = len(self.lines) + 1
        return lid

    def next_curve_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                cid = self.allocator.next_curve_id()
                try:
                    self.curve_id_counter = max(getattr(self, 'curve_id_counter', 0), int(getattr(self.allocator, 'curve_counter', getattr(self, 'curve_id_counter', 0))))
                except Exception:
                    pass
                return cid
        except Exception:
            pass
        return len(self.curves) + 1

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

        # Left: Notebook with 2D view and 3D view
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(side="left", fill="both", expand=True)

        # 2D view tab
        view2d_frame = tk.Frame(self.notebook)
        view2d_frame.grid_rowconfigure(0, weight=1)
        view2d_frame.grid_columnconfigure(0, weight=1)
        self.notebook.add(view2d_frame, text="2D Viewer")

        self.canvas = tk.Canvas(view2d_frame, bg="grey", cursor="crosshair")
        self.vscroll = tk.Scrollbar(view2d_frame, orient="vertical", command=self.canvas.yview)
        self.hscroll = tk.Scrollbar(view2d_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="ew")

        # 3D view tab (matplotlib) - created lazily
        self.view3d_frame = tk.Frame(self.notebook)
        self.notebook.add(self.view3d_frame, text="3D View")
        # Editor tab for listing and editing entities
        self.editor_frame = tk.Frame(self.notebook)
        self.notebook.add(self.editor_frame, text="Editor")
        self._build_editor_tab(self.editor_frame)

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

        # Initialize 3D plotting support (lazy import)
        self._3d_initialized = False
        # 3D view preferences
        self._3d_point_size = 20
        self._3d_point_color = 'b'
        self._3d_line_color = 'orange'
        self._3d_curve_color = 'purple'
        self._3d_theme = 'default'
        self._3d_show_grid = True
        self._3d_elev = 30
        self._3d_azim = -60

    def _init_3d_canvas(self):
        if self._3d_initialized:
            return
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.figure import Figure
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        except Exception as e:
            messagebox.showerror("3D View Error", f"Matplotlib required for 3D view: {e}")
            return

        self._3d_fig = Figure(figsize=(6, 6))
        self._3d_ax = self._3d_fig.add_subplot(111, projection='3d')
        self._3d_canvas = FigureCanvasTkAgg(self._3d_fig, master=self.view3d_frame)
        # Toolbar frame above the canvas
        toolbar = tk.Frame(self.view3d_frame)
        toolbar.pack(side='top', fill='x', padx=2, pady=2)

        tk.Button(toolbar, text='Reset View', command=self.reset_3d_view).pack(side='left')
        tk.Button(toolbar, text='Zoom Extents', command=self.reset_3d_view).pack(side='left')
        tk.Button(toolbar, text='Point -', command=self.decrease_point_size).pack(side='left', padx=(6, 0))
        tk.Button(toolbar, text='Point +', command=self.increase_point_size).pack(side='left')

        tk.Label(toolbar, text='Theme:').pack(side='left', padx=(12, 0))
        theme_cb = ttk.Combobox(toolbar, values=['default', 'dark'], width=8)
        theme_cb.set(self._3d_theme)
        theme_cb.pack(side='left')
        def _on_theme(event=None):
            self.set_3d_theme(theme_cb.get())
        theme_cb.bind('<<ComboboxSelected>>', _on_theme)

        grid_btn = tk.Checkbutton(toolbar, text='Grid', variable=tk.BooleanVar(value=self._3d_show_grid), command=self.toggle_3d_grid)
        # We maintain our own flag; configure the checkbutton to reflect it
        grid_btn_var = tk.BooleanVar(value=self._3d_show_grid)
        grid_btn.config(variable=grid_btn_var)
        grid_btn.pack(side='left', padx=(8, 0))

        self._3d_toolbar_vars = {'theme_cb': theme_cb, 'grid_var': grid_btn_var}

        self._3d_canvas.get_tk_widget().pack(fill='both', expand=True)
        # Add Matplotlib navigation toolbar (rotate/pan/zoom)
        try:
            nav_toolbar = NavigationToolbar2Tk(self._3d_canvas, self.view3d_frame)
            nav_toolbar.update()
            nav_toolbar.pack(side='top', fill='x')
        except Exception:
            pass
        # Connect Matplotlib scroll_event as an additional reliable wheel handler
        try:
            try:
                self._3d_canvas.mpl_connect('scroll_event', self._on_3d_mpl_scroll)
            except Exception:
                self._3d_fig.canvas.mpl_connect('scroll_event', self._on_3d_mpl_scroll)
        except Exception:
            pass
        # Bind mouse wheel for 3D zoom (Windows: <MouseWheel>, Linux: Button-4/5)
        try:
            w = self._3d_canvas.get_tk_widget()
            w.bind("<MouseWheel>", self._on_3d_mousewheel)
            w.bind("<Button-4>", self._on_3d_mousewheel)
            w.bind("<Button-5>", self._on_3d_mousewheel)
        except Exception:
            pass
        self._3d_initialized = True

    # --- Editor tab implementation ---
    def _build_editor_tab(self, parent):
        # Left: lists, Right: editor details
        left = tk.Frame(parent)
        left.pack(side='left', fill='y', padx=4, pady=4)
        right = tk.Frame(parent)
        right.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        # Points treeview (replaces listbox + hide column)
        points_frame = tk.Frame(left)
        points_frame.pack(anchor='nw', pady=(0,6))
        tk.Label(points_frame, text='Points').grid(row=0, column=0, sticky='w')
        self.points_tv = ttk.Treeview(points_frame, columns=('id', 'coords', 'z', 'hidden'), show='headings', height=10)
        self.points_tv.heading('id', text='ID')
        self.points_tv.heading('coords', text='Coords')
        self.points_tv.heading('z', text='Z')
        self.points_tv.heading('hidden', text='Hidden')
        self.points_tv.column('id', width=40, anchor='center')
        self.points_tv.column('coords', width=120)
        self.points_tv.column('z', width=50, anchor='center')
        self.points_tv.column('hidden', width=50, anchor='center')
        self.points_tv.grid(row=1, column=0, sticky='ns')
        self.points_tv.bind('<<TreeviewSelect>>', self._on_point_select)

        # Lines treeview
        lines_frame = tk.Frame(left)
        lines_frame.pack(anchor='nw', pady=(8,6))
        tk.Label(lines_frame, text='Lines').grid(row=0, column=0, sticky='w')
        self.lines_tv = ttk.Treeview(lines_frame, columns=('id', 'ends', 'hidden'), show='headings', height=8)
        self.lines_tv.heading('id', text='ID')
        self.lines_tv.heading('ends', text='Start->End')
        self.lines_tv.heading('hidden', text='Hidden')
        self.lines_tv.column('id', width=40, anchor='center')
        self.lines_tv.column('ends', width=120)
        self.lines_tv.column('hidden', width=50, anchor='center')
        self.lines_tv.grid(row=1, column=0, sticky='ns')
        self.lines_tv.bind('<<TreeviewSelect>>', self._on_line_select)

        # Curves treeview
        curves_frame = tk.Frame(left)
        curves_frame.pack(anchor='nw', pady=(8,6))
        tk.Label(curves_frame, text='Curves').grid(row=0, column=0, sticky='w')
        self.curves_tv = ttk.Treeview(curves_frame, columns=('id', 'pts', 'z', 'hidden'), show='headings', height=8)
        self.curves_tv.heading('id', text='ID')
        self.curves_tv.heading('pts', text='Points')
        self.curves_tv.heading('z', text='Z')
        self.curves_tv.heading('hidden', text='Hidden')
        self.curves_tv.column('id', width=40, anchor='center')
        self.curves_tv.column('pts', width=80, anchor='center')
        self.curves_tv.column('z', width=50, anchor='center')
        self.curves_tv.column('hidden', width=50, anchor='center')
        self.curves_tv.grid(row=1, column=0, sticky='ns')
        self.curves_tv.bind('<<TreeviewSelect>>', self._on_curve_select)

        # Right: detail editor
        dframe = tk.LabelFrame(right, text='Edit Entity')
        dframe.pack(fill='both', expand=True)

        # Point edit fields
        tk.Label(dframe, text='Point ID:').grid(row=0, column=0, sticky='e')
        self.point_id_var = tk.StringVar()
        tk.Entry(dframe, textvariable=self.point_id_var, state='disabled').grid(row=0, column=1, sticky='w')

        tk.Label(dframe, text='Real X:').grid(row=1, column=0, sticky='e')
        self.point_realx_var = tk.StringVar()
        tk.Entry(dframe, textvariable=self.point_realx_var).grid(row=1, column=1, sticky='w')

        tk.Label(dframe, text='Real Y:').grid(row=2, column=0, sticky='e')
        self.point_realy_var = tk.StringVar()
        tk.Entry(dframe, textvariable=self.point_realy_var).grid(row=2, column=1, sticky='w')

        tk.Label(dframe, text='Z:').grid(row=3, column=0, sticky='e')
        self.point_z_var = tk.StringVar()
        tk.Entry(dframe, textvariable=self.point_z_var).grid(row=3, column=1, sticky='w')
        # Hide in 3D checkbox for point
        self.point_hide_var = tk.BooleanVar(value=False)
        tk.Checkbutton(dframe, text='Hide in 3D', variable=self.point_hide_var).grid(row=4, column=0, columnspan=2, sticky='w')

        tk.Button(dframe, text='Apply Point Edit', command=self.apply_point_edit).grid(row=5, column=0, columnspan=2, pady=6)
        tk.Button(dframe, text='Delete Selected', command=self.editor_delete_selected).grid(row=5, column=0, columnspan=2, pady=6)

        # Line editor controls below
        lframe = tk.LabelFrame(right, text='Line Editor')
        lframe.pack(fill='x', pady=6)
        tk.Label(lframe, text='Line ID:').grid(row=0, column=0, sticky='e')
        self.line_id_var = tk.StringVar()
        tk.Entry(lframe, textvariable=self.line_id_var, state='disabled').grid(row=0, column=1, sticky='w')
        tk.Label(lframe, text='Start Point ID:').grid(row=1, column=0, sticky='e')
        self.line_start_cb = ttk.Combobox(lframe, values=[], width=8)
        self.line_start_cb.grid(row=1, column=1, sticky='w')
        tk.Label(lframe, text='End Point ID:').grid(row=2, column=0, sticky='e')
        self.line_end_cb = ttk.Combobox(lframe, values=[], width=8)
        self.line_end_cb.grid(row=2, column=1, sticky='w')
        # Hide in 3D checkbox for line
        self.line_hide_var = tk.BooleanVar(value=False)
        tk.Checkbutton(lframe, text='Hide in 3D', variable=self.line_hide_var).grid(row=3, column=0, columnspan=2, sticky='w')
        tk.Button(lframe, text='Apply Line Edit', command=self.apply_line_edit).grid(row=4, column=0, columnspan=2, pady=6)

        # Curve editor
        cframe = tk.LabelFrame(right, text='Curve Editor')
        cframe.pack(fill='x', pady=6)
        tk.Label(cframe, text='Curve ID:').grid(row=0, column=0, sticky='e')
        self.curve_id_var = tk.StringVar()
        tk.Entry(cframe, textvariable=self.curve_id_var, state='disabled').grid(row=0, column=1, sticky='w')
        tk.Label(cframe, text='Z Level:').grid(row=1, column=0, sticky='e')
        self.curve_z_var = tk.StringVar()
        tk.Entry(cframe, textvariable=self.curve_z_var).grid(row=1, column=1, sticky='w')
        # Hide in 3D checkbox for curve
        self.curve_hide_var = tk.BooleanVar(value=False)
        tk.Checkbutton(cframe, text='Hide in 3D', variable=self.curve_hide_var).grid(row=2, column=0, columnspan=2, sticky='w')
        tk.Button(cframe, text='Apply Curve Edit', command=self.apply_curve_edit).grid(row=3, column=0, columnspan=2, pady=6)

        # Fill lists
        self.refresh_editor_lists()

    def refresh_editor_lists(self):
        # Points
        try:
            # treeview: clear and populate
            for it in self.points_tv.get_children():
                self.points_tv.delete(it)
            for p in self.user_points:
                coords = f"({p.get('real_x', p.get('pdf_x'))}, {p.get('real_y', p.get('pdf_y'))})"
                hidden_mark = '✓' if p.get('hidden', False) else ''
                self.points_tv.insert('', 'end', iid=f"p_{p['id']}", values=(p['id'], coords, p.get('z', 0), hidden_mark))
        except Exception:
            pass

        # Lines
        try:
            for it in self.lines_tv.get_children():
                self.lines_tv.delete(it)
            for l in self.lines:
                ends = f"{l['start_id']} -> {l['end_id']}"
                hidden_mark = '✓' if l.get('hidden', False) else ''
                self.lines_tv.insert('', 'end', iid=f"l_{l['id']}", values=(l['id'], ends, hidden_mark))
        except Exception:
            pass

        # Curves
        try:
            for it in self.curves_tv.get_children():
                self.curves_tv.delete(it)
            for c in self.curves:
                pts = len(c.get('arc_point_ids', []))
                zval = c.get('z_level', c.get('z', 0))
                hidden_mark = '✓' if c.get('hidden', False) else ''
                self.curves_tv.insert('', 'end', iid=f"c_{c['id']}", values=(c['id'], pts, zval, hidden_mark))
        except Exception:
            pass

        # Update combobox options for point IDs
        try:
            ids = [p['id'] for p in self.user_points]
            self.line_start_cb['values'] = ids
            self.line_end_cb['values'] = ids
        except Exception:
            pass

    def _on_point_select(self, event):
        # Treeview selection: extract point id from selected item
        sel = event.widget.selection()
        if not sel:
            return
        item = sel[0]
        try:
            values = event.widget.item(item, 'values')
            pid = int(values[0])
        except Exception:
            return
        p = next((pp for pp in self.user_points if pp['id'] == pid), None)
        if p is None:
            return
        self.point_id_var.set(str(p['id']))
        self.point_realx_var.set(str(p.get('real_x', p.get('pdf_x'))))
        self.point_realy_var.set(str(p.get('real_y', p.get('pdf_y'))))
        self.point_z_var.set(str(p.get('z', 0)))
        try:
            self.point_hide_var.set(bool(p.get('hidden', False)))
        except Exception:
            pass

    

    def apply_point_edit(self):
        try:
            pid = int(self.point_id_var.get())
        except Exception:
            return
        p = next((pp for pp in self.user_points if pp['id'] == pid), None)
        if p is None:
            return
        try:
            p['real_x'] = float(self.point_realx_var.get())
            p['real_y'] = float(self.point_realy_var.get())
            # preserve z numeric
            p['z'] = float(self.point_z_var.get())
        except ValueError:
            self.update_status('Invalid numeric value for point')
            return
        # Refresh UI and views
        try:
            self.redraw_markers()
        except Exception:
            pass
        self.update_points_label()
        try:
            # Persist hide state
            p['hidden'] = bool(self.point_hide_var.get())
            self.update_3d_plot()
        except Exception:
            pass
        self.refresh_editor_lists()

    def _on_line_select(self, event):
        sel = event.widget.selection()
        if not sel:
            return
        item = sel[0]
        try:
            values = event.widget.item(item, 'values')
            lid = int(values[0])
        except Exception:
            return
        l = next((ll for ll in self.lines if ll['id'] == lid), None)
        if l is None:
            return
        self.line_id_var.set(str(l['id']))
        self.line_start_cb.set(l.get('start_id'))
        self.line_end_cb.set(l.get('end_id'))
        try:
            self.line_hide_var.set(bool(l.get('hidden', False)))
        except Exception:
            pass

    

    def apply_line_edit(self):
        try:
            lid = int(self.line_id_var.get())
        except Exception:
            return
        l = next((ll for ll in self.lines if ll['id'] == lid), None)
        if l is None:
            return
        try:
            start_id = int(self.line_start_cb.get())
            end_id = int(self.line_end_cb.get())
        except Exception:
            self.update_status('Invalid point id for line')
            return
        l['start_id'] = start_id
        l['end_id'] = end_id
        self.redraw_markers()
        try:
            # Persist hide state for line
            l['hidden'] = bool(self.line_hide_var.get())
            self.update_3d_plot()
        except Exception:
            pass
        self.refresh_editor_lists()

    def _on_curve_select(self, event):
        sel = event.widget.selection()
        if not sel:
            return
        item = sel[0]
        try:
            values = event.widget.item(item, 'values')
            cid = int(values[0])
        except Exception:
            return
        c = next((cc for cc in self.curves if cc['id'] == cid), None)
        if c is None:
            return
        self.curve_id_var.set(str(c['id']))
        self.curve_z_var.set(str(c.get('z_level', c.get('z', 0))))
        try:
            self.curve_hide_var.set(bool(c.get('hidden', False)))
        except Exception:
            pass

    

    def apply_curve_edit(self):
        try:
            cid = int(self.curve_id_var.get())
        except Exception:
            return
        c = next((cc for cc in self.curves if cc['id'] == cid), None)
        if c is None:
            return
        try:
            c['z_level'] = float(self.curve_z_var.get())
        except ValueError:
            self.update_status('Invalid z value for curve')
            return
        self.redraw_markers()
        try:
            # Persist hide state for curve
            c['hidden'] = bool(self.curve_hide_var.get())
            self.update_3d_plot()
        except Exception:
            pass
        self.refresh_editor_lists()

    def editor_delete_selected(self):
        # Delete selected point/line/curve based on which list has focus
        # Points treeview selection
        pts_sel = self.points_tv.selection()
        if pts_sel:
            item = pts_sel[0]
            try:
                pid = int(self.points_tv.item(item, 'values')[0])
            except Exception:
                return
            p = next((pp for pp in self.user_points if pp['id'] == pid), None)
            if p is None:
                return
            try:
                self.delete_point(p)
            except Exception:
                self.user_points = [pp for pp in self.user_points if pp['id'] != p['id']]
            self.redraw_markers()
            self.update_points_label()
            self.refresh_editor_lists()
            return

        # Lines treeview selection
        lines_sel = self.lines_tv.selection()
        if lines_sel:
            item = lines_sel[0]
            try:
                lid = int(self.lines_tv.item(item, 'values')[0])
            except Exception:
                return
            l = next((ll for ll in self.lines if ll['id'] == lid), None)
            if l is None:
                return
            try:
                self.delete_line(l)
            except Exception:
                self.lines = [ll for ll in self.lines if ll['id'] != l['id']]
            self.redraw_markers()
            self.refresh_editor_lists()
            return

        # Curves treeview selection
        curves_sel = self.curves_tv.selection()
        if curves_sel:
            item = curves_sel[0]
            try:
                cid = int(self.curves_tv.item(item, 'values')[0])
            except Exception:
                return
            c = next((cc for cc in self.curves if cc['id'] == cid), None)
            if c is None:
                return
            try:
                self.delete_curve(c)
            except Exception:
                self.curves = [cc for cc in self.curves if cc['id'] != c['id']]
        try:
            self.update_3d_plot()
        except Exception:
            pass
        self.refresh_editor_lists()

    def update_3d_plot(self):
        # Initialize if needed
        if not self._3d_initialized:
            self._init_3d_canvas()
            if not self._3d_initialized:
                return

        ax = self._3d_ax
        ax.cla()

        # Apply theme
        if self._3d_theme == 'dark':
            ax.set_facecolor('#222222')
            self._3d_fig.patch.set_facecolor('#222222')
        else:
            ax.set_facecolor('white')
            self._3d_fig.patch.set_facecolor('white')

        # Prepare accumulators for autoscaling and plotting
        all_x = []
        all_y = []
        all_z = []

        # Plot points (mirror along Y by negating Y coordinates)
        pts = [p for p in self.user_points if not p.get('hidden', False)]
        xs = [p.get('real_x', p.get('pdf_x')) for p in pts]
        ys = [-(p.get('real_y', p.get('pdf_y'))) for p in pts]
        zs = [float(p.get('z', 0)) for p in pts]
        if xs and ys and zs:
            ax.scatter(xs, ys, zs, c=self._3d_point_color, s=self._3d_point_size)
            # Add labels for each visible point (ID) near the point marker
            try:
                for p in pts:
                    px = p.get('real_x', p.get('pdf_x'))
                    py = -(p.get('real_y', p.get('pdf_y')))
                    pz = float(p.get('z', 0))
                    pid = p.get('id')
                    if pid is not None:
                        ax.text(px, py, pz + 0.01, str(pid), color='white' if self._3d_theme == 'dark' else 'black', fontsize=8)
                    all_x.append(px)
                    all_y.append(py)
                    all_z.append(pz)
            except Exception:
                pass

        # Plot lines (use safe lookups so missing keys don't abort the entire 3D update)
        for line in self.lines:
            try:
                # Skip lines flagged hidden
                if line.get('hidden', False):
                    continue
                start = next(p for p in self.user_points if p['id'] == line['start_id'])
                end = next(p for p in self.user_points if p['id'] == line['end_id'])
                # Safe coordinate extraction with fallbacks
                sx = start.get('real_x', start.get('pdf_x', 0.0))
                sy = -(start.get('real_y', start.get('pdf_y', 0.0)))
                sz = float(start.get('z', 0.0))

                ex = end.get('real_x', end.get('pdf_x', 0.0))
                ey = -(end.get('real_y', end.get('pdf_y', 0.0)))
                ez = float(end.get('z', 0.0))

                ax.plot([sx, ex], [sy, ey], [sz, ez], c=self._3d_line_color)

                # Add a label at the midpoint of the line
                try:
                    mid_x = (sx + ex) / 2.0
                    mid_y = (sy + ey) / 2.0
                    mid_z = (sz + ez) / 2.0
                    label_color = 'white' if self._3d_theme == 'dark' else 'black'
                    lid = line.get('id')
                    if lid is not None:
                        ax.text(mid_x, mid_y, mid_z + 0.01, str(lid), color=label_color, fontsize=8)
                except Exception:
                    pass
                # include endpoints in autoscale
                all_x.extend([sx, ex])
                all_y.extend([sy, ey])
                all_z.extend([sz, ez])
            except Exception:
                # If anything goes wrong for this line, skip it but continue plotting others
                continue

        # Plot curves
        for curve in self.curves:
            # Skip curves flagged hidden
            if curve.get('hidden', False):
                continue

            pts = []
            if curve.get('arc_points_real'):
                arc = curve['arc_points_real']
                # If arc entries already include Z values, use them
                if all(len(t) > 2 for t in arc):
                    pts = [(t[0], t[1], float(t[2])) for t in arc]
                else:
                    # Fall back: try to map each arc entry to the corresponding arc_point_id to fetch Z
                    ids = curve.get('arc_point_ids', [])
                    for i, t in enumerate(arc):
                        x = t[0]
                        y = t[1]
                        z = None
                        if i < len(ids):
                            pid = ids[i]
                            p = next((u for u in self.user_points if u['id'] == pid), None)
                            if p:
                                z = float(p.get('z', 0))
                        if z is None:
                            z = float(curve.get('z_level', curve.get('z', 0)))
                        pts.append((x, y, z))
            else:
                for pid in curve.get('arc_point_ids', []):
                    p = next((u for u in self.user_points if u['id'] == pid), None)
                    if p:
                        pts.append((p.get('real_x', p.get('pdf_x')), p.get('real_y', p.get('pdf_y')), float(p.get('z', 0))))

            if not pts:
                continue

            xs = [t[0] for t in pts]
            ys = [-(t[1]) for t in pts]
            zs = [t[2] for t in pts]
            ax.plot(xs, ys, zs, c=self._3d_curve_color)
            all_x.extend(xs)
            all_y.extend(ys)
            all_z.extend(zs)
        # Autoscale axes to include all plotted items with padding to avoid clipping
        try:
            if all_x and all_y and all_z:
                xmin, xmax = min(all_x), max(all_x)
                ymin, ymax = min(all_y), max(all_y)
                zmin, zmax = min(all_z), max(all_z)
                # add small padding (8%) or minimal epsilon
                def pad(a, b):
                    rng = b - a
                    padv = max(1e-6, rng * 0.08)
                    return a - padv, b + padv

                nx0, nx1 = pad(xmin, xmax)
                ny0, ny1 = pad(ymin, ymax)
                nz0, nz1 = pad(zmin, zmax)
                ax.set_xlim3d(nx0, nx1)
                ax.set_ylim3d(ny0, ny1)
                ax.set_zlim3d(nz0, nz1)
        except Exception:
            pass
    def increase_point_size(self):
        self._3d_point_size = min(200, int(self._3d_point_size * 1.25) + 1)
        self.update_3d_plot()

    def decrease_point_size(self):
        self._3d_point_size = max(1, int(self._3d_point_size / 1.25))
        self.update_3d_plot()

    def _on_3d_mousewheel(self, event):
        """Zoom the 3D view using the mouse wheel by adjusting axis limits."""
        try:
            if not getattr(self, '_3d_initialized', False):
                return
            ax = self._3d_ax
            # Determine wheel direction; Windows uses event.delta, X11 uses Button-4/5
            factor = 1.0
            if hasattr(event, 'delta'):
                # event.delta typically positive for up, negative for down
                factor = 1.1 if event.delta > 0 else 0.9
            else:
                # On some systems event.num==4 means up, 5 means down
                try:
                    factor = 1.1 if int(getattr(event, 'num', 0)) == 4 else 0.9
                except Exception:
                    factor = 1.0

            # Current limits
            try:
                x0, x1 = ax.get_xlim3d()
                y0, y1 = ax.get_ylim3d()
                z0, z1 = ax.get_zlim3d()
            except Exception:
                return

            cx = 0.5 * (x0 + x1)
            cy = 0.5 * (y0 + y1)
            cz = 0.5 * (z0 + z1)

            nx0 = cx + (x0 - cx) * (1.0 / factor)
            nx1 = cx + (x1 - cx) * (1.0 / factor)
            ny0 = cy + (y0 - cy) * (1.0 / factor)
            ny1 = cy + (y1 - cy) * (1.0 / factor)
            nz0 = cz + (z0 - cz) * (1.0 / factor)
            nz1 = cz + (z1 - cz) * (1.0 / factor)

            ax.set_xlim3d(nx0, nx1)
            ax.set_ylim3d(ny0, ny1)
            ax.set_zlim3d(nz0, nz1)

            try:
                # Use draw_idle to be more responsive
                self._3d_canvas.draw_idle()
            except Exception:
                try:
                    self._3d_canvas.draw()
                except Exception:
                    pass
        except Exception:
            pass

    def _on_3d_mpl_scroll(self, event):
        """Matplotlib scroll_event handler fallback for zooming the 3D view."""
        try:
            if not getattr(self, '_3d_initialized', False):
                return
            # Determine direction from event.step (newer mpl) or event.button
            step = getattr(event, 'step', None)
            if step is None:
                btn = getattr(event, 'button', None)
                if isinstance(btn, str):
                    step = 1 if btn.lower() in ('up', 'forward') else -1
                else:
                    # conservative fallback
                    step = 1 if getattr(event, 'guiEvent', None) is None else 0

            factor = 1.1 if step > 0 else 0.9

            ax = self._3d_ax
            try:
                x0, x1 = ax.get_xlim3d()
                y0, y1 = ax.get_ylim3d()
                z0, z1 = ax.get_zlim3d()
            except Exception:
                return

            cx = 0.5 * (x0 + x1)
            cy = 0.5 * (y0 + y1)
            cz = 0.5 * (z0 + z1)

            nx0 = cx + (x0 - cx) * (1.0 / factor)
            nx1 = cx + (x1 - cx) * (1.0 / factor)
            ny0 = cy + (y0 - cy) * (1.0 / factor)
            ny1 = cy + (y1 - cy) * (1.0 / factor)
            nz0 = cz + (z0 - cz) * (1.0 / factor)
            nz1 = cz + (z1 - cz) * (1.0 / factor)

            ax.set_xlim3d(nx0, nx1)
            ax.set_ylim3d(ny0, ny1)
            ax.set_zlim3d(nz0, nz1)

            try:
                self._3d_canvas.draw_idle()
            except Exception:
                try:
                    self._3d_canvas.draw()
                except Exception:
                    pass
        except Exception:
            pass

    def reset_3d_view(self):
        # reset to default orientation and autoscale
        self._3d_elev = 30
        self._3d_azim = -60
        try:
            self.update_3d_plot()
        except Exception:
            pass

    def set_3d_theme(self, theme_name: str):
        if theme_name not in ('default', 'dark'):
            return
        self._3d_theme = theme_name
        # update combobox if present
        try:
            cb = self._3d_toolbar_vars.get('theme_cb')
            if cb:
                cb.set(theme_name)
        except Exception:
            pass
        self.update_3d_plot()

    def toggle_3d_grid(self):
        try:
            var = self._3d_toolbar_vars.get('grid_var')
            self._3d_show_grid = bool(var.get())
        except Exception:
            self._3d_show_grid = not self._3d_show_grid
        self.update_3d_plot()

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
        # Ensure editor lists and 3D view reflect the current markers immediately.
        # Use try/except to avoid crashing the UI if either subsystem isn't ready.
        try:
            self.refresh_editor_lists()
        except Exception:
            pass
        try:
            # update_3d_plot will initialize 3D canvas lazily if needed
            self.update_3d_plot()
        except Exception:
            pass

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
        # Allow saving once a PDF is loaded or calibration exists.
        # Points, lines and curves are optional for a valid project.
        if self.pdf_doc is None and self.transformation_matrix is None:
            messagebox.showwarning("No Data", "No PDF loaded and no calibration available. Load a PDF or complete calibration before saving.")
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
        # include allocator counters if available
        try:
            if self.allocator is not None:
                project_data['id_counters'] = self.allocator.to_dict()
        except Exception:
            pass

        # Validate project before saving (optional: allow override)
        try:
            if validate_project is not None:
                errs = validate_project(project_data)
                if errs:
                    proceed = messagebox.askyesno("Validation Warnings", f"Project validation returned errors:\n{errs}\n\nSave anyway?")
                    if not proceed:
                        return
        except Exception:
            pass
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

            # Backup original project before any migration
            try:
                bak_name = project_path + '.bak.' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                shutil.copy(project_path, bak_name)
            except Exception:
                pass

            # Prepare allocator from project and migrate to canonical schema if helpers available
            try:
                if IDAllocator is not None:
                    self.allocator = IDAllocator.from_project(project_data)
                if migrate_project is not None:
                    project_data = migrate_project(project_data, self.allocator if self.allocator is not None else None, self.transform_point, tol_pixels=3.0)
            except Exception:
                # If migration fails, continue with best-effort
                pass

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
            # Ensure point_id_counter continues from allocator if available
            try:
                if self.allocator is not None:
                    # keep point_id_counter in sync for legacy code paths
                    self.point_id_counter = max(self.point_id_counter, int(getattr(self.allocator, 'point_counter', self.point_id_counter)))
                else:
                    max_id = max((p.get('id', 0) for p in self.user_points), default=0)
                    self.point_id_counter = max(self.point_id_counter, max_id + 1)
            except Exception:
                pass

            # Refresh editor lists and 3D view to reflect loaded project
            try:
                self.refresh_editor_lists()
            except Exception:
                pass
            try:
                self.update_3d_plot()
            except Exception:
                pass
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

        # Ensure each curve has a fixed number of positions (interior + 2 endpoints)
        total_positions = max(2, int(getattr(self, 'curve_interior_points', 4)) + 2)

        def find_or_create_point(px, py, z_val=None):
            # Try to find an existing point by pdf coords (exact match, small tolerance)
            tol = 1e-6
            for p in self.user_points:
                if abs(p.get('pdf_x', 1e12) - px) < tol and abs(p.get('pdf_y', 1e12) - py) < tol:
                    return p['id']
            # Create new point
            rx, ry = self.transform_point(px, py)
            # Use centralized helper to allocate a new point id
            new_id = self.next_point_id()
            new_pt = {
                'id': new_id,
                'pdf_x': px,
                'pdf_y': py,
                'real_x': round(rx, 2),
                'real_y': round(ry, 2),
                'z': float(z_val) if z_val is not None else 0.0
            }
            self.user_points.append(new_pt)
            return new_id

        # Reconstruct or normalize arc_point_ids for each curve (may create new points)
        for curve in self.curves:
            # Determine base z-level for this curve
            z_level = float(curve.get('z_level', curve.get('z', 0)))

            # If arc_point_ids present and correct length, keep them
            ids = list(curve.get('arc_point_ids', [])) if curve.get('arc_point_ids') else []

            # If arc_points_pdf present, try to map them to points
            arc_pdf = curve.get('arc_points_pdf', [])
            if not ids and arc_pdf:
                for (px, py) in arc_pdf:
                    pid = find_or_create_point(px, py, z_level)
                    ids.append(pid)

            # Ensure start/end are present and prefer start_id/end_id if available
            start_id = curve.get('start_id')
            end_id = curve.get('end_id')
            if start_id is not None:
                if not ids or ids[0] != start_id:
                    if start_id in ids:
                        # move existing to front
                        ids.remove(start_id)
                    ids.insert(0, start_id)
            if end_id is not None:
                if not ids or ids[-1] != end_id:
                    if end_id in ids:
                        ids.remove(end_id)
                    ids.append(end_id)

            # If still missing positions, interpolate between start and end (pdf coords)
            if len(ids) < total_positions:
                # gather pdf coords for interpolation
                if arc_pdf and len(arc_pdf) >= 2:
                    # use pdf coords from arc_pdf if available
                    # build complete list of pdf coords (try to include start/end)
                    pdf_coords = list(arc_pdf)
                    # ensure start/end pdf present
                    try:
                        if start_id is not None:
                            sp = next((p for p in self.user_points if p['id'] == start_id), None)
                            if sp:
                                if (sp['pdf_x'], sp['pdf_y']) not in pdf_coords:
                                    pdf_coords.insert(0, (sp['pdf_x'], sp['pdf_y']))
                        if end_id is not None:
                            ep = next((p for p in self.user_points if p['id'] == end_id), None)
                            if ep:
                                if (ep['pdf_x'], ep['pdf_y']) not in pdf_coords:
                                    pdf_coords.append((ep['pdf_x'], ep['pdf_y']))
                    except Exception:
                        pass
                    # linear interpolate along the available endpoints
                    if len(pdf_coords) >= 2:
                        sx, sy = pdf_coords[0]
                        ex, ey = pdf_coords[-1]
                        needed = total_positions - len(ids)
                        # insert interior points between start and end
                        insert_ids = []
                        for i in range(1, total_positions - 1):
                            t = i / (total_positions - 1)
                            ix = sx * (1 - t) + ex * t
                            iy = sy * (1 - t) + ey * t
                            pid = find_or_create_point(ix, iy, z_level)
                            insert_ids.append(pid)
                        # final assembly: start, interiors, end
                        final_ids = []
                        if start_id is not None:
                            final_ids.append(start_id)
                        else:
                            final_ids.append(insert_ids[0] if insert_ids else (ids[0] if ids else None))
                        # pick appropriate interior ids
                        final_ids.extend(insert_ids[:max(0, total_positions - 2)])
                        if end_id is not None:
                            final_ids.append(end_id)
                        else:
                            final_ids.append(insert_ids[-1] if insert_ids else (ids[-1] if ids else None))
                        ids = [i for i in final_ids if i is not None]
                else:
                    # fallback: duplicate start/end points as necessary
                    if start_id is None and end_id is None:
                        # nothing to do; create dummy points at origin
                        while len(ids) < total_positions:
                            pid = find_or_create_point(0.0, 0.0, z_level)
                            ids.append(pid)
                    else:
                        # expand by repeating start/end
                        while len(ids) < total_positions:
                            if len(ids) < (total_positions // 2):
                                if start_id is not None:
                                    ids.insert(0, start_id)
                                else:
                                    pid = find_or_create_point(0.0, 0.0, z_level)
                                    ids.insert(0, pid)
                            else:
                                if end_id is not None:
                                    ids.append(end_id)
                                else:
                                    pid = find_or_create_point(0.0, 0.0, z_level)
                                    ids.append(pid)

            # Truncate or pad to exactly total_positions
            if len(ids) > total_positions:
                ids = ids[:total_positions]
            while len(ids) < total_positions:
                # pad using last id
                if ids:
                    ids.append(ids[-1])
                else:
                    ids.append(find_or_create_point(0.0, 0.0, z_level))

            curve['arc_point_ids'] = ids

        # Now write points, lines, curves and SQL (points may have been created above)
        with open(points_file, 'w') as f:
            f.write("ID,X,Y,Z\n")
            for point in self.user_points:
                # ensure real coords exist
                if 'real_x' not in point or 'real_y' not in point:
                    rx, ry = self.transform_point(point.get('pdf_x', 0.0), point.get('pdf_y', 0.0))
                    point['real_x'] = round(rx, 2)
                    point['real_y'] = round(ry, 2)
                f.write(f"{point['id']},{point['real_x']},{point['real_y']},{point.get('z', 0.0)}\n")

        with open(lines_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['LineID', 'StartPointID', 'EndPointID', 'StartPointZ', 'EndPointZ'])
            for line in self.lines:
                start_id = line['start_id']
                end_id = line['end_id']
                start_z = next((p.get('z') for p in self.user_points if p['id'] == start_id), None)
                end_z = next((p.get('z') for p in self.user_points if p['id'] == end_id), None)
                writer.writerow([line['id'], start_id, end_id, start_z, end_z])

        with open(curves_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Per-user requirement: Position,PointID,LineID (exactly total_positions rows per curve)
            writer.writerow(['Position', 'PointID', 'LineID'])
            for curve in self.curves:
                line_id = next((l['id'] for l in self.lines if
                                (l['start_id'] == curve.get('start_id') and l['end_id'] == curve.get('end_id')) or
                                (l['start_id'] == curve.get('end_id') and l['end_id'] == curve.get('start_id'))
                                ), 0)
                base_line_id = curve.get('base_line_id', line_id)
                ids = curve.get('arc_point_ids', [])
                for pos in range(total_positions):
                    pid = ids[pos] if pos < len(ids) else ids[-1]
                    writer.writerow([pos, pid, base_line_id])

        # Generate SQL file with IDENTITY_INSERT
        with open(sql_file, 'w') as f:
            f.write("-- SQL Insert Script for SeasPathDB\n")
            f.write("-- Generated from 3DMaker Export\n\n")

            # Points table
            f.write("-- Insert Visualization_Coordinate (Points)\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;\n")
            for point in self.user_points:
                f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) ")
                f.write(f"VALUES ({point['id']}, {point['real_x']}, {point['real_y']}, {point.get('z', 0.0)}, '3D Visualisation');\n")
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
            curve_row_id = 1
            for curve in self.curves:
                line_id = next((l['id'] for l in self.lines if
                                (l['start_id'] == curve.get('start_id') and l['end_id'] == curve.get('end_id')) or
                                (l['start_id'] == curve.get('end_id') and l['end_id'] == curve.get('start_id'))
                                ), 0)
                edge_id = curve.get('base_line_id', line_id)
                ids = curve.get('arc_point_ids', [])
                for position in range(total_positions):
                    pid = ids[position] if position < len(ids) else ids[-1]
                    f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Curve (Id, PositionNumber, CoordinateId, EdgeId) ")
                    f.write(f"VALUES ({curve_row_id}, {position}, {pid}, {edge_id});\n")
                    curve_row_id += 1
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
            # Use centralized helper to allocate a new point id
            new_id = self.next_point_id()
            new_point['id'] = new_id
            new_point['z'] = z
            self.user_points.append(new_point)

    def duplicate_line(self, line, z_values):
        for z in z_values:
            # Get start and end points
            start = next(p for p in self.user_points if p['id'] == line['start_id'])
            end = next(p for p in self.user_points if p['id'] == line['end_id'])

            # Create new points at new Z level
            # allocate new start/end point ids
            # Allocate new start point id via centralized helper
            start_id = self.next_point_id()

            new_start = start.copy()
            new_start['id'] = start_id
            new_start['z'] = z
            self.user_points.append(new_start)

            # Allocate new end point id via centralized helper
            end_id = self.next_point_id()

            new_end = end.copy()
            new_end['id'] = end_id
            new_end['z'] = z
            self.user_points.append(new_end)

            # Create new line id
            # Allocate new line id via centralized helper
            new_lid = self.next_line_id()

            new_line = line.copy()
            new_line['id'] = new_lid
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
                # Allocate new intermediate arc point id
                new_pid = self.next_point_id()
                new_point['id'] = new_pid
                new_point['z'] = z
                self.user_points.append(new_point)
                new_arc_point_ids.append(new_pid)

            # Create new curve
            new_curve = curve.copy()
            # Allocate new curve id via centralized helper
            new_curve['id'] = self.next_curve_id()
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