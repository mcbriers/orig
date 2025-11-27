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
        # caching and zoom debounce helpers
        self._zoom_render_job = None
        self._pending_zoom_level = None
        self._pending_zoom_pdf_coords = None
        self._last_rendered_pil = None

        self.reference_points_pdf = []
        self.reference_points_real = []
        self.user_points = []
        
        # Track backup file created on project load for cleanup
        self._current_backup_file = None
        # Track current project path for Save vs Save As behavior
        self._project_path = None
        # Track if project has been modified since last save
        self._modified = False

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
        # legacy counters removed; IDs are allocated deterministically via next_* helpers
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
        
        # Remember last Z value used for duplication
        self._last_z_value = ""

        self.point_markers = {}
        self.point_labels = {}
        self.calibration_markers = {}
        self.zoom_entry = None
        self.points_label = None
        self.calib_status = None
        self.status_label = None
        self.canvas = None
        self.vscroll = None
        self.hscroll = None

        self.selected_item = None
        # sort state for treeviews: map (tree, column) -> ascending(bool)
        self._tv_sort_state = {}
        # store base heading texts per tree so we can add visual sort indicators
        self._tv_heading_texts = {}

        self.build_ui()

    # Centralized ID helpers to keep legacy counters synchronized with allocator
    def next_point_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                nid = self.allocator.next_point_id()
                return nid
        except Exception:
            pass
        # Deterministic fallback: use max existing point id + 1
        try:
            max_id = max((p.get('id', 0) for p in self.user_points), default=0)
            return max_id + 1
        except Exception:
            # final fallback
            return 1

    def next_line_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                lid = self.allocator.next_line_id()
                try:
                    # if allocator tracks line counter, keep in sync
                    pass
                except Exception:
                    pass
                return lid
        except Exception:
            pass
        try:
            max_id = max((l.get('id', 0) for l in self.lines), default=0)
            return max_id + 1
        except Exception:
            return 1

    def next_curve_id(self):
        try:
            if hasattr(self, 'allocator') and self.allocator is not None:
                cid = self.allocator.next_curve_id()
                try:
                    pass
                except Exception:
                    pass
                return cid
        except Exception:
            pass
        try:
            max_id = max((c.get('id', 0) for c in self.curves), default=0)
            return max_id + 1
        except Exception:
            return 1

    def build_ui(self):
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open PDF...", command=self.open_file)
        file_menu.add_command(label="Open Project...", command=self.open_project)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Save Project As...", command=self.save_project_as)
        file_menu.add_command(label="Close PDF", command=self.close_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.export_data)
        file_menu.add_command(label="Export PDF to PNG...", command=self.export_pdf_to_png)
        file_menu.add_separator()
        file_menu.add_command(label="Clean Old Backups...", command=self.clean_old_backups)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Clear All (Points/Lines/Curves)", command=self.clear_points)
        edit_menu.add_command(label="Clear Lines Only", command=self.clear_lines_only)
        edit_menu.add_command(label="Clear Curves Only", command=self.clear_curves_only)
        edit_menu.add_separator()
        edit_menu.add_command(label="Undo Clear", command=self.undo_clear)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear Calibration", command=self.clear_calibration)
        edit_menu.add_separator()
        edit_menu.add_command(label="Validate Z Levels...", command=self.editor_validate_z_levels)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        # View menu: options window for display settings
        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(label="Options...", command=self.open_display_options)
        menu_bar.add_cascade(label="View", menu=view_menu)

        # Tools menu
        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label="Audit Project...", command=self.audit_project)
        tools_menu.add_command(label="Line Audit...", command=self.open_line_audit_tool)
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        main_frame = tk.PanedWindow(self.master, orient='horizontal')
        main_frame.pack(fill="both", expand=True)

        # Left content frame (holds notebook)
        content_frame = tk.Frame(main_frame)
        main_frame.add(content_frame, stretch='always')

        # Left: Notebook with 2D view and 3D view
        # Style notebook tabs to be wider
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 8])
        self.notebook = ttk.Notebook(content_frame)
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

        # Editor tab for listing and editing entities
        self.editor_frame = tk.Frame(self.notebook)
        self.notebook.add(self.editor_frame, text="Editor")
        self._build_editor_tab(self.editor_frame)
        
        # 3D view tab (matplotlib) - created lazily
        self.view3d_frame = tk.Frame(self.notebook)
        self.notebook.add(self.view3d_frame, text="3D View")

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
        
        # Handle window close button
        self.master.protocol("WM_DELETE_WINDOW", self.on_exit)

        control_panel = tk.Frame(main_frame, width=320, bg="lightgrey", padx=5, pady=5)
        main_frame.add(control_panel, stretch='never', minsize=250)
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

        # PDF fade control (overlay-based, does not trigger re-render)
        fade_frame = tk.Frame(zoom_frame)
        fade_frame.pack(fill='x', padx=2, pady=(6,2))
        tk.Label(fade_frame, text="Fade PDF:").pack(side='left')
        try:
            self.fade_level = tk.IntVar(value=0)
        except Exception:
            self.fade_level = None
        self.fade_slider = tk.Scale(fade_frame, from_=0, to=100, orient='horizontal', command=lambda v: self._update_pdf_fade(), length=160)
        self.fade_slider.set(0)
        self.fade_slider.pack(side='left', padx=6)

        calib_frame = tk.LabelFrame(control_panel, text="Calibration", padx=5, pady=5)
        calib_frame.pack(fill='x', padx=5, pady=5)
        self.calib_status = tk.Label(calib_frame, text="Not Calibrated", bg="#ff6666", fg="white", relief="sunken", wraplength=200)
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
        tk.Radiobutton(mode_frame, text="Duplicate Points", variable=self.mode_var, value="duplicate_points").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Duplicate Lines", variable=self.mode_var, value="duplicate_lines").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Duplicate Curves", variable=self.mode_var, value="duplicate_curves").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Deletion", variable=self.mode_var, value="deletion").pack(anchor="w", padx=10)
        tk.Radiobutton(mode_frame, text="Identify", variable=self.mode_var, value="identify").pack(anchor="w", padx=10)

        tk.Label(point_frame, text="Level Name:").pack(pady=(10, 0))
        tk.Entry(point_frame, width=20, textvariable=self.elevation_var).pack(padx=5, pady=2)

        self.points_label = tk.Label(point_frame, text="Points: 0", bg="white", relief="sunken")
        self.points_label.pack(fill='x', padx=2, pady=2)

        # Line / Curve counters (kept in the control panel)
        self.lines_label = tk.Label(point_frame, text="Lines: 0", bg="white", relief="sunken")
        self.lines_label.pack(fill='x', padx=2, pady=2)
        self.curves_label = tk.Label(point_frame, text="Curves: 0", bg="white", relief="sunken")
        self.curves_label.pack(fill='x', padx=2, pady=2)

        # Clear buttons with more granular control
        clear_btn_frame = tk.Frame(point_frame)
        clear_btn_frame.pack(fill='x', padx=2, pady=2)
        tk.Button(clear_btn_frame, text="Clear All", command=self.clear_points, bg="#ff6b6b", fg="white").pack(side='left', fill='x', expand=True, padx=(0,2))
        tk.Button(clear_btn_frame, text="Clear Lines", command=self.clear_lines_only, bg="#ffa94d").pack(side='left', fill='x', expand=True, padx=2)
        tk.Button(clear_btn_frame, text="Clear Curves", command=self.clear_curves_only, bg="#ffd43b").pack(side='left', fill='x', expand=True, padx=(2,0))

        # NOTE: Display controls moved to a separate Options window (View -> Options...)
        # Default display params (2D) are still initialized here so other code can rely on them.
        from tkinter import colorchooser
        self.point_color_2d = 'blue'
        self.line_color_2d = 'orange'
        self.curve_color_2d = 'purple'
        self.point_marker_size = 5
        self.line_width_2d = 4
        self.curve_width_2d = 2
        self.label_font_size = 12

        # Display-related Tk variables/widgets are created in the Options window.
        # Initialize variables here so other code can reference them safely.
        try:
            self.point_size_var = tk.IntVar(value=self.point_marker_size)
            self.line_width_var = tk.IntVar(value=self.line_width_2d)
            self.font_size_var = tk.IntVar(value=self.label_font_size)
        except Exception:
            self.point_size_var = None
            self.line_width_var = None
            self.font_size_var = None

        # Swatch widgets will be created when the Options window opens.
        self.point_color_swatch = None
        self.line_color_swatch = None
        self.curve_color_swatch = None

        # Display controls have been moved to a separate Options window (View -> Options...).
        # Use `open_display_options()` to show and edit colors/sizes when needed.

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
        self._3d_highlight_color = '#ff00ff'
        self._3d_theme = 'default'
        self._3d_show_grid = True
        self._3d_elev = 30
        self._3d_azim = -60
        # Line audit state
        self._line_audit_window = None
        self._line_audit_start_var = None
        self._line_audit_point_combo = None
        self.line_audit_results_tv = None
        self._line_audit_summary_label = None
        self._line_audit_last_start = ""
        self._line_audit_highlights = {'lines': set(), 'curves': set(), 'endpoints': set()}
        # 3D point selection state
        self._3d_selected_point_id = None
        self._3d_selection_annotation = None

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
        # Connect button_press_event for point picking
        try:
            self._3d_canvas.mpl_connect('button_press_event', self._on_3d_click)
        except Exception:
            pass
        self._3d_initialized = True

    def _do_full_zoom_render(self):
        """Perform a full high-quality PDF render for the pending zoom level and re-center view."""
        try:
            if getattr(self, '_zoom_render_job', None):
                try:
                    self.master.after_cancel(self._zoom_render_job)
                except Exception:
                    pass
                self._zoom_render_job = None

            if self._pending_zoom_level is None:
                return

            # preserve desired pdf coords to center on
            coords = self._pending_zoom_pdf_coords or (None, None)
            x_pdf, y_pdf = coords

            # apply final zoom level and perform full render
            try:
                self.zoom_level = float(self._pending_zoom_level)
            except Exception:
                pass
            # trigger the normal full rendering path
            self.display_page()

            # if we have a center point, recenter the canvas so that the same PDF point
            # remains under the original cursor location
            try:
                if x_pdf is not None and y_pdf is not None and self.photo_image is not None:
                    img_width = self.photo_image.width()
                    img_height = self.photo_image.height()
                    x_scroll_new = x_pdf * self.zoom_level
                    y_scroll_new = y_pdf * self.zoom_level
                    frac_x = (x_scroll_new - (self.canvas.winfo_width() // 2)) / img_width if img_width > 0 else 0
                    frac_y = (y_scroll_new - (self.canvas.winfo_height() // 2)) / img_height if img_height > 0 else 0
                    frac_x = max(0, min(1, frac_x))
                    frac_y = max(0, min(1, frac_y))
                    try:
                        self.canvas.xview_moveto(frac_x)
                        self.canvas.yview_moveto(frac_y)
                    except Exception:
                        pass
            except Exception:
                pass

            # clear pending state
            self._pending_zoom_level = None
            self._pending_zoom_pdf_coords = None
        except Exception:
            return

    # --- Editor tab implementation ---
    def _build_editor_tab(self, parent):
        # Editor area: three treeviews side-by-side for Points / Lines / Curves
        editor_area = tk.Frame(parent)
        editor_area.pack(fill='both', expand=True, padx=4, pady=4)

        # Points treeview (left)
        points_frame = tk.Frame(editor_area)
        points_frame.grid(row=0, column=0, sticky='nsew', padx=(0,4))
        editor_area.grid_columnconfigure(0, weight=1)
        # allow the points_frame to expand its first column
        points_frame.grid_columnconfigure(0, weight=1)
        tk.Label(points_frame, text='Points').grid(row=0, column=0, sticky='w')
        # Points treeview: include a 'Refs' column showing how many entities reference each point
        self.points_tv = ttk.Treeview(points_frame, columns=('id', 'coords', 'x', 'y', 'z', 'refs', 'description', 'hidden'), show='headings', height=24, selectmode='extended')
        self.points_tv.heading('id', text='ID', command=lambda c='id': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('coords', text='Coords', command=lambda c='coords': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('x', text='X', command=lambda c='x': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('y', text='Y', command=lambda c='y': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('z', text='Z', command=lambda c='z': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('refs', text='Refs', command=lambda c='refs': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('description', text='Description', command=lambda c='description': self._treeview_sort(self.points_tv, c))
        self.points_tv.heading('hidden', text='Hidden', command=lambda c='hidden': self._treeview_sort(self.points_tv, c))
        self.points_tv.column('id', width=40, anchor='center')
        self.points_tv.column('coords', width=100)
        self.points_tv.column('x', width=60, anchor='center')
        self.points_tv.column('y', width=60, anchor='center')
        self.points_tv.column('z', width=60, anchor='center')
        self.points_tv.column('refs', width=60, anchor='center')
        self.points_tv.column('description', width=120)
        self.points_tv.column('hidden', width=50, anchor='center')
        # add a vertical scrollbar so users see when more rows are available
        pts_v = ttk.Scrollbar(points_frame, orient='vertical', command=self.points_tv.yview)
        self.points_tv.configure(yscrollcommand=pts_v.set)
        self.points_tv.grid(row=1, column=0, sticky='nsew')
        pts_v.grid(row=1, column=1, sticky='ns')
        # visual tag for newly created/duplicated rows
        try:
            self.points_tv.tag_configure('new', background='#fff2a8')
        except Exception:
            pass
        points_frame.grid_rowconfigure(1, weight=1, minsize=240)
        self.points_tv.bind('<<TreeviewSelect>>', self._on_point_select)
        self.points_tv.bind('<Double-1>', self._on_treeview_double_click)

        # Lines treeview (center)
        lines_frame = tk.Frame(editor_area)
        lines_frame.grid(row=0, column=1, sticky='nsew', padx=4)
        editor_area.grid_columnconfigure(1, weight=1)
        lines_frame.grid_columnconfigure(0, weight=1)
        tk.Label(lines_frame, text='Lines').grid(row=0, column=0, sticky='w')
        self.lines_tv = ttk.Treeview(lines_frame, columns=('id', 'from', 'to', 'z', 'curve', 'hidden'), show='headings', height=24, selectmode='extended')
        self.lines_tv.heading('id', text='ID', command=lambda c='id': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.heading('from', text='From', command=lambda c='from': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.heading('to', text='To', command=lambda c='to': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.heading('z', text='Z', command=lambda c='z': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.heading('curve', text='Curve', command=lambda c='curve': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.heading('hidden', text='Hidden', command=lambda c='hidden': self._treeview_sort(self.lines_tv, c))
        self.lines_tv.column('id', width=40, anchor='center')
        self.lines_tv.column('from', width=80, anchor='center')
        self.lines_tv.column('to', width=80, anchor='center')
        self.lines_tv.column('z', width=60, anchor='center')
        self.lines_tv.column('curve', width=70, anchor='center')
        self.lines_tv.column('hidden', width=50, anchor='center')
        # add vertical scrollbar for lines treeview
        lines_v = ttk.Scrollbar(lines_frame, orient='vertical', command=self.lines_tv.yview)
        self.lines_tv.configure(yscrollcommand=lines_v.set)
        self.lines_tv.grid(row=1, column=0, sticky='nsew')
        lines_v.grid(row=1, column=1, sticky='ns')
        lines_frame.grid_rowconfigure(1, weight=1, minsize=240)
        self.lines_tv.bind('<<TreeviewSelect>>', self._on_line_select)
        # reuse generic double-click handler which now understands 'from'/'to' keys
        self.lines_tv.bind('<Double-1>', self._on_treeview_double_click)

        # Curves treeview (right)
        curves_frame = tk.Frame(editor_area)
        curves_frame.grid(row=0, column=2, sticky='nsew', padx=(4,0))
        editor_area.grid_columnconfigure(2, weight=1)
        curves_frame.grid_columnconfigure(0, weight=1)
        tk.Label(curves_frame, text='Curves').grid(row=0, column=0, sticky='w')
        self.curves_tv = ttk.Treeview(curves_frame, columns=('curve', 'position', 'point', 'baseline', 'z', 'hidden'), show='headings', height=24, selectmode='extended')
        self.curves_tv.heading('curve', text='Curve', command=lambda c='curve': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.heading('position', text='Position', command=lambda c='position': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.heading('point', text='Point ID', command=lambda c='point': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.heading('baseline', text='Base Line', command=lambda c='baseline': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.heading('z', text='Z Level', command=lambda c='z': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.heading('hidden', text='Hidden', command=lambda c='hidden': self._treeview_sort(self.curves_tv, c))
        self.curves_tv.column('curve', width=60, anchor='center')
        self.curves_tv.column('position', width=70, anchor='center')
        self.curves_tv.column('point', width=80, anchor='center')
        self.curves_tv.column('baseline', width=80, anchor='center')
        self.curves_tv.column('z', width=70, anchor='center')
        self.curves_tv.column('hidden', width=50, anchor='center')
        # add vertical scrollbar for curves treeview
        cur_v = ttk.Scrollbar(curves_frame, orient='vertical', command=self.curves_tv.yview)
        self.curves_tv.configure(yscrollcommand=cur_v.set)
        self.curves_tv.grid(row=1, column=0, sticky='nsew')
        cur_v.grid(row=1, column=1, sticky='ns')
        curves_frame.grid_rowconfigure(1, weight=1, minsize=240)
        self.curves_tv.bind('<<TreeviewSelect>>', self._on_curve_select)
        self.curves_tv.bind('<Double-1>', self._on_treeview_double_click)
        # RFID treeview (right-most)
        rfid_frame = tk.Frame(editor_area)
        rfid_frame.grid(row=0, column=3, sticky='nsew', padx=(4,0))
        editor_area.grid_columnconfigure(3, weight=1)
        rfid_frame.grid_columnconfigure(0, weight=1)
        tk.Label(rfid_frame, text='RFID').grid(row=0, column=0, sticky='w')
        # columns: Vertex, TransponderID, Line ID, length
        self.rfid_tv = ttk.Treeview(rfid_frame, columns=('vertex', 'transponder', 'line', 'length'), show='headings', height=24, selectmode='extended')
        self.rfid_tv.heading('vertex', text='Vertex', command=lambda c='vertex': self._treeview_sort(self.rfid_tv, c))
        self.rfid_tv.heading('transponder', text='TransponderID', command=lambda c='transponder': self._treeview_sort(self.rfid_tv, c))
        self.rfid_tv.heading('line', text='Line ID', command=lambda c='line': self._treeview_sort(self.rfid_tv, c))
        self.rfid_tv.heading('length', text='Length', command=lambda c='length': self._treeview_sort(self.rfid_tv, c))
        self.rfid_tv.column('vertex', width=60, anchor='center')
        self.rfid_tv.column('transponder', width=140)
        self.rfid_tv.column('line', width=60, anchor='center')
        self.rfid_tv.column('length', width=80, anchor='e')
        # add vertical scrollbar for rfid treeview
        rfid_v = ttk.Scrollbar(rfid_frame, orient='vertical', command=self.rfid_tv.yview)
        self.rfid_tv.configure(yscrollcommand=rfid_v.set)
        self.rfid_tv.grid(row=1, column=0, sticky='nsew')
        rfid_v.grid(row=1, column=1, sticky='ns')
        rfid_frame.grid_rowconfigure(1, weight=1, minsize=240)
        self.rfid_tv.bind('<<TreeviewSelect>>', lambda e: None)
        self.rfid_tv.bind('<Double-1>', self._on_treeview_double_click)
        # Editor context menu for hide/show
        self.editor_menu = tk.Menu(parent, tearoff=0)
        self.editor_menu.add_command(label='Toggle Hide/Show', command=self.editor_toggle_hide_selected)
        self.editor_menu.add_command(label='Duplicate Point...', command=self.editor_duplicate_point)
        self.editor_menu.add_command(label='Insert Line...', command=self.editor_insert_line)
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label='Reassign References...', command=self.editor_reassign_references)
        self.editor_menu.add_separator()
        # Line editing helpers
        self.editor_menu.add_command(label='Line: New Start (coords from start, z from end)', command=self.editor_line_new_start)
        self.editor_menu.add_command(label='Line: New End (coords from end, z from start)', command=self.editor_line_new_end)
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label='Bulk Replace Z...', command=self.editor_bulk_replace_z)
        # Bind right-click to show context menu and select the clicked row
        self.points_tv.bind('<Button-3>', self._show_editor_menu)
        self.lines_tv.bind('<Button-3>', self._show_editor_menu)
        self.curves_tv.bind('<Button-3>', self._show_editor_menu)
        self.rfid_tv.bind('<Button-3>', self._show_editor_menu)

        # Controls below treeviews: Delete / Hide/Show
        control_row = tk.Frame(parent)
        control_row.pack(fill='x', padx=4, pady=(2,6))
        tk.Button(control_row, text='Delete Selected', command=self.editor_delete_selected).pack(side='left', padx=6)
        tk.Button(control_row, text='Hide/Show Selected', command=self.editor_toggle_hide_selected).pack(side='left')
        tk.Button(control_row, text='Merge Duplicate Points', command=self.merge_duplicate_points).pack(side='left', padx=6)

        # Editor selection/edit state variables and hidden widgets
        try:
            self.point_id_var = tk.StringVar()
            self.point_realx_var = tk.StringVar()
            self.point_realy_var = tk.StringVar()
            self.point_z_var = tk.StringVar()
            self.point_hide_var = tk.BooleanVar(value=False)

            self.line_id_var = tk.StringVar()
            # create combobox widgets (not packed) to back selection state; values set in refresh
            self.line_start_cb = ttk.Combobox(parent, values=[], state='readonly', width=8)
            self.line_end_cb = ttk.Combobox(parent, values=[], state='readonly', width=8)
            self.line_hide_var = tk.BooleanVar(value=False)

            self.curve_id_var = tk.StringVar()
            self.curve_z_var = tk.StringVar()
            self.curve_hide_var = tk.BooleanVar(value=False)
        except Exception:
            # Defensive fallback to simple attributes
            self.point_id_var = None
            self.point_realx_var = None
            self.point_realy_var = None
            self.point_z_var = None
            self.point_hide_var = None
            self.line_id_var = None
            self.line_start_cb = None
            self.line_end_cb = None
            self.line_hide_var = None
            self.curve_id_var = None
            self.curve_z_var = None
            self.curve_hide_var = None

        # Fill lists
        self.refresh_editor_lists()

        # Capture base heading texts for treeviews so we can show sort indicators
        try:
            for tv in (self.points_tv, self.lines_tv, self.curves_tv, self.rfid_tv):
                try:
                    mapping = {}
                    for col in tv['columns']:
                        try:
                            mapping[col] = tv.heading(col)['text']
                        except Exception:
                            mapping[col] = col.title()
                    self._tv_heading_texts[id(tv)] = mapping
                except Exception:
                    continue
        except Exception:
            pass

        # Initial sort on startup: IDs ascending for each list
        try:
            self._treeview_sort(self.points_tv, 'id')
            self._treeview_sort(self.lines_tv, 'id')
            self._treeview_sort(self.curves_tv, 'curve')
            # no default sort for RFID (empty)
        except Exception:
            pass

    def editor_bulk_replace_z(self):
        """Bulk replace Z values across selected points (or all points if none selected)."""
        import re
        dlg = tk.Toplevel(self.master)
        dlg.title('Bulk Replace Z')
        dlg.geometry('380x160')
        dlg.transient(self.master)
        tk.Label(dlg, text='Replace occurrences of pattern with integer value').pack(pady=6)
        frm = tk.Frame(dlg)
        frm.pack(fill='x', padx=10)
        tk.Label(frm, text='Pattern:').grid(row=0, column=0, sticky='e', padx=4, pady=4)
        pat_entry = tk.Entry(frm)
        pat_entry.grid(row=0, column=1, sticky='ew', padx=4)
        tk.Label(frm, text='Integer:').grid(row=1, column=0, sticky='e', padx=4, pady=4)
        rep_entry = tk.Entry(frm)
        rep_entry.grid(row=1, column=1, sticky='ew', padx=4)
        frm.grid_columnconfigure(1, weight=1)
        sel_only = tk.BooleanVar(value=True)
        tk.Checkbutton(dlg, text='Only selected points', variable=sel_only).pack(pady=4)

        def do_replace():
            pat = pat_entry.get().strip()
            rep = rep_entry.get().strip()
            if not pat:
                messagebox.showwarning('Missing Pattern', 'Please enter a pattern to search for.')
                return
            try:
                rep_int = int(rep)
            except Exception:
                messagebox.showerror('Invalid Integer', 'Replacement must be an integer value.')
                return
            rows = self.points_tv.selection() if sel_only.get() else self.points_tv.get_children()
            ids = set()
            for r in rows:
                try:
                    pid = int(self.points_tv.set(r, 'id'))
                    ids.add(pid)
                except Exception:
                    pass
            count = 0
            rx = re.compile(pat)
            for p in self.user_points:
                if ids and p.get('id') not in ids:
                    continue
                z = p.get('z')
                if z is None:
                    continue
                z_str = str(z)
                if rx.search(z_str):
                    p['z'] = rep_int
                    count += 1
            self.refresh_editor_lists()
            # Validate z-level consistency across lines and curves
            issues = self.validate_z_levels()
            msg = f"Bulk replace updated Z on {count} point(s)."
            if issues:
                msg += f" Inconsistencies found: {len(issues)}"
                try:
                    messagebox.showwarning('Z-Level Inconsistencies', '\n'.join(issues[:20]) + ("\n..." if len(issues) > 20 else ""))
                except Exception:
                    pass
            self.update_status(msg)
            dlg.destroy()

        btns = tk.Frame(dlg)
        btns.pack(pady=8)
        tk.Button(btns, text='Replace', command=do_replace, bg='#4CAF50', fg='white').pack(side='left', padx=6)
        tk.Button(btns, text='Cancel', command=dlg.destroy).pack(side='left', padx=6)
        dlg.grab_set()

    def validate_z_levels(self):
        """Check that all lines and curves refer to points with consistent integer z-levels.
        Returns a list of issue strings.
        """
        issues = []
        try:
            # Build map id -> z
            zmap = {}
            for p in self.user_points:
                try:
                    zmap[p['id']] = int(p.get('z', 0))
                except Exception:
                    # non-integer z treated as inconsistent
                    zmap[p['id']] = None
            # Lines: start/end must match
            for l in self.lines:
                s = l.get('start_id')
                e = l.get('end_id')
                zs = zmap.get(s)
                ze = zmap.get(e)
                if zs is None or ze is None or zs != ze:
                    issues.append(f"Line {l.get('id')}: z mismatch start={zs} end={ze}")
            # Curves: all arc_point_ids must share same z
            for c in self.curves:
                ids = c.get('arc_point_ids', [])
                vals = [zmap.get(pid) for pid in ids]
                base = None if not vals else vals[0]
                if any(v is None for v in vals) or any(v != base for v in vals):
                    issues.append(f"Curve {c.get('id')}: z mismatch points={vals}")
        except Exception:
            pass
        return issues

    def editor_validate_z_levels(self):
        """Run z-level validation and present results to the user."""
        issues = self.validate_z_levels()
        if not issues:
            messagebox.showinfo('Z-Level Validation', 'All lines and curves have consistent z-levels.')
            self.update_status('Z-Level validation passed')
        else:
            try:
                messagebox.showwarning('Z-Level Inconsistencies', '\n'.join(issues[:50]) + ("\n..." if len(issues) > 50 else ""))
            except Exception:
                pass
            self.update_status(f'Z-Level validation found {len(issues)} inconsistencies')

    def _get_point_by_id(self, pid):
        try:
            return next((p for p in self.user_points if p.get('id') == pid), None)
        except Exception:
            return None

    def editor_line_new_start(self):
        """For selected line(s), create a new start point using start's coords and end's z, then update line start_id."""
        rows = self.lines_tv.selection()
        if not rows:
            messagebox.showinfo('No Selection', 'Select one or more lines in the editor.')
            return
        changed = 0
        for r in rows:
            try:
                lid = int(self.lines_tv.set(r, 'id'))
                line = next((l for l in self.lines if l.get('id') == lid), None)
                if not line:
                    continue
                s_id = line.get('start_id')
                e_id = line.get('end_id')
                s_pt = self._get_point_by_id(s_id)
                e_pt = self._get_point_by_id(e_id)
                if not s_pt or not e_pt:
                    continue
                # new point: coords from start, z from end
                new_pid = self.next_point_id()
                try:
                    new_point = {
                        'id': new_pid,
                        'real_x': int(round(s_pt.get('real_x', s_pt.get('pdf_x', 0)))) ,
                        'real_y': int(round(s_pt.get('real_y', s_pt.get('pdf_y', 0)))) ,
                        'z': int(round(float(e_pt.get('z', 0)))) ,
                        'hidden': False,
                        'pdf_x': s_pt.get('pdf_x'),
                        'pdf_y': s_pt.get('pdf_y'),
                    }
                except Exception:
                    new_point = {
                        'id': new_pid,
                        'real_x': s_pt.get('real_x', 0),
                        'real_y': s_pt.get('real_y', 0),
                        'z': e_pt.get('z', 0),
                        'hidden': False,
                        'pdf_x': s_pt.get('pdf_x'),
                        'pdf_y': s_pt.get('pdf_y'),
                    }
                self.user_points.append(new_point)
                # update line start
                line['start_id'] = new_pid
                changed += 1
            except Exception:
                continue
        if changed:
            try:
                self.refresh_editor_lists()
            except Exception:
                pass
            try:
                self.update_3d_plot()
            except Exception:
                pass
            self.update_status(f'Created {changed} new start point(s) and updated lines')

    def editor_line_new_end(self):
        """For selected line(s), create a new end point using end's coords and start's z, then update line end_id."""
        rows = self.lines_tv.selection()
        if not rows:
            messagebox.showinfo('No Selection', 'Select one or more lines in the editor.')
            return
        changed = 0
        for r in rows:
            try:
                lid = int(self.lines_tv.set(r, 'id'))
                line = next((l for l in self.lines if l.get('id') == lid), None)
                if not line:
                    continue
                s_id = line.get('start_id')
                e_id = line.get('end_id')
                s_pt = self._get_point_by_id(s_id)
                e_pt = self._get_point_by_id(e_id)
                if not s_pt or not e_pt:
                    continue
                # new point: coords from end, z from start
                new_pid = self.next_point_id()
                try:
                    new_point = {
                        'id': new_pid,
                        'real_x': int(round(e_pt.get('real_x', e_pt.get('pdf_x', 0)))) ,
                        'real_y': int(round(e_pt.get('real_y', e_pt.get('pdf_y', 0)))) ,
                        'z': int(round(float(s_pt.get('z', 0)))) ,
                        'hidden': False,
                        'pdf_x': e_pt.get('pdf_x'),
                        'pdf_y': e_pt.get('pdf_y'),
                    }
                except Exception:
                    new_point = {
                        'id': new_pid,
                        'real_x': e_pt.get('real_x', 0),
                        'real_y': e_pt.get('real_y', 0),
                        'z': s_pt.get('z', 0),
                        'hidden': False,
                        'pdf_x': e_pt.get('pdf_x'),
                        'pdf_y': e_pt.get('pdf_y'),
                    }
                self.user_points.append(new_point)
                # update line end
                line['end_id'] = new_pid
                changed += 1
            except Exception:
                continue
        if changed:
            try:
                self.refresh_editor_lists()
            except Exception:
                pass
            try:
                self.update_3d_plot()
            except Exception:
                pass
            self.update_status(f'Created {changed} new end point(s) and updated lines')

    def refresh_editor_lists(self):
        # Points
        try:
            # treeview: clear and populate
            for it in self.points_tv.get_children():
                self.points_tv.delete(it)
            for p in self.user_points:
                real_x = p.get('real_x', p.get('pdf_x'))
                real_y = p.get('real_y', p.get('pdf_y'))
                z_val = p.get('z', 0)
                coords = f"({real_x}, {real_y})"
                hidden_mark = '✓' if p.get('hidden', False) else ''
                # count references from lines and curves
                try:
                    pid = p['id']
                    refs = 0
                    for l in self.lines:
                        if l.get('start_id') == pid or l.get('end_id') == pid:
                            refs += 1
                    for c in self.curves:
                        if pid in c.get('arc_point_ids', []):
                            refs += 1
                        if c.get('start_id') == pid or c.get('end_id') == pid:
                            refs += 1
                except Exception:
                    refs = 0
                description = p.get('description', '3D Visualisation')
                tags = ('new',) if p.get('just_duplicated') else ()
                self.points_tv.insert('', 'end', iid=f"p_{p['id']}", values=(p['id'], coords, real_x, real_y, z_val, refs, description, hidden_mark), tags=tags)
        except Exception:
            pass

        # Lines
        try:
            for it in self.lines_tv.get_children():
                self.lines_tv.delete(it)
            for l in self.lines:
                hidden_mark = '✓' if l.get('hidden', False) else ''
                start = l.get('start_id', '')
                end = l.get('end_id', '')
                # determine z for the line: explicit 'z' if present, else average of endpoints if available
                zval = ''
                try:
                    if 'z' in l:
                        zval = l.get('z')
                    else:
                        s = next((p for p in self.user_points if p['id'] == start), None)
                        e = next((p for p in self.user_points if p['id'] == end), None)
                        if s is not None and e is not None:
                            zval = (float(s.get('z', 0)) + float(e.get('z', 0))) / 2.0
                except Exception:
                    zval = ''
                related_curves = [c.get('id') for c in self.curves if c.get('base_line_id') == l.get('id')]
                curve_display = ','.join(map(str, related_curves)) if related_curves else ''
                self.lines_tv.insert('', 'end', iid=f"l_{l['id']}", values=(l['id'], start, end, zval, curve_display, hidden_mark))
        except Exception:
            pass

        # Curves
        try:
            for it in self.curves_tv.get_children():
                self.curves_tv.delete(it)

            total_positions = max(2, int(getattr(self, 'curve_interior_points', 4)) + 2)

            for c in self.curves:
                curve_id = c.get('id')
                zval = c.get('z_level', c.get('z', 0))
                hidden_mark = '✓' if c.get('hidden', False) else ''

                line_id = next((l['id'] for l in self.lines if
                                (l['start_id'] == c.get('start_id') and l['end_id'] == c.get('end_id')) or
                                (l['start_id'] == c.get('end_id') and l['end_id'] == c.get('start_id'))
                                ), 0)
                base_line_id = c.get('base_line_id', line_id)

                ids = list(c.get('arc_point_ids', []))
                if not ids:
                    ids = []

                for position in range(total_positions):
                    if position < len(ids):
                        pid = ids[position]
                    elif ids:
                        pid = ids[-1]
                    else:
                        pid = ''

                    self.curves_tv.insert(
                        '',
                        'end',
                        iid=f"c_{curve_id}_{position}",
                        values=(curve_id, position, pid, base_line_id, zval, hidden_mark)
                    )
        except Exception:
            pass

        # RFID (currently empty placeholder)
        try:
            for it in self.rfid_tv.get_children():
                self.rfid_tv.delete(it)
            # no population logic yet; reserved for future use
        except Exception:
            pass

        # Update combobox options for point IDs
        try:
            ids = [p['id'] for p in self.user_points]
            self.line_start_cb['values'] = ids
            self.line_end_cb['values'] = ids
        except Exception:
            pass
        # Ensure UI updates immediately
        try:
            self.master.update_idletasks()
        except Exception:
            pass

        # Update Lines/Curves counters if present (keep in sync with lists)
        try:
            if hasattr(self, 'lines_label') and self.lines_label is not None:
                try:
                    self.lines_label.config(text=f"Lines: {len(self.lines)}")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, 'curves_label') and self.curves_label is not None:
                try:
                    self.curves_label.config(text=f"Curves: {len(self.curves)}")
                except Exception:
                    pass
        except Exception:
            pass

    def _treeview_sort(self, tree, column):
        """Sort a Treeview by `column`. Toggles ascending/descending each click."""
        try:
            # use id(tree) so keys are stable across same widget instances
            key = (id(tree), column)
            asc = self._tv_sort_state.get(key, True)

            items = list(tree.get_children(''))

            def _conv(v):
                # try numeric conversion first
                if v is None:
                    return ''
                try:
                    if isinstance(v, (int, float)):
                        return v
                    s = str(v).strip()
                    if s == '':
                        return ''
                    # try int then float
                    try:
                        return int(s)
                    except Exception:
                        return float(s)
                except Exception:
                    return str(v).lower()

            decorated = []
            for iid in items:
                try:
                    # prefer named column access
                    val = tree.set(iid, column)
                    if val is None:
                        val = ''
                except Exception:
                    # fallback to positional values
                    try:
                        vals = tree.item(iid, 'values') or ()
                        cols = tree['columns']
                        try:
                            idx = list(cols).index(column)
                            val = vals[idx] if idx < len(vals) else ''
                        except Exception:
                            val = ''
                    except Exception:
                        val = ''
                try:
                    keyval = _conv(val)
                except Exception:
                    keyval = str(val)
                decorated.append((keyval, iid))

            decorated.sort(key=lambda x: (x[0] is None, x[0]), reverse=not asc)

            for idx, (_k, iid) in enumerate(decorated):
                try:
                    tree.move(iid, '', idx)
                except Exception:
                    pass

            # update header labels to show an arrow on the active column
            try:
                base = self._tv_heading_texts.get(id(tree), {})
                cols = list(tree['columns'])
                for col in cols:
                    b = base.get(col, col.title())
                    if col == column:
                        arrow = '▲' if asc else '▼'
                        label = f"{b} {arrow}"
                    else:
                        label = b
                    try:
                        tree.heading(col, text=label, command=(lambda c=col, t=tree: self._treeview_sort(t, c)))
                    except Exception:
                        try:
                            tree.heading(col, text=label)
                        except Exception:
                            pass
            except Exception:
                pass

            # toggle for next time
            self._tv_sort_state[key] = not asc
        except Exception:
            return

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

    def _on_treeview_double_click(self, event):
        # Start inline edit on double click for the appropriate cell
        widget = event.widget
        try:
            region = widget.identify('region', event.x, event.y)
            if region != 'cell':
                return
            row = widget.identify_row(event.y)
            col = widget.identify_column(event.x)
            if not row or not col:
                return
            # Map Treeview column index (e.g. '#1','#2') to our headings
            col_index = int(col.replace('#', '')) - 1
            # Use the tree's actual column ordering so indexes match (includes 'refs' etc.)
            try:
                cols = tuple(widget['columns'])
            except Exception:
                # fallback to previous mappings
                if widget is self.points_tv:
                    cols = ('id', 'coords', 'x', 'y', 'z', 'refs', 'description', 'hidden')
                elif widget is self.lines_tv:
                    cols = ('id', 'from', 'to', 'z', 'curve', 'hidden')
                elif widget is self.curves_tv:
                    cols = ('curve', 'position', 'point', 'baseline', 'z', 'hidden')
                else:
                    return
            if col_index < 0 or col_index >= len(cols):
                return
            key = cols[col_index]
            # do not edit ID column
            if key in ('id', 'pts', 'curve', 'position', 'point', 'baseline'):
                return
            bbox = widget.bbox(row, column=col)
            if not bbox:
                return
            x, y, w, h = bbox
            # get current value
            cur = widget.item(row, 'values')[col_index]
            # create entry overlay
            entry = tk.Entry(widget)
            entry.insert(0, str(cur))
            entry.place(x=x, y=y, width=w, height=h)
            entry.focus_set()

            def commit(event=None):
                new_val = entry.get()
                entry.destroy()
                self._commit_tree_edit(widget, row, key, new_val)

            def cancel(event=None):
                try:
                    entry.destroy()
                except Exception:
                    pass

            entry.bind('<Return>', commit)
            entry.bind('<FocusOut>', commit)
            entry.bind('<Escape>', cancel)
        except Exception:
            return

    def _start_treeview_inline_edit(self, tree, iid, key):
        """Programmatically open the inline Entry editor for a given tree item and column key."""
        try:
            cols = list(tree['columns'])
            if key not in cols:
                return
            col_index = cols.index(key)
            col_id = f"#{col_index+1}"
            bbox = tree.bbox(iid, column=col_id)
            if not bbox:
                # ensure layout updated and try again
                try:
                    self.master.update_idletasks()
                    bbox = tree.bbox(iid, column=col_id)
                except Exception:
                    bbox = None
            if not bbox:
                return
            x, y, w, h = bbox
            vals = tree.item(iid, 'values') or ()
            cur = vals[col_index] if col_index < len(vals) else ''
            entry = tk.Entry(tree)
            entry.insert(0, str(cur))
            entry.place(x=x, y=y, width=w, height=h)
            entry.focus_set()

            def commit(event=None):
                new_val = entry.get()
                try:
                    entry.destroy()
                except Exception:
                    pass
                self._commit_tree_edit(tree, iid, key, new_val)

            def cancel(event=None):
                try:
                    entry.destroy()
                except Exception:
                    pass

            entry.bind('<Return>', commit)
            entry.bind('<FocusOut>', commit)
            entry.bind('<Escape>', cancel)
        except Exception:
            return

    def _commit_tree_edit(self, tree, iid, key, new_val):
        # Update underlying data structures based on which tree and key
        try:
            if tree is self.points_tv:
                pid = int(tree.item(iid, 'values')[0])
                p = next((pp for pp in self.user_points if pp['id'] == pid), None)
                if p is None:
                    return
                if key == 'coords':
                    # Expect 'x, y' or 'x y'
                    s = new_val.replace(',', ' ').split()
                    if len(s) >= 2:
                        try:
                            rx = float(s[0])
                            ry = float(s[1])
                            p['real_x'] = round(rx, 2)
                            p['real_y'] = round(ry, 2)
                        except ValueError:
                            return
                elif key == 'z':
                    # Validate numeric Z
                    try:
                        new_z = float(new_val)
                    except ValueError:
                        messagebox.showerror("Invalid Z", "Z value must be numeric.")
                        return
                    # If this point was freshly duplicated, apply change silently.
                    if p.get('just_duplicated'):
                        try:
                            p['z'] = new_z
                        except Exception:
                            pass
                        try:
                            del p['just_duplicated']
                        except Exception:
                            pass
                    else:
                        # Check for other points at same XY with different Z (conflict)
                        try:
                            others = self._find_points_at_xy(p)
                            # filter out those that actually differ in z
                            conflicts = [q for q in others if float(q.get('z', 0)) != new_z]
                        except Exception:
                            conflicts = []

                        if conflicts:
                            # Synchronizing existing points' Z is unsafe because they may be referenced
                            # by other lines/curves. Offer only duplication or cancel.
                            resp = messagebox.askyesno(
                                "Z level conflict",
                                f"Found {len(conflicts)} other point(s) at the same XY with different Z values.\n\n"
                                "Yes = Create a new duplicate point with this Z (you can optionally reassign references).\n"
                                "No = Cancel the change.")
                            if not resp:
                                # User chose No -> cancel
                                return
                            # Create duplicate point with same coordinates but new Z
                            new_pt_id = self._create_duplicate_point(p, new_z)
                            # Inform the user; reassigning references is a separate action
                            try:
                                messagebox.showinfo("Duplicate Created",
                                                    f"Created duplicate point ID {new_pt_id} with Z={new_z}.\n\n"
                                                    "If you want to move lines/curves to the new point, select the original point and choose 'Reassign References' from the editor context menu.")
                            except Exception:
                                pass
                        else:
                            # no conflicts, just set
                            p['z'] = new_z
                elif key == 'hidden':
                    p['hidden'] = bool(new_val) and new_val not in ('', '0', 'False', 'false')
                # If this point was freshly duplicated, clear the transient highlight now that user edited it
                try:
                    if p.get('just_duplicated'):
                        try:
                            del p['just_duplicated']
                        except Exception:
                            pass
                except Exception:
                    pass
                # refresh visuals
                self.redraw_markers()
                self.refresh_editor_lists()
                try:
                    self.update_3d_plot()
                    if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                        try:
                            self._3d_canvas.draw_idle()
                        except Exception:
                            try:
                                self._3d_canvas.draw()
                            except Exception:
                                pass
                except Exception:
                    pass
            elif tree is self.lines_tv:
                lid = int(tree.item(iid, 'values')[0])
                l = next((ll for ll in self.lines if ll['id'] == lid), None)
                if l is None:
                    return
                if key == 'from':
                    try:
                        start_id = int(str(new_val).strip())
                        if any(p['id'] == start_id for p in self.user_points):
                            l['start_id'] = start_id
                    except Exception:
                        return
                elif key == 'to':
                    try:
                        end_id = int(str(new_val).strip())
                        if any(p['id'] == end_id for p in self.user_points):
                            l['end_id'] = end_id
                    except Exception:
                        return
                elif key == 'z':
                    try:
                        new_z = float(new_val)
                    except Exception:
                        messagebox.showerror("Invalid Z", "Z value must be numeric.")
                        return
                    # Update endpoints: if safe to set directly (not referenced elsewhere), set their z.
                    # Otherwise, create duplicates at new Z and update this line to point to duplicates.
                    start_id = l.get('start_id')
                    end_id = l.get('end_id')
                    id_map = {}
                    for pid in (start_id, end_id):
                        try:
                            p = next((pp for pp in self.user_points if pp['id'] == pid), None)
                            if p is None:
                                continue
                            cur_z = float(p.get('z', 0))
                            if cur_z == new_z:
                                continue
                            # count references excluding this line
                            refs = 0
                            for ln in self.lines:
                                if ln.get('id') == l.get('id'):
                                    continue
                                if ln.get('start_id') == pid or ln.get('end_id') == pid:
                                    refs += 1
                            for cv in self.curves:
                                if pid in cv.get('arc_point_ids', []):
                                    refs += 1
                                if cv.get('start_id') == pid or cv.get('end_id') == pid:
                                    refs += 1
                            if refs > 0:
                                # duplicate point
                                new_pid = self._create_duplicate_point(p, new_z)
                                if new_pid:
                                    id_map[pid] = new_pid
                            else:
                                # safe to update in-place
                                try:
                                    p['z'] = new_z
                                except Exception:
                                    pass
                        except Exception:
                            continue
                    # apply id_map replacements to this line
                    if id_map:
                        if start_id in id_map:
                            l['start_id'] = id_map[start_id]
                        if end_id in id_map:
                            l['end_id'] = id_map[end_id]
                elif key == 'hidden':
                    l['hidden'] = bool(new_val) and new_val not in ('', '0', 'False', 'false')
                self.redraw_markers()
                self.refresh_editor_lists()
                try:
                    self.update_3d_plot()
                    if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                        try:
                            self._3d_canvas.draw_idle()
                        except Exception:
                            try:
                                self._3d_canvas.draw()
                            except Exception:
                                pass
                except Exception:
                    pass
            elif tree is self.curves_tv:
                cid = int(tree.item(iid, 'values')[0])
                c = next((cc for cc in self.curves if cc['id'] == cid), None)
                if c is None:
                    return
                if key == 'z':
                    try:
                        new_z = float(new_val)
                    except ValueError:
                        messagebox.showerror("Invalid Z", "Z value must be numeric.")
                        return
                    # Check if arc_point_ids reference points that have different Z values
                    try:
                        ids = c.get('arc_point_ids', [])
                        differing = []
                        for pid in ids:
                            p = next((pp for pp in self.user_points if pp['id'] == pid), None)
                            if p and float(p.get('z', 0)) != new_z:
                                differing.append(p)
                    except Exception:
                        differing = []
                    if differing:
                        resp = messagebox.askyesnocancel(
                            "Curve Z conflict",
                            f"Some points used by this curve have different Z values.\n\n"
                            "Yes = Apply this Z to all points used by the curve.\n"
                            "No = Keep point Zs unchanged and set only the curve's z level.\n"
                            "Cancel = Abort change.")
                        if resp is None:
                            return
                        if resp is True:
                            # Apply new Z to points used by the curve. If a point is referenced elsewhere,
                            # duplicate it at the new Z and update the curve to use the duplicate.
                            id_map = {}
                            for p in differing:
                                try:
                                    pid = p.get('id')
                                    # count references excluding this curve
                                    refs = 0
                                    for ln in self.lines:
                                        if ln.get('start_id') == pid or ln.get('end_id') == pid:
                                            refs += 1
                                    for cv in self.curves:
                                        if cv.get('id') == c.get('id'):
                                            continue
                                        if pid in cv.get('arc_point_ids', []):
                                            refs += 1
                                        if cv.get('start_id') == pid or cv.get('end_id') == pid:
                                            refs += 1
                                    if refs > 0:
                                        new_pid = self._create_duplicate_point(p, new_z)
                                        if new_pid:
                                            id_map[pid] = new_pid
                                    else:
                                        try:
                                            p['z'] = new_z
                                        except Exception:
                                            pass
                                except Exception:
                                    continue
                            # apply id_map replacements in this curve
                            if id_map:
                                try:
                                    c['arc_point_ids'] = [id_map.get(pid, pid) for pid in c.get('arc_point_ids', [])]
                                except Exception:
                                    pass
                                if c.get('start_id') in id_map:
                                    c['start_id'] = id_map[c.get('start_id')]
                                if c.get('end_id') in id_map:
                                    c['end_id'] = id_map[c.get('end_id')]
                            c['z_level'] = new_z
                        else:
                            c['z_level'] = new_z
                    else:
                        c['z_level'] = new_z
                elif key == 'hidden':
                    c['hidden'] = bool(new_val) and new_val not in ('', '0', 'False', 'false')
                self.redraw_markers()
                self.refresh_editor_lists()
                try:
                    self.update_3d_plot()
                    if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                        try:
                            self._3d_canvas.draw_idle()
                        except Exception:
                            try:
                                self._3d_canvas.draw()
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            return

    def _show_editor_menu(self, event):
        try:
            widget = event.widget
            # remember which widget invoked the editor menu so handlers can act contextually
            try:
                self._editor_menu_widget = widget
            except Exception:
                pass
            # select the row under the cursor so action applies to it
            iid = widget.identify_row(event.y)
            if iid:
                widget.selection_set(iid)
            self.editor_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.editor_menu.grab_release()
            except Exception:
                pass

    def editor_reassign_references(self):
        # Reassign references from a selected source point to a target point chosen by the user
        try:
            sel = self.points_tv.selection()
            if not sel:
                messagebox.showwarning('No Selection', 'Select a single source point first.')
                return
            if len(sel) > 1:
                messagebox.showwarning('Multiple Selection', 'Select only one source point to reassign from.')
                return
            src_iid = sel[0]
            try:
                src_id = int(self.points_tv.item(src_iid, 'values')[0])
            except Exception:
                messagebox.showerror('Invalid Selection', 'Could not determine selected point id.')
                return

            # Find references that point to src_id
            line_refs = [l for l in self.lines if l.get('start_id') == src_id or l.get('end_id') == src_id]
            curve_refs = [c for c in self.curves if src_id in c.get('arc_point_ids', []) or c.get('start_id') == src_id or c.get('end_id') == src_id]

            if not line_refs and not curve_refs:
                messagebox.showinfo('No References', f'Point {src_id} is not referenced by any line or curve.')
                return

            # Build list of candidate target points (exclude source) and show a modal
            # dialog with a combobox and a live preview of affected lines/curves.
            candidates_pts = [p for p in self.user_points if p['id'] != src_id]
            if not candidates_pts:
                messagebox.showerror('No Targets', 'No other points available to reassign to.')
                return

            from tkinter import Toplevel, Label, Button, Listbox, Scrollbar
            from tkinter import StringVar
            from tkinter import ttk

            # Helper to format a point for display in combobox
            def _fmt_point(p):
                rx = p.get('real_x', p.get('pdf_x', 0.0))
                ry = p.get('real_y', p.get('pdf_y', 0.0))
                z = p.get('z', 0)
                # count existing refs to give context
                refs = 0
                for l in self.lines:
                    if l.get('start_id') == p['id'] or l.get('end_id') == p['id']:
                        refs += 1
                for c in self.curves:
                    if p['id'] in c.get('arc_point_ids', []) or c.get('start_id') == p['id'] or c.get('end_id') == p['id']:
                        refs += 1
                return f"{p['id']} — ({rx:.2f},{ry:.2f}) z={z} refs={refs}"

            display_vals = [_fmt_point(p) for p in candidates_pts]

            def ask_target_with_preview(cands_pts, displays, default_index=0):
                res = {'ok': False, 'val': None}
                dlg = Toplevel(self.master)
                dlg.transient(self.master)
                dlg.grab_set()
                dlg.title('Select Target Point')

                Label(dlg, text=f'Source point: {src_id}').grid(row=0, column=0, columnspan=2, padx=8, pady=(8,4), sticky='w')
                Label(dlg, text='Choose a target point:').grid(row=1, column=0, sticky='w', padx=8)

                sel_var = StringVar(value=displays[default_index])
                cb = ttk.Combobox(dlg, values=displays, textvariable=sel_var, state='readonly', width=48)
                cb.grid(row=1, column=1, sticky='w', padx=8, pady=4)

                # Preview listbox showing which lines/curves will be affected and how
                Label(dlg, text='Preview of affected items:').grid(row=2, column=0, sticky='nw', padx=8, pady=(6,0))
                preview_lb = Listbox(dlg, width=60, height=10)
                preview_lb.grid(row=2, column=1, sticky='nsew', padx=8, pady=(6,0))
                preview_scroll = Scrollbar(dlg, orient='vertical', command=preview_lb.yview)
                preview_lb.configure(yscrollcommand=preview_scroll.set)
                preview_scroll.grid(row=2, column=2, sticky='ns', pady=(6,0))

                # Layout expansion
                dlg.grid_columnconfigure(1, weight=1)
                dlg.grid_rowconfigure(2, weight=1)

                # Precompute the references that will be reassigned
                src_line_refs = [l for l in self.lines if l.get('start_id') == src_id or l.get('end_id') == src_id]
                src_curve_refs = [c for c in self.curves if src_id in c.get('arc_point_ids', []) or c.get('start_id') == src_id or c.get('end_id') == src_id]

                def _update_preview(event=None):
                    # Determine selected target id
                    sel_text = sel_var.get()
                    try:
                        idx = displays.index(sel_text)
                    except Exception:
                        idx = default_index
                    tgt_pt = cands_pts[idx]
                    tgt_id = tgt_pt['id']
                    preview_lb.delete(0, 'end')
                    # Lines: show current endpoints and what they'll become
                    if src_line_refs:
                        preview_lb.insert('end', 'Lines:')
                        for l in src_line_refs:
                            sid = l.get('start_id')
                            eid = l.get('end_id')
                            new_sid = tgt_id if sid == src_id else sid
                            new_eid = tgt_id if eid == src_id else eid
                            warn = ''
                            if new_sid == new_eid:
                                warn = '  [Warning: endpoints would collapse]'
                            preview_lb.insert('end', f"  L{l.get('id')}: {sid} -> {eid}  ->  {new_sid} -> {new_eid}{warn}")
                    # Curves: show occurrences and replacements
                    if src_curve_refs:
                        preview_lb.insert('end', 'Curves:')
                        for c in src_curve_refs:
                            cid = c.get('id')
                            # count occurrences in arc list
                            occ = c.get('arc_point_ids', []).count(src_id)
                            start_match = c.get('start_id') == src_id
                            end_match = c.get('end_id') == src_id
                            parts = []
                            if occ:
                                parts.append(f"arc occurrences={occ}")
                            if start_match:
                                parts.append('start')
                            if end_match:
                                parts.append('end')
                            desc = ','.join(parts) if parts else 'refs'
                            preview_lb.insert('end', f"  C{cid}: {desc}  -> uses target {tgt_id}")

                cb.bind('<<ComboboxSelected>>', _update_preview)
                # Initialize preview
                _update_preview()

                def on_ok():
                    sel_text = sel_var.get()
                    try:
                        idx = displays.index(sel_text)
                    except Exception:
                        messagebox.showerror('Invalid', 'Select a valid target from the list.')
                        return
                    res['ok'] = True
                    res['val'] = cands_pts[idx]['id']
                    dlg.destroy()

                def on_cancel():
                    dlg.destroy()

                btnf = ttk.Frame(dlg)
                btnf.grid(row=3, column=0, columnspan=3, pady=(6,8))
                Button(btnf, text='OK', command=on_ok).pack(side='left', padx=6)
                Button(btnf, text='Cancel', command=on_cancel).pack(side='left')

                dlg.update_idletasks()
                try:
                    x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
                    y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
                    dlg.geometry(f'+{x}+{y}')
                except Exception:
                    pass

                self.master.wait_window(dlg)
                return res

            default_index = 0
            resp = ask_target_with_preview(candidates_pts, display_vals, default_index)
            if not resp.get('ok'):
                return
            tgt = resp.get('val')
            if tgt == src_id:
                messagebox.showwarning('Same Point', 'Target must be a different point.')
                return

            # Confirm with the user, showing counts
            if not messagebox.askyesno('Confirm Reassign', f'Reassign {len(line_refs)} line(s) and {len(curve_refs)} curve(s) from {src_id} to {tgt}?'):
                return

            # Perform reassignment
            try:
                self._reassign_references(src_id, tgt)
            except Exception:
                messagebox.showerror('Reassign Failed', 'An error occurred while reassigning references.')
                return
            # Refresh visuals and lists
            self.redraw_markers()
            try:
                self.update_3d_plot()
            except Exception:
                pass
            self.refresh_editor_lists()
            messagebox.showinfo('Reassign Complete', f'Reassigned references from {src_id} to {tgt}.')
        except Exception as e:
            messagebox.showerror('Error', f'Error in reassign: {e}')

    def editor_insert_line(self):
        """Insert a new line. Auto-assign ID, prompt for start/end point IDs, validate and add."""
        try:
            widget = getattr(self, '_editor_menu_widget', None)
            # only valid when invoked from the Lines treeview (but still allow direct call)
            if widget is not None and widget is not self.lines_tv:
                if messagebox.askyesno('Insert Line', 'Insert line from current selection? (Yes = use selection; No = abort)') is False:
                    return

            # gather available point ids
            point_ids = [p['id'] for p in self.user_points]
            if not point_ids:
                messagebox.showerror('No Points', 'No points available to create a line.')
                return
            # Use a small modal dialog with comboboxes to choose start/end IDs
            from tkinter import Toplevel, Label, Button
            from tkinter import StringVar
            from tkinter import ttk

            def ask_start_end(ids, default_start, default_end):
                res = {'ok': False, 'start': None, 'end': None}
                dlg = Toplevel(self.master)
                dlg.transient(self.master)
                dlg.grab_set()
                dlg.title('Insert Line')
                Label(dlg, text='Start ID:').grid(row=0, column=0, sticky='e', padx=(8,4), pady=4)
                start_var = StringVar(value=str(default_start))
                start_cb = ttk.Combobox(dlg, values=ids, textvariable=start_var, state='readonly')
                start_cb.grid(row=1, column=1, sticky='w', padx=(0,8), pady=4)
                Label(dlg, text='End ID:').grid(row=2, column=0, sticky='e', padx=(8,4), pady=4)
                end_var = StringVar(value=str(default_end))
                end_cb = ttk.Combobox(dlg, values=ids, textvariable=end_var, state='readonly')
                end_cb.grid(row=2, column=1, sticky='w', padx=(0,8), pady=4)

                # Precompute z-by-id map for filtering
                try:
                    z_by_id = {p['id']: float(p.get('z', 0)) for p in self.user_points}
                except Exception:
                    z_by_id = {i: 0.0 for i in ids}

                def filter_other(chosen_id, target_cb):
                    # Show only points that share the same Z as chosen_id
                    try:
                        if chosen_id is None:
                            target_cb['values'] = ids
                            return
                        chosen_z = z_by_id.get(int(chosen_id), None)
                        if chosen_z is None:
                            target_cb['values'] = ids
                            return
                        cand = [i for i in ids if abs(float(z_by_id.get(i, 0.0)) - chosen_z) <= 1e-9 and i != int(chosen_id)]
                        # If no other on same Z, allow selecting any different id (user may still pick)
                        if not cand:
                            cand = [i for i in ids if i != int(chosen_id)]
                        target_cb['values'] = cand
                        # if current target value not in candidates, set to first
                        try:
                            cur = int(target_cb.get())
                            if cur not in cand and cand:
                                target_cb.set(cand[0])
                        except Exception:
                            if cand:
                                target_cb.set(cand[0])
                    except Exception:
                        try:
                            target_cb['values'] = ids
                        except Exception:
                            pass

                def on_start_selected(event=None):
                    try:
                        s = int(start_var.get())
                    except Exception:
                        s = None
                    filter_other(s, end_cb)

                def on_end_selected(event=None):
                    try:
                        e = int(end_var.get())
                    except Exception:
                        e = None
                    filter_other(e, start_cb)

                # Bind selection events so either combobox can be chosen first
                start_cb.bind('<<ComboboxSelected>>', on_start_selected)
                end_cb.bind('<<ComboboxSelected>>', on_end_selected)

                # Initialize filtering to prefer end choices matching default start
                try:
                    on_start_selected()
                except Exception:
                    pass

                def on_ok():
                    try:
                        s = int(start_var.get())
                        e = int(end_var.get())
                        if s == e:
                            messagebox.showerror('Invalid IDs', 'Start and end must differ.')
                            return
                        res['ok'] = True
                        res['start'] = s
                        res['end'] = e
                        dlg.destroy()
                    except Exception:
                        messagebox.showerror('Invalid', 'Please select valid IDs.')

                def on_cancel():
                    dlg.destroy()

                btn_frame = ttk.Frame(dlg)
                btn_frame.grid(row=3, column=0, columnspan=2, pady=(6,8))
                Button(btn_frame, text='OK', command=on_ok).pack(side='left', padx=6)
                Button(btn_frame, text='Cancel', command=on_cancel).pack(side='left')

                # center dialog
                dlg.update_idletasks()
                try:
                    x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
                    y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
                    dlg.geometry(f'+{x}+{y}')
                except Exception:
                    pass

                self.master.wait_window(dlg)
                return res

            default_start = point_ids[0]
            default_end = point_ids[0] if len(point_ids) == 1 else point_ids[-1]
            resp = ask_start_end(point_ids, default_start, default_end)
            if not resp.get('ok'):
                return
            start_id = resp.get('start')
            end_id = resp.get('end')

            if start_id == end_id:
                messagebox.showerror('Invalid IDs', 'Start and end must be different point IDs.')
                return

            # validate points exist
            s = next((p for p in self.user_points if p['id'] == start_id), None)
            e = next((p for p in self.user_points if p['id'] == end_id), None)
            if s is None or e is None:
                messagebox.showerror('Invalid ID', 'One or both point IDs do not exist.')
                return

            # test z level equality
            try:
                sz = float(s.get('z', 0))
                ez = float(e.get('z', 0))
            except Exception:
                sz = float(s.get('z', 0)) if s else 0.0
                ez = float(e.get('z', 0)) if e else 0.0
            if abs(sz - ez) > 1e-9:
                messagebox.showerror('Z Mismatch', f'Cannot create line: start Z={sz}, end Z={ez} differ.')
                return

            # create line
            lid = self.next_line_id()
            new_line = {'id': lid, 'start_id': start_id, 'end_id': end_id, 'z': sz, 'hidden': False}
            self.lines.append(new_line)

            # refresh and select
            try:
                self.redraw_markers()
            except Exception:
                pass
            try:
                self.update_3d_plot()
            except Exception:
                pass
            self.refresh_editor_lists()
            try:
                iid = f"l_{lid}"
                self.lines_tv.selection_set(iid)
                self.lines_tv.see(iid)
            except Exception:
                pass
            messagebox.showinfo('Line Created', f'Created line ID {lid} from {start_id} to {end_id}.')
        except Exception as e:
            messagebox.showerror('Error', f'Error creating line: {e}')

    def editor_duplicate_point(self):
        """Duplicate the selected point(s). Prompt for Z value for each duplicate."""
        try:
            sel = list(self.points_tv.selection())
            if not sel:
                messagebox.showwarning('No Selection', 'Select one or more points to duplicate.')
                return
            from tkinter import simpledialog
            new_ids = []
            for iid in sel:
                try:
                    src_id = int(self.points_tv.item(iid, 'values')[0])
                except Exception:
                    continue
                src = next((p for p in self.user_points if p['id'] == src_id), None)
                if src is None:
                    continue
                # create duplicate with same Z initially; user can edit Z afterwards via editor
                new_id = self._create_duplicate_point(src, src.get('z', 0))
                if not new_id:
                    continue
                new_ids.append(new_id)

            # Refresh visuals and lists
            try:
                self.redraw_markers()
            except Exception:
                pass
            self.refresh_editor_lists()
            try:
                self.update_3d_plot()
            except Exception:
                pass

            # select and show the last created duplicate if present
            if new_ids:
                try:
                    last_iid = f"p_{new_ids[-1]}"
                    self.points_tv.selection_set(last_iid)
                    self.points_tv.see(last_iid)
                    # open inline editor on the Z column for the newly created point
                    try:
                        self.master.update_idletasks()
                        self._start_treeview_inline_edit(self.points_tv, last_iid, 'z')
                    except Exception:
                        pass
                except Exception:
                    pass

            messagebox.showinfo('Duplicate Complete', f'Created {len(new_ids)} duplicate point(s).')
            # keep highlight until user edits the new point; do not auto-clear
        except Exception as e:
            messagebox.showerror('Error', f'Error duplicating point: {e}')

    # --- Z-level helpers ---
    def _find_points_at_xy(self, point, tol=1e-6):
        """Return other points that share the same XY (pdf or real coords) within tolerance."""
        results = []
        try:
            x = point.get('real_x', point.get('pdf_x'))
            y = point.get('real_y', point.get('pdf_y'))
            for p in self.user_points:
                if p is point:
                    continue
                px = p.get('real_x', p.get('pdf_x'))
                py = p.get('real_y', p.get('pdf_y'))
                try:
                    if abs(float(px) - float(x)) <= tol and abs(float(py) - float(y)) <= tol:
                        results.append(p)
                except Exception:
                    continue
        except Exception:
            pass
        return results

    def _create_duplicate_point(self, orig_point, z_value):
        """Create a new point with same coordinates as orig_point but with provided z; return new id."""
        try:
            new_id = self.next_point_id()
            new_pt = {
                'id': new_id,
                'pdf_x': orig_point.get('pdf_x', orig_point.get('real_x', 0.0)),
                'pdf_y': orig_point.get('pdf_y', orig_point.get('real_y', 0.0)),
                'real_x': orig_point.get('real_x', orig_point.get('pdf_x', 0.0)),
                'real_y': orig_point.get('real_y', orig_point.get('pdf_y', 0.0)),
                'z': float(z_value),
                # mark freshly duplicated points so subsequent inline edits can be silent
                'just_duplicated': True,
                'hidden': bool(orig_point.get('hidden', False))
            }
            self.user_points.append(new_pt)
            # Refresh labels and visuals
            try:
                self.update_points_label()
            except Exception:
                pass
            try:
                self.redraw_markers()
            except Exception:
                pass
            try:
                # ensure editor lists reflect the new point
                self.refresh_editor_lists()
            except Exception:
                pass
            return new_id
        except Exception:
            return None

    def _reassign_references(self, old_pid, new_pid):
        """Replace references to old_pid with new_pid in lines and curves."""
        try:
            for l in self.lines:
                if l.get('start_id') == old_pid:
                    l['start_id'] = new_pid
                if l.get('end_id') == old_pid:
                    l['end_id'] = new_pid
            for c in self.curves:
                # replace in arc_point_ids
                if 'arc_point_ids' in c and c['arc_point_ids']:
                    c['arc_point_ids'] = [new_pid if pid == old_pid else pid for pid in c['arc_point_ids']]
                # replace start/end ids if present
                if c.get('start_id') == old_pid:
                    c['start_id'] = new_pid
                if c.get('end_id') == old_pid:
                    c['end_id'] = new_pid
        except Exception:
            pass

    def editor_toggle_hide_selected(self):
        # Toggle hidden flag for all selected items across Points, Lines and Curves
        changed = False
        try:
            for item in self.points_tv.selection():
                try:
                    pid = int(self.points_tv.item(item, 'values')[0])
                    p = next((pp for pp in self.user_points if pp['id'] == pid), None)
                    if p is not None:
                        p['hidden'] = not bool(p.get('hidden', False))
                        changed = True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for item in self.lines_tv.selection():
                try:
                    lid = int(self.lines_tv.item(item, 'values')[0])
                    l = next((ll for ll in self.lines if ll['id'] == lid), None)
                    if l is not None:
                        l['hidden'] = not bool(l.get('hidden', False))
                        changed = True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for item in self.curves_tv.selection():
                try:
                    cid = int(self.curves_tv.item(item, 'values')[0])
                    c = next((cc for cc in self.curves if cc['id'] == cid), None)
                    if c is not None:
                        c['hidden'] = not bool(c.get('hidden', False))
                        changed = True
                except Exception:
                    continue
        except Exception:
            pass

        if changed:
            self.redraw_markers()
            try:
                self.update_3d_plot()
                if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                    try:
                        self._3d_canvas.draw_idle()
                    except Exception:
                        try:
                            self._3d_canvas.draw()
                        except Exception:
                            pass
            except Exception:
                pass
            self.refresh_editor_lists()

    

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
        # Delete all selected points, lines and curves (multi-select aware)
        deleted = False
        try:
            pts_sel = list(self.points_tv.selection())
            for item in pts_sel:
                try:
                    pid = int(self.points_tv.item(item, 'values')[0])
                except Exception:
                    continue
                p = next((pp for pp in self.user_points if pp['id'] == pid), None)
                if p is None:
                    continue
                try:
                    self.delete_point(p)
                except Exception:
                    self.user_points = [pp for pp in self.user_points if pp['id'] != p['id']]
                deleted = True
        except Exception:
            pass

        try:
            lines_sel = list(self.lines_tv.selection())
            for item in lines_sel:
                try:
                    lid = int(self.lines_tv.item(item, 'values')[0])
                except Exception:
                    continue
                l = next((ll for ll in self.lines if ll['id'] == lid), None)
                if l is None:
                    continue
                try:
                    self.delete_line(l)
                except Exception:
                    self.lines = [ll for ll in self.lines if ll['id'] != l['id']]
                deleted = True
        except Exception:
            pass

        try:
            curves_sel = list(self.curves_tv.selection())
            for item in curves_sel:
                try:
                    cid = int(self.curves_tv.item(item, 'values')[0])
                except Exception:
                    continue
                c = next((cc for cc in self.curves if cc['id'] == cid), None)
                if c is None:
                    continue
                try:
                    self.delete_curve(c)
                except Exception:
                    self.curves = [cc for cc in self.curves if cc['id'] != c['id']]
                deleted = True
        except Exception:
            pass

        if deleted:
            try:
                self.update_3d_plot()
            except Exception:
                pass
        # Always refresh lists after any deletion attempt
        self.redraw_markers()
        self.update_points_label()
        self.refresh_editor_lists()

    # note: clearing of 'just_duplicated' is handled when the user makes an edit

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
        point_lookup = {p.get('id'): p for p in self.user_points if p.get('id') is not None}
        highlight_info = getattr(self, '_line_audit_highlights', None) or {}
        highlight_line_ids = set(highlight_info.get('lines', set()))
        highlight_curve_ids = set(highlight_info.get('curves', set()))
        highlight_endpoints = set(highlight_info.get('endpoints', set()))

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

        # Overlay highlighted endpoints (if any)
        if highlight_endpoints:
            hx = []
            hy = []
            hz = []
            for pid in highlight_endpoints:
                point = point_lookup.get(pid)
                if not point:
                    continue
                px = point.get('real_x', point.get('pdf_x', 0))
                py = -(point.get('real_y', point.get('pdf_y', 0)))
                pz = float(point.get('z', 0))
                hx.append(px)
                hy.append(py)
                hz.append(pz)
                all_x.append(px)
                all_y.append(py)
                all_z.append(pz)
            if hx and hy and hz:
                try:
                    ax.scatter(hx, hy, hz, c=self._3d_highlight_color, s=self._3d_point_size * 1.6, depthshade=False)
                except Exception:
                    pass

        # Highlight selected point (if any)
        if self._3d_selected_point_id:
            selected_point = point_lookup.get(self._3d_selected_point_id)
            if selected_point and not selected_point.get('hidden', False):
                sx = selected_point.get('real_x', selected_point.get('pdf_x', 0))
                sy = -(selected_point.get('real_y', selected_point.get('pdf_y', 0)))
                sz = float(selected_point.get('z', 0))
                try:
                    # Draw selection highlight with distinctive color and size
                    ax.scatter([sx], [sy], [sz], c='#00ff00', s=self._3d_point_size * 2.0, 
                              marker='o', edgecolors='black', linewidths=2, depthshade=False, zorder=1000)
                    # Add text annotation
                    label_color = 'white' if self._3d_theme == 'dark' else 'black'
                    ax.text(sx, sy, sz + 0.02, f"Selected: {self._3d_selected_point_id}", 
                           color=label_color, fontsize=10, weight='bold')
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
                highlighted = line.get('id') in highlight_line_ids if line.get('id') is not None else False
                line_color = self._3d_highlight_color if highlighted else self._3d_line_color
                line_width = 6 if highlighted else 2

                ax.plot([sx, ex], [sy, ey], [sz, ez], c=line_color, linewidth=line_width)

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
            highlighted = curve.get('id') in highlight_curve_ids if curve.get('id') is not None else False
            curve_color = self._3d_highlight_color if highlighted else self._3d_curve_color
            curve_width = 6 if highlighted else 2
            ax.plot(xs, ys, zs, c=curve_color, linewidth=curve_width)
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
        # Ensure the Matplotlib canvas redraws so visibility changes appear immediately
        try:
            if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                try:
                    self._3d_canvas.draw_idle()
                except Exception:
                    try:
                        self._3d_canvas.draw()
                    except Exception:
                        pass
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

    def _on_3d_click(self, event):
        """Handle mouse clicks in the 3D view to select points."""
        print(f"3D click event: button={event.button}, inaxes={event.inaxes == self._3d_ax if hasattr(self, '_3d_ax') else 'no ax'}")
        
        if not self._3d_initialized:
            print("3D not initialized")
            return
            
        if event.inaxes != self._3d_ax:
            print(f"Click outside axes: event.inaxes={event.inaxes}, self._3d_ax={self._3d_ax}")
            return
            
        # Only handle left clicks (button==1)
        if event.button != 1:
            print(f"Ignoring non-left click: button={event.button}")
            return
        
        try:
            # Get click position in display (pixel) coordinates
            print(f"Click coordinates: x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}")
            
            if event.x is None or event.y is None:
                print("Click coordinates are None")
                return
            
            click_display_x = event.x
            click_display_y = event.y
            
            # Find nearest point by projecting all points to screen space
            min_dist = float('inf')
            nearest_point = None
            debug_count = 0
            
            for point in self.user_points:
                if point.get('hidden', False):
                    continue
                px = point.get('real_x', point.get('pdf_x', 0))
                py = -(point.get('real_y', point.get('pdf_y', 0)))
                pz = float(point.get('z', 0))
                
                # Project point to 2D screen space (display coordinates)
                try:
                    # For 3D plots, use proj3d to convert 3D coords to 2D display coords
                    from mpl_toolkits.mplot3d import proj3d
                    proj_x, proj_y, _ = proj3d.proj_transform(px, py, pz, self._3d_ax.get_proj())
                    
                    # Convert from normalized coordinates to display pixels
                    # The projection gives us normalized coordinates, we need to transform to display
                    display_coords = self._3d_ax.transData.transform([(proj_x, proj_y)])[0]
                    proj_x_display = display_coords[0]
                    proj_y_display = display_coords[1]
                    
                    # Calculate pixel distance between click and projected point
                    dist = ((proj_x_display - click_display_x)**2 + (proj_y_display - click_display_y)**2)**0.5
                    
                    if debug_count < 3:  # Show first 3 points for debugging
                        print(f"Point {point.get('id')}: 3D=({px:.1f},{py:.1f},{pz:.1f}) -> 2D=({proj_x_display:.1f},{proj_y_display:.1f}), dist={dist:.1f}px")
                        debug_count += 1
                    
                    if dist < min_dist:
                        min_dist = dist
                        nearest_point = point
                except Exception as e:
                    # If projection fails, skip this point
                    if debug_count < 3:
                        print(f"Point {point.get('id')} projection failed: {e}")
                        import traceback
                        traceback.print_exc()
                        debug_count += 1
                    continue
            
            print(f"Nearest point: {nearest_point.get('id') if nearest_point else None}, distance: {min_dist:.1f}px")
            
            # Selection threshold in pixels (increased for easier selection)
            if min_dist > 500:  # pixels
                # Provide feedback when no point is close enough
                self.update_status(f"No point within selection range (nearest: {min_dist:.0f}px)")
                return
            
            if nearest_point:
                self._3d_selected_point_id = nearest_point.get('id')
                
                # If line audit window is open, populate the start field and auto-run audit
                if self._line_audit_window and self._line_audit_window.winfo_exists():
                    if self._line_audit_start_var:
                        self._line_audit_start_var.set(str(self._3d_selected_point_id))
                        # Automatically run the audit with the newly selected point
                        try:
                            self._run_line_audit_from_ui()
                        except Exception as e:
                            print(f"Auto-run audit failed: {e}")
                
                # Update status and redraw with highlight
                self.update_status(f"Selected point {self._3d_selected_point_id} in 3D view (distance: {min_dist:.0f}px)")
                self.update_3d_plot()
        except Exception as e:
            print(f"3D click handler error: {e}")
            import traceback
            traceback.print_exc()

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

    def open_display_options(self):
        """Open a separate Options window to edit display colors and sizes."""
        try:
            from tkinter import Toplevel, Label, Button
            dlg = Toplevel(self.master)
            dlg.transient(self.master)
            dlg.title('Display Options')
            dlg.grab_set()

            from tkinter import colorchooser

            def choose_point_color():
                c = colorchooser.askcolor(title='Choose point color', color=self.point_color_2d)
                if c and c[1]:
                    self.point_color_2d = c[1]
                    try:
                        self._3d_point_color = self.point_color_2d
                    except Exception:
                        pass
                    try:
                        if self.point_color_swatch is not None:
                            self.point_color_swatch.config(bg=self.point_color_2d)
                    except Exception:
                        pass
                    try:
                        self.redraw_markers()
                    except Exception:
                        pass

            def choose_line_color():
                c = colorchooser.askcolor(title='Choose line color', color=self.line_color_2d)
                if c and c[1]:
                    self.line_color_2d = c[1]
                    try:
                        self._3d_line_color = self.line_color_2d
                    except Exception:
                        pass
                    try:
                        if self.line_color_swatch is not None:
                            self.line_color_swatch.config(bg=self.line_color_2d)
                    except Exception:
                        pass
                    try:
                        self.redraw_markers()
                    except Exception:
                        pass

            def choose_curve_color():
                c = colorchooser.askcolor(title='Choose curve color', color=self.curve_color_2d)
                if c and c[1]:
                    self.curve_color_2d = c[1]
                    try:
                        self._3d_curve_color = self.curve_color_2d
                    except Exception:
                        pass
                    try:
                        if self.curve_color_swatch is not None:
                            self.curve_color_swatch.config(bg=self.curve_color_2d)
                    except Exception:
                        pass
                    try:
                        self.redraw_markers()
                    except Exception:
                        pass

            # color row
            row = 0
            tk.Label(dlg, text='Point Color:').grid(row=row, column=0, sticky='e', padx=6, pady=4)
            pc_btn = Button(dlg, text='Choose...', command=choose_point_color)
            pc_btn.grid(row=row, column=1, sticky='w', padx=6, pady=4)
            self.point_color_swatch = tk.Label(dlg, width=3, bg=self.point_color_2d, relief='sunken')
            self.point_color_swatch.grid(row=row, column=2, sticky='w', padx=6)

            row += 1
            tk.Label(dlg, text='Line Color:').grid(row=row, column=0, sticky='e', padx=6, pady=4)
            lc_btn = Button(dlg, text='Choose...', command=choose_line_color)
            lc_btn.grid(row=row, column=1, sticky='w', padx=6, pady=4)
            self.line_color_swatch = tk.Label(dlg, width=3, bg=self.line_color_2d, relief='sunken')
            self.line_color_swatch.grid(row=row, column=2, sticky='w', padx=6)

            row += 1
            tk.Label(dlg, text='Curve Color:').grid(row=row, column=0, sticky='e', padx=6, pady=4)
            cc_btn = Button(dlg, text='Choose...', command=choose_curve_color)
            cc_btn.grid(row=row, column=1, sticky='w', padx=6, pady=4)
            self.curve_color_swatch = tk.Label(dlg, width=3, bg=self.curve_color_2d, relief='sunken')
            self.curve_color_swatch.grid(row=row, column=2, sticky='w', padx=6)

            row += 1
            # Sizes
            tk.Label(dlg, text='Point Size:').grid(row=row, column=0, sticky='e', padx=6, pady=6)
            ps = tk.Scale(dlg, from_=1, to=30, orient='horizontal', variable=self.point_size_var, command=lambda v: self._set_point_size(v))
            ps.grid(row=row, column=1, columnspan=2, sticky='ew', padx=6)

            row += 1
            tk.Label(dlg, text='Line Width:').grid(row=row, column=0, sticky='e', padx=6, pady=6)
            lw = tk.Scale(dlg, from_=1, to=12, orient='horizontal', variable=self.line_width_var, command=lambda v: self._set_line_width(v))
            lw.grid(row=row, column=1, columnspan=2, sticky='ew', padx=6)

            row += 1
            tk.Label(dlg, text='Label Font:').grid(row=row, column=0, sticky='e', padx=6, pady=6)
            fs = tk.Scale(dlg, from_=6, to=32, orient='horizontal', variable=self.font_size_var, command=lambda v: self._set_label_font_size(v))
            fs.grid(row=row, column=1, columnspan=2, sticky='ew', padx=6)

            # Close button
            row += 1
            btnf = tk.Frame(dlg)
            btnf.grid(row=row, column=0, columnspan=3, pady=(8,10))
            Button(btnf, text='Close', command=dlg.destroy).pack()

            dlg.update_idletasks()
            try:
                x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
                y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
                dlg.geometry(f'+{x}+{y}')
            except Exception:
                pass
        except Exception:
            return

    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        self.update_status("Configuration saved")

    def update_status(self, message):
        self.status_label.config(text=message)
        self.master.update_idletasks()

    def _update_pdf_fade(self):
        """Update the PDF fade overlay based on slider value without re-rendering the page."""
        try:
            if getattr(self, 'pdf_fade_rect', None) is None:
                return
            level = 0
            try:
                level = int(self.fade_slider.get())
            except Exception:
                pass
            # Map 0-100 to Tk stipple steps (discrete): none, gray12, gray25, gray50, gray75
            if level <= 0:
                self.canvas.itemconfigure(self.pdf_fade_rect, state='hidden')
                return
            self.canvas.itemconfigure(self.pdf_fade_rect, state='normal')
            if level <= 12:
                stip = 'gray12'
            elif level <= 25:
                stip = 'gray25'
            elif level <= 50:
                stip = 'gray50'
            else:
                stip = 'gray75'
            try:
                self.canvas.itemconfigure(self.pdf_fade_rect, stipple=stip)
            except Exception:
                # Fallback: toggle visibility for coarse effect
                if level < 50:
                    self.canvas.itemconfigure(self.pdf_fade_rect, state='hidden')
                else:
                    self.canvas.itemconfigure(self.pdf_fade_rect, state='normal')
        except Exception:
            pass

    def update_calibration_status(self):
        """Update the calibration status indicator based on transformation_matrix."""
        if self.transformation_matrix is not None:
            self.calib_status.config(text="Calibrated", bg="#4CAF50", fg="white")
        else:
            self.calib_status.config(text="Not Calibrated", bg="#ff6666", fg="white")

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
            # create a PIL image and cache it for fast preview resizing during interactive zoom
            try:
                pil_img = Image.open(io.BytesIO(img_data)).convert('RGBA')
                self._last_rendered_pil = pil_img
                self.photo_image = ImageTk.PhotoImage(pil_img)
            except Exception:
                # fallback: keep previous photo_image if any
                try:
                    self.photo_image = ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))
                except Exception:
                    pass
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
        new_zoom = self.zoom_level * zoom_factor

        # Quick preview: if we have a cached PIL image for the page, resize it quickly
        try:
            pil = getattr(self, '_last_rendered_pil', None)
            if pil is not None:
                # Compute scale relative to last rendered PIL (which represents current zoom)
                try:
                    scale = new_zoom / old_zoom if old_zoom != 0 else 1.0
                except Exception:
                    scale = 1.0
                try:
                    new_w = max(1, int(pil.width * scale))
                    new_h = max(1, int(pil.height * scale))
                    preview = pil.resize((new_w, new_h), resample=Image.BILINEAR)
                    self.photo_image = ImageTk.PhotoImage(preview)
                    if self.canvas_image:
                        try:
                            self.canvas.itemconfig(self.canvas_image, image=self.photo_image)
                        except Exception:
                            self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.photo_image)
                    else:
                        self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.photo_image)
                    # adjust scrollregion to preview size
                    try:
                        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        # Schedule a full quality render after a short debounce interval
        self._pending_zoom_pdf_coords = (x_pdf, y_pdf)
        self._pending_zoom_level = new_zoom
        # cancel previous job
        try:
            if getattr(self, '_zoom_render_job', None):
                self.master.after_cancel(self._zoom_render_job)
        except Exception:
            pass
        try:
            # schedule final render after 250ms of no further zoom events
            self._zoom_render_job = self.master.after(250, self._do_full_zoom_render)
        except Exception:
            # fallback to immediate render
            try:
                self._do_full_zoom_render()
            except Exception:
                pass

    def redraw_markers(self):
        # Remove existing canvas items for our element tags so redraw reflects size/font changes
        try:
            self.canvas.delete("user_point")
        except Exception:
            pass
        try:
            self.canvas.delete("point_label")
        except Exception:
            pass
        try:
            self.canvas.delete("user_line")
        except Exception:
            pass
        try:
            self.canvas.delete("line_label")
        except Exception:
            pass
        try:
            self.canvas.delete("user_curve")
        except Exception:
            pass
        try:
            self.canvas.delete("arc_point")
        except Exception:
            pass
        try:
            self.canvas.delete("calibration_point")
        except Exception:
            pass

        self.point_markers.clear()
        self.point_labels.clear()
        self.calibration_markers.clear()
        size = getattr(self, 'point_marker_size', 5)

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
                clr = getattr(self, 'point_color_2d', 'blue')
                m_id = self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                              outline=clr, fill=clr, tags="user_point", width=2)
                self.point_markers[point['id']] = m_id
                # create or update a label for the point id
                # always compute a safe label font size (at least 1)
                lbl_size = max(1, int(getattr(self, 'label_font_size', 10) or 10))
                text_x = x + (size + 6)
                text_y = y - (size + 2)
                # if a previous text canvas id exists, remove it to avoid stale references
                try:
                    old_tid = point.get('text_id') or self.point_labels.get(point['id'])
                    if old_tid:
                        try:
                            self.canvas.delete(old_tid)
                        except Exception:
                            pass
                except Exception:
                    pass
                # create a fresh label with the current font size
                try:
                    t_id = self.canvas.create_text(text_x, text_y, text=str(point['id']), fill=clr, tags="point_label", font=("Helvetica", lbl_size))
                    self.point_labels[point['id']] = t_id
                    try:
                        point['text_id'] = t_id
                    except Exception:
                        pass
                except Exception:
                    pass

        for line in self.lines:
            start = next(p for p in self.user_points if p['id'] == line['start_id'])
            end = next(p for p in self.user_points if p['id'] == line['end_id'])
            x1 = start['pdf_x'] * self.zoom_level
            y1 = start['pdf_y'] * self.zoom_level
            x2 = end['pdf_x'] * self.zoom_level
            y2 = end['pdf_y'] * self.zoom_level
            lw = getattr(self, 'line_width_2d', 4)
            lclr = getattr(self, 'line_color_2d', 'orange')
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill=lclr, width=lw, tags="user_line")
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
            # robust text label handling: treat falsy or missing text_id as absent
            # always recreate line label to ensure font/position are correct
            try:
                old_tid = line.get('text_id')
                if old_tid:
                    try:
                        self.canvas.delete(old_tid)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                lbl_size = max(1, int(getattr(self, 'label_font_size', 12) or 12))
                t_id = self.canvas.create_text(mid_x, text_y, text=str(line['id']), fill=lclr, tags="line_label", font=("Helvetica", lbl_size))
                line['text_id'] = t_id
            except Exception:
                pass

        for curve in self.curves:
            coords = []
            for px, py in curve['arc_points_pdf']:
                coords.extend([px * self.zoom_level, py * self.zoom_level])
            cwidth = getattr(self, 'curve_width_2d', 2)
            cclr = getattr(self, 'curve_color_2d', 'purple')
            curve_id = self.canvas.create_line(*coords, fill=cclr, width=cwidth, smooth=True, splinesteps=36, tags="user_curve")
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
                                                   outline=cclr, fill=cclr, tags="arc_point", width=2)
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

    # --- Display setters used by the sliders ---
    def _set_point_size(self, v):
        try:
            self.point_marker_size = int(float(v))
        except Exception:
            return
        try:
            self.redraw_markers()
        except Exception:
            pass

    def _set_line_width(self, v):
        try:
            self.line_width_2d = int(float(v))
        except Exception:
            return
        try:
            self.redraw_markers()
        except Exception:
            pass

    def _set_label_font_size(self, v):
        try:
            self.label_font_size = int(float(v))
        except Exception:
            return
        try:
            self.redraw_markers()
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
            self.update_calibration_status()
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
            # Reverse vertical scroll direction
            self.canvas.yview_scroll(-delta, "units")

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
        elif mode in ["duplicate_points", "duplicate_lines", "duplicate_curves"]:
            self.handle_duplication_click(event)
        elif mode == "identify":
            # Identify multiple nearby items at this location and present details
            try:
                candidates = self.find_items_near(pdf_x, pdf_y)
            except Exception:
                candidates = None
            if not candidates:
                self.update_status("No nearby items found")
                return
            # Build a readable listing
            lines = []
            for kind, item, dist in candidates:
                if kind == 'point':
                    lines.append(f"Point id={item.get('id')} pdf=({item.get('pdf_x')},{item.get('pdf_y')}) z={item.get('z', '')}")
                elif kind == 'line':
                    lines.append(f"Line id={item.get('id')} start={item.get('start_id')} end={item.get('end_id')}")
                else:
                    lines.append(f"Curve id={item.get('id')} z={item.get('z_level', item.get('z',''))} arc_points={len(item.get('arc_point_ids',[]))}")
            try:
                from tkinter import messagebox
                messagebox.showinfo("Identify Results", "\n".join(lines))
            except Exception:
                self.update_status("Identified: " + "; ".join(lines))
        else:
            self.update_status(f"Unknown mode: {mode}")

    def save_project(self):
        # Allow saving once a PDF is loaded or calibration exists.
        # Points, lines and curves are optional for a valid project.
        if self.pdf_doc is None and self.transformation_matrix is None:
            messagebox.showwarning("No Data", "No PDF loaded and no calibration available. Load a PDF or complete calibration before saving.")
            return
        # If we have an existing project path, save directly; otherwise route to Save As
        project_path = self._project_path
        if not project_path:
            return self.save_project_as()
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
        # Include display settings so project remembers user's visual choices
        try:
            project_data['display'] = {
                'point_color_2d': getattr(self, 'point_color_2d', None),
                'line_color_2d': getattr(self, 'line_color_2d', None),
                'curve_color_2d': getattr(self, 'curve_color_2d', None),
                'point_marker_size': getattr(self, 'point_marker_size', None),
                'line_width_2d': getattr(self, 'line_width_2d', None),
                'curve_width_2d': getattr(self, 'curve_width_2d', None),
                'label_font_size': getattr(self, 'label_font_size', None),
                # also persist 3D preferences where useful
                '3d_point_size': getattr(self, '_3d_point_size', None),
                '3d_point_color': getattr(self, '_3d_point_color', None),
                '3d_line_color': getattr(self, '_3d_line_color', None),
                '3d_curve_color': getattr(self, '_3d_curve_color', None),
            }
        except Exception:
            pass
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
            self._modified = False  # Reset modified flag after successful save
            messagebox.showinfo("Saved", f"Project saved to {project_path}")
            self.update_status(f"Project saved to {project_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving project: {e}")

    def save_project_as(self):
        # Save with choose path, then set current project path
        if self.pdf_doc is None and self.transformation_matrix is None:
            messagebox.showwarning("No Data", "No PDF loaded and no calibration available. Load a PDF or complete calibration before saving.")
            return
        project_path = filedialog.asksaveasfilename(defaultextension=".dig",
                                                    filetypes=[("DIG Project Files", "*.dig")],
                                                    title="Save Project As")
        if not project_path:
            return
        self._project_path = project_path
        return self.save_project()

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
                self._current_backup_file = bak_name
            except Exception:
                pass
            # Remember current project path
            self._project_path = project_path

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
            self.update_calibration_status()
            self.user_points = project_data.get("points", [])
            self.lines = project_data.get("lines", [])
            self.curves = project_data.get("curves", [])
            self.zoom_level = project_data.get("zoom_level", 1.0)
            # Restore display settings if present
            try:
                dsp = project_data.get('display', {}) or {}
                if 'point_color_2d' in dsp and dsp['point_color_2d']:
                    self.point_color_2d = dsp['point_color_2d']
                if 'line_color_2d' in dsp and dsp['line_color_2d']:
                    self.line_color_2d = dsp['line_color_2d']
                if 'curve_color_2d' in dsp and dsp['curve_color_2d']:
                    self.curve_color_2d = dsp['curve_color_2d']
                if 'point_marker_size' in dsp and dsp['point_marker_size'] is not None:
                    try:
                        self.point_marker_size = int(dsp['point_marker_size'])
                        self.point_size_var.set(self.point_marker_size)
                    except Exception:
                        pass
                if 'line_width_2d' in dsp and dsp['line_width_2d'] is not None:
                    try:
                        self.line_width_2d = int(dsp['line_width_2d'])
                        self.line_width_var.set(self.line_width_2d)
                    except Exception:
                        pass
                if 'curve_width_2d' in dsp and dsp['curve_width_2d'] is not None:
                    try:
                        self.curve_width_2d = int(dsp['curve_width_2d'])
                    except Exception:
                        pass
                if 'label_font_size' in dsp and dsp['label_font_size'] is not None:
                    try:
                        self.label_font_size = int(dsp['label_font_size'])
                        self.font_size_var.set(self.label_font_size)
                    except Exception:
                        pass
                # 3D prefs
                if '3d_point_size' in dsp and dsp['3d_point_size'] is not None:
                    try:
                        self._3d_point_size = int(dsp['3d_point_size'])
                    except Exception:
                        pass
                if '3d_point_color' in dsp and dsp['3d_point_color']:
                    try:
                        self._3d_point_color = dsp['3d_point_color']
                    except Exception:
                        pass
                if '3d_line_color' in dsp and dsp['3d_line_color']:
                    try:
                        self._3d_line_color = dsp['3d_line_color']
                    except Exception:
                        pass
                if '3d_curve_color' in dsp and dsp['3d_curve_color']:
                    try:
                        self._3d_curve_color = dsp['3d_curve_color']
                    except Exception:
                        pass
                # update swatches if the UI exists
                try:
                    if hasattr(self, 'point_color_swatch') and self.point_color_swatch is not None:
                        self.point_color_swatch.config(bg=self.point_color_2d)
                except Exception:
                    pass
                try:
                    if hasattr(self, 'line_color_swatch') and self.line_color_swatch is not None:
                        self.line_color_swatch.config(bg=self.line_color_2d)
                except Exception:
                    pass
                try:
                    if hasattr(self, 'curve_color_swatch') and self.curve_color_swatch is not None:
                        self.curve_color_swatch.config(bg=self.curve_color_2d)
                except Exception:
                    pass
            except Exception:
                pass
            if self.zoom_entry:
                self.zoom_entry.delete(0, tk.END)
                self.zoom_entry.insert(0, f"{self.zoom_level*100:.0f}")
            self.display_page()
            self.update_points_label()
            # ID counters are deterministic via next_* helpers; no legacy counter sync required

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
            # Force immediate redraw of calibration points and IDs so they appear right after loading
            try:
                self.redraw_markers()
            except Exception:
                pass
            try:
                self.refresh_editor_lists()
            except Exception:
                pass
            try:
                # Ensure canvas refresh
                if self.canvas is not None:
                    try:
                        self.canvas.update_idletasks()
                        self.canvas.update()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(self, '_3d_canvas') and self._3d_canvas is not None:
                    try:
                        self._3d_canvas.draw_idle()
                    except Exception:
                        try:
                            self._3d_canvas.draw()
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Load Error", f"Error loading project: {e}")

    def export_data(self):  
        if self.transformation_matrix is None:
            messagebox.showwarning("Export Error", "Calibration required before export.")
            return

        from tkinter import simpledialog
        
        # Propose project name based on current file
        default_name = ""
        if self._project_path:
            default_name = os.path.splitext(os.path.basename(self._project_path))[0]
            
        project_name = simpledialog.askstring("Project Name", "Enter project name for export:", initialvalue=default_name)
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
                # Swap Y and Z, and export as integers
                x = int(round(point['real_x']))
                z = int(round(point['real_y']))  # real_y becomes Z
                y = int(round(point.get('z', 0.0)))  # z becomes Y
                f.write(f"{point['id']},{x},{y},{z}\n")

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

            # Remove existing data first (Curves, Lines, Points)
            f.write("-- Clear existing data (order: Curves, Lines, Points)\n")
            f.write("DELETE FROM SeasPathDB.dbo.Visualization_Curve;\n")
            f.write("DELETE FROM SeasPathDB.dbo.Visualization_Edge;\n")
            f.write("DELETE FROM SeasPathDB.dbo.Visualization_Coordinate;\n\n")

            # Points table
            f.write("-- Insert Visualization_Coordinate (Points)\n")
            f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Coordinate ON;\n")
            for point in self.user_points:
                # Swap Y and Z, and export as integers
                x = int(round(point['real_x']))
                z = int(round(point['real_y']))  # real_y becomes Z
                y = int(round(point.get('z', 0.0)))  # z becomes Y
                desc = point.get('description', '3D Visualisation')
                f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Coordinate (Id, X, Y, Z, Description) ")
                f.write(f"VALUES ({point['id']}, {x}, {y}, {z}, '{desc}');\n")
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
            # Id column removed as requested
            # f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve ON;\n")
            for curve in self.curves:
                line_id = next((l['id'] for l in self.lines if
                                (l['start_id'] == curve.get('start_id') and l['end_id'] == curve.get('end_id')) or
                                (l['start_id'] == curve.get('end_id') and l['end_id'] == curve.get('start_id'))
                                ), 0)
                edge_id = curve.get('base_line_id', line_id)
                ids = curve.get('arc_point_ids', [])
                for position in range(total_positions):
                    pid = ids[position] if position < len(ids) else ids[-1]
                    f.write(f"INSERT INTO SeasPathDB.dbo.Visualization_Curve (PositionNumber, CoordinateId, EdgeId) ")
                    f.write(f"VALUES ({position}, {pid}, {edge_id});\n")
            # f.write("SET IDENTITY_INSERT SeasPathDB.dbo.Visualization_Curve OFF;\n")

        messagebox.showinfo("Export Success", f"Exported data to {export_dir}\nFiles: {project_name}_points.txt, {project_name}_lines.txt, {project_name}_curves.txt, {project_name}_insert.sql")

    def find_closest_item_by_type(self, pdf_x, pdf_y, entity_type):
        """Find closest item of a specific type (point, line, or curve)."""
        # Get all candidates
        candidates = self.find_items_near(pdf_x, pdf_y)
        
        # Debug: log what was found
        if not candidates:
            self.update_status(f"No items found near click location (PDF: {pdf_x:.1f}, {pdf_y:.1f})")
            return None
        
        # Filter by type (note: find_items_near returns 'curve_arc' for curves and 'curve_baseline' for baseline clicks)
        if entity_type == 'curve':
            filtered = [(kind, item, dist) for kind, item, dist in candidates if kind in ('curve', 'curve_arc', 'curve_baseline')]
        else:
            filtered = [(kind, item, dist) for kind, item, dist in candidates if kind == entity_type]
        
        if not filtered:
            # Debug: show what types were found
            found_types = set(kind for kind, _, _ in candidates)
            self.update_status(f"No {entity_type} found. Found: {', '.join(found_types)}")
            return None
        
        # If only one, return it
        if len(filtered) == 1:
            kind, item, _ = filtered[0]
            return (kind, item)
        
        # Multiple candidates: ask user which to select
        from tkinter import simpledialog, messagebox
        choices = []
        for idx, (kind, item, dist) in enumerate(filtered, start=1):
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
        
        choice_str = "\n".join(choices)
        answer = simpledialog.askstring("Select Entity", f"Multiple {entity_type}s found. Enter number:\n{choice_str}")
        if answer:
            try:
                selection = int(answer)
                if 1 <= selection <= len(filtered):
                    kind, item, _ = filtered[selection - 1]
                    return (kind, item)
            except ValueError:
                pass
        return None

    def handle_duplication_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level

        # Determine what type to search for based on mode
        mode = self.mode_var.get()
        if mode == 'duplicate_points':
            search_type = 'point'
        elif mode == 'duplicate_lines':
            search_type = 'line'
        elif mode == 'duplicate_curves':
            search_type = 'curve'
        else:
            self.update_status("Invalid duplication mode.")
            return

        # Find closest entity of the specified type
        selected = self.find_closest_item_by_type(pdf_x, pdf_y, search_type)
        if selected is None:
            self.update_status(f"No {search_type} close enough to duplicate.")
            return

        entity_type, entity = selected

        # Ask for Z values with last used value as default
        from tkinter import simpledialog
        prompt_text = "Enter Z values (comma-delimited):\nExample: 1,2,3"
        if self._last_z_value:
            prompt_text += f"\n\nLast used: {self._last_z_value}"
        
        z_input = simpledialog.askstring(
            "Duplicate Entity",
            prompt_text,
            initialvalue=self._last_z_value
        )
        if not z_input:
            return

        try:
            z_values = [float(z.strip()) for z in z_input.split(',')]
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid Z values.")
            return
        
        # Remember this Z value for next time
        self._last_z_value = z_input

        # Duplicate based on entity type
        if entity_type == 'point':
            self.duplicate_point(entity, z_values)
        elif entity_type == 'line':
            self.duplicate_line(entity, z_values)
        elif entity_type in ('curve', 'curve_arc', 'curve_baseline'):
            self.duplicate_curve(entity, z_values)

        self.redraw_markers()
        self.update_points_label()
        self.update_status(f"Duplicated {entity_type} at {len(z_values)} Z levels.")

    def export_pdf_to_png(self):
        """Export current PDF page to PNG at full resolution."""
        if not self.pdf_doc:
            messagebox.showwarning("No PDF", "Please open a PDF file first.")
            return
        
        # Ask for output file
        from tkinter import filedialog
        
        initial_file = "export.png"
        if self._project_path:
            base = os.path.splitext(os.path.basename(self._project_path))[0]
            initial_file = f"{base}.png"
            
        output_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=initial_file,
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Save PDF page as PNG"
        )
        if not output_path:
            return
        
        try:
            # Get current page
            page = self.pdf_doc[self.current_page]
            
            # Render at high resolution (300 DPI)
            # Default is 72 DPI, so 300/72 = 4.166... zoom factor
            zoom = 300 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Save directly to PNG
            pix.save(output_path)
            
            messagebox.showinfo(
                "Export Complete",
                f"PDF page exported to:\n{output_path}\n\nResolution: {pix.width}x{pix.height} pixels"
            )
            self.update_status(f"Exported PDF page to {os.path.basename(output_path)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export PDF to PNG:\n{e}")

    def find_point_by_coords(self, real_x, real_y, z):
        """Return existing point matching integer-rounded coords and z, else None."""
        try:
            target = (int(round(real_x)), int(round(real_y)), int(round(z)))
        except Exception:
            target = (real_x, real_y, z)
        for existing in self.user_points:
            ex = int(round(existing.get('real_x', existing.get('pdf_x', 0))))
            ey = int(round(existing.get('real_y', existing.get('pdf_y', 0))))
            ez = int(round(existing.get('z', 0)))
            if (ex, ey, ez) == target:
                return existing
        return None

    def duplicate_point(self, point, z_values):
        for z in z_values:
            new_point = point.copy()
            # Use centralized helper to allocate a new point id
            new_id = self.next_point_id()
            new_point['id'] = new_id
            new_point['z'] = z
            self.user_points.append(new_point)
        self.mark_modified()

    def duplicate_line(self, line, z_values):
        # Check if this line is a baseline for any curve
        line_id = line.get('id')
        curve_using_line = next((c for c in self.curves if c.get('base_line_id') == line_id), None)
        
        if curve_using_line:
            # This line is a curve baseline - duplicate the entire curve instead
            self.duplicate_curve(curve_using_line, z_values)
            return
        
        # Regular line duplication
        for z in z_values:
            # Get start and end points
            start = next(p for p in self.user_points if p['id'] == line['start_id'])
            end = next(p for p in self.user_points if p['id'] == line['end_id'])

            # Determine or create start point at new Z level
            start_real_x = start.get('real_x', start.get('pdf_x', 0))
            start_real_y = start.get('real_y', start.get('pdf_y', 0))
            existing_start = self.find_point_by_coords(start_real_x, start_real_y, z)
            if existing_start:
                start_id = existing_start['id']
            else:
                start_id = self.next_point_id()
                new_start = start.copy()
                new_start['id'] = start_id
                new_start['z'] = z
                self.user_points.append(new_start)

            # Determine or create end point at new Z level
            end_real_x = end.get('real_x', end.get('pdf_x', 0))
            end_real_y = end.get('real_y', end.get('pdf_y', 0))
            existing_end = self.find_point_by_coords(end_real_x, end_real_y, z)
            if existing_end:
                end_id = existing_end['id']
            else:
                end_id = self.next_point_id()
                new_end = end.copy()
                new_end['id'] = end_id
                new_end['z'] = z
                self.user_points.append(new_end)

            # Create new line id
            new_lid = self.next_line_id()

            new_line = line.copy()
            new_line['id'] = new_lid
            new_line['start_id'] = start_id
            new_line['end_id'] = end_id
            self.lines.append(new_line)
        self.mark_modified()

    def duplicate_curve(self, curve, z_values):
        for z in z_values:
            # Duplicate all arc points at new Z level
            new_arc_point_ids = []
            for arc_point_id in curve['arc_point_ids']:
                orig_point = next(p for p in self.user_points if p['id'] == arc_point_id)
                real_x = orig_point.get('real_x', orig_point.get('pdf_x', 0))
                real_y = orig_point.get('real_y', orig_point.get('pdf_y', 0))
                existing = self.find_point_by_coords(real_x, real_y, z)
                if existing:
                    new_arc_point_ids.append(existing['id'])
                    continue
                new_point = orig_point.copy()
                new_pid = self.next_point_id()
                new_point['id'] = new_pid
                new_point['z'] = z
                self.user_points.append(new_point)
                new_arc_point_ids.append(new_pid)

            # Build new arc_points_real list so 3D view uses the duplicated Z level
            new_arc_points_real = []
            for pid in new_arc_point_ids:
                point_ref = next((p for p in self.user_points if p['id'] == pid), None)
                if not point_ref:
                    continue
                rx = int(round(point_ref.get('real_x', point_ref.get('pdf_x', 0))))
                ry = int(round(point_ref.get('real_y', point_ref.get('pdf_y', 0))))
                rz = int(round(point_ref.get('z', z)))
                new_arc_points_real.append((rx, ry, rz))

            # Duplicate the baseline if it exists
            base_line_id = curve.get('base_line_id')
            new_base_line_id = 0
            new_start_id = None
            new_end_id = None
            
            if base_line_id:
                base_line = next((l for l in self.lines if l.get('id') == base_line_id), None)
                if base_line:
                    # Get baseline endpoints
                    start = next((p for p in self.user_points if p['id'] == base_line['start_id']), None)
                    end = next((p for p in self.user_points if p['id'] == base_line['end_id']), None)
                    
                    if start and end:
                        # Create new start point
                        start_real_x = start.get('real_x', start.get('pdf_x', 0))
                        start_real_y = start.get('real_y', start.get('pdf_y', 0))
                        existing_start = self.find_point_by_coords(start_real_x, start_real_y, z)
                        if existing_start:
                            new_start_id = existing_start['id']
                        else:
                            new_start = start.copy()
                            new_start_id = self.next_point_id()
                            new_start['id'] = new_start_id
                            new_start['z'] = z
                            self.user_points.append(new_start)
                        
                        # Create new end point
                        end_real_x = end.get('real_x', end.get('pdf_x', 0))
                        end_real_y = end.get('real_y', end.get('pdf_y', 0))
                        existing_end = self.find_point_by_coords(end_real_x, end_real_y, z)
                        if existing_end:
                            new_end_id = existing_end['id']
                        else:
                            new_end = end.copy()
                            new_end_id = self.next_point_id()
                            new_end['id'] = new_end_id
                            new_end['z'] = z
                            self.user_points.append(new_end)
                        
                        # Create new baseline
                        new_base_line = base_line.copy()
                        new_base_line_id = self.next_line_id()
                        new_base_line['id'] = new_base_line_id
                        new_base_line['start_id'] = new_start_id
                        new_base_line['end_id'] = new_end_id
                        self.lines.append(new_base_line)

            # Create new curve
            new_curve = curve.copy()
            new_curve['id'] = self.next_curve_id()
            new_curve['arc_point_ids'] = new_arc_point_ids
            new_curve['arc_points_real'] = new_arc_points_real
            new_curve['z_level'] = z
            new_curve['base_line_id'] = new_base_line_id

            if new_arc_point_ids:
                new_curve['start_id'] = new_arc_point_ids[0]
                new_curve['end_id'] = new_arc_point_ids[-1]
            if new_start_id is not None:
                new_curve['start_id'] = new_start_id
            if new_end_id is not None:
                new_curve['end_id'] = new_end_id
                
            self.curves.append(new_curve)
        self.mark_modified()

    def merge_duplicate_points(self):
        """Merge all points with identical 3D coordinates into the point with lowest ID."""
        from tkinter import messagebox
        
        if not self.user_points:
            messagebox.showinfo("Merge Duplicates", "No points to merge.")
            return
        
        # Build map of (x, y, z) -> list of points with those coordinates
        position_map = {}
        for point in self.user_points:
            # Get integer coordinates for comparison
            x = int(round(point.get('real_x', 0)))
            y = int(round(point.get('z', 0)))
            z = int(round(point.get('real_y', 0)))
            key = (x, y, z)
            
            if key not in position_map:
                position_map[key] = []
            position_map[key].append(point)
        
        # Find duplicate groups (positions with more than one point)
        merge_map = {}  # old_id -> new_id (keeping lowest ID)
        points_to_remove = set()
        merge_count = 0
        
        for position, points in position_map.items():
            if len(points) > 1:
                # Sort by ID to keep the lowest
                points_sorted = sorted(points, key=lambda p: p['id'])
                keeper = points_sorted[0]
                keeper_id = keeper['id']
                
                # Map all other IDs to the keeper
                for i in range(1, len(points_sorted)):
                    dup = points_sorted[i]
                    merge_map[dup['id']] = keeper_id
                    points_to_remove.add(dup['id'])
                    merge_count += 1
        
        if not merge_map:
            messagebox.showinfo("Merge Duplicates", "No duplicate points found.")
            return
        
        # Confirm with user
        total_points = len(self.user_points)
        remaining_points = total_points - merge_count
        
        confirm = messagebox.askyesno(
            "Merge Duplicates",
            f"Found {merge_count} duplicate point(s) to remove.\n\n"
            f"Current points: {total_points}\n"
            f"After merge: {remaining_points}\n\n"
            f"Lines and curves will be updated to reference the merged points.\n\n"
            f"Proceed with merge?"
        )
        
        if not confirm:
            return
        
        # Update all references in lines
        for line in self.lines:
            if line.get('start_id') in merge_map:
                line['start_id'] = merge_map[line['start_id']]
            if line.get('end_id') in merge_map:
                line['end_id'] = merge_map[line['end_id']]
        
        # Update all references in curves
        for curve in self.curves:
            # Update arc_point_ids
            if 'arc_point_ids' in curve:
                curve['arc_point_ids'] = [
                    merge_map.get(pid, pid) for pid in curve['arc_point_ids']
                ]
            # Update start_id and end_id if present
            if 'start_id' in curve and curve['start_id'] in merge_map:
                curve['start_id'] = merge_map[curve['start_id']]
            if 'end_id' in curve and curve['end_id'] in merge_map:
                curve['end_id'] = merge_map[curve['end_id']]
        
        # Remove duplicate points
        self.user_points = [p for p in self.user_points if p['id'] not in points_to_remove]
        
        # Mark as modified and refresh display
        self.mark_modified()
        self.redraw_markers()
        self.refresh_editor_lists()
        self.update_points_label()
        
        messagebox.showinfo(
            "Merge Complete",
            f"Merged {merge_count} duplicate points.\n"
            f"Remaining points: {len(self.user_points)}"
        )
        self.update_status(f"Merged {merge_count} duplicate points")

    def audit_project(self):
        """Audit the project for data consistency issues."""
        issues = []
        
        # 1. Check points for duplicates
        position_map = {}
        duplicate_points_count = 0
        for point in self.user_points:
            # Use same rounding logic as merge
            x = int(round(point.get('real_x', 0)))
            y = int(round(point.get('z', 0)))
            z = int(round(point.get('real_y', 0)))
            key = (x, y, z)
            if key in position_map:
                duplicate_points_count += 1
            else:
                position_map[key] = point['id']
        
        if duplicate_points_count > 0:
            issues.append(f"Found {duplicate_points_count} duplicate points (same X, Y, Z).")

        # 2. Check lines for start and end point on the same z level
        lines_with_z_mismatch = []
        for line in self.lines:
            start = next((p for p in self.user_points if p['id'] == line['start_id']), None)
            end = next((p for p in self.user_points if p['id'] == line['end_id']), None)
            
            if start and end:
                if abs(float(start.get('z', 0)) - float(end.get('z', 0))) > 0.001:
                    lines_with_z_mismatch.append(line['id'])
        
        if lines_with_z_mismatch:
            issues.append(f"Found {len(lines_with_z_mismatch)} lines with start/end Z mismatch (IDs: {', '.join(map(str, lines_with_z_mismatch[:10]))}{'...' if len(lines_with_z_mismatch) > 10 else ''}).")

        # 3. Check curves start, end, line and circumference points all on same level
        curves_with_z_mismatch = []
        for curve in self.curves:
            curve_z = float(curve.get('z_level', curve.get('z', 0)))
            mismatch = False
            
            # Check start point
            if 'start_id' in curve:
                p = next((p for p in self.user_points if p['id'] == curve['start_id']), None)
                if p and abs(float(p.get('z', 0)) - curve_z) > 0.001:
                    mismatch = True
            
            # Check end point
            if 'end_id' in curve:
                p = next((p for p in self.user_points if p['id'] == curve['end_id']), None)
                if p and abs(float(p.get('z', 0)) - curve_z) > 0.001:
                    mismatch = True
            
            # Check arc points
            for pid in curve.get('arc_point_ids', []):
                p = next((p for p in self.user_points if p['id'] == pid), None)
                if p and abs(float(p.get('z', 0)) - curve_z) > 0.001:
                    mismatch = True
            
            # Check base line
            base_line_id = curve.get('base_line_id')
            if base_line_id:
                line = next((l for l in self.lines if l['id'] == base_line_id), None)
                if line:
                    start = next((p for p in self.user_points if p['id'] == line['start_id']), None)
                    end = next((p for p in self.user_points if p['id'] == line['end_id']), None)
                    if start and abs(float(start.get('z', 0)) - curve_z) > 0.001:
                        mismatch = True
                    if end and abs(float(end.get('z', 0)) - curve_z) > 0.001:
                        mismatch = True
            
            if mismatch:
                curves_with_z_mismatch.append(curve['id'])

        if curves_with_z_mismatch:
            issues.append(f"Found {len(curves_with_z_mismatch)} curves with Z level inconsistencies (IDs: {', '.join(map(str, curves_with_z_mismatch[:10]))}{'...' if len(curves_with_z_mismatch) > 10 else ''}).")

        from tkinter import messagebox
        if not issues:
            messagebox.showinfo("Project Audit", "Audit passed! No issues found.")
        else:
            report = "\n\n".join(issues)
            messagebox.showwarning("Project Audit", f"Found the following issues:\n\n{report}")

    def open_line_audit_tool(self):
        if not self.user_points:
            messagebox.showinfo("Line Audit", "Please add points before running the line audit.")
            return

        if self._line_audit_window and self._line_audit_window.winfo_exists():
            try:
                self._line_audit_window.deiconify()
                self._line_audit_window.lift()
                self._line_audit_window.focus_set()
            except Exception:
                pass
            self._refresh_line_audit_point_choices()
            return

        win = tk.Toplevel(self.master)
        win.title("Line Audit")
        win.geometry("620x460")
        # Don't make it transient or modal - let it float freely
        self._line_audit_window = win
        win.protocol("WM_DELETE_WINDOW", self._close_line_audit_window)
        # Keep window on top for easy access
        win.attributes('-topmost', True)

        container = tk.Frame(win, padx=10, pady=10)
        container.pack(fill='both', expand=True)

        header = tk.Label(container, text="Traverse lines/curves from a start point and list all reachable endpoints.", anchor='w')
        header.pack(fill='x', pady=(0, 8))

        start_frame = tk.Frame(container)
        start_frame.pack(fill='x', pady=(0, 6))

        tk.Label(start_frame, text="Start Point ID:").pack(side='left')
        self._line_audit_start_var = tk.StringVar(value=self._line_audit_last_start or "")
        combo = ttk.Combobox(start_frame, textvariable=self._line_audit_start_var, width=12, state='normal')
        combo.pack(side='left', padx=(6, 6))
        self._line_audit_point_combo = combo
        self._refresh_line_audit_point_choices()

        tk.Button(start_frame, text="Use Editor Selection", command=self._line_audit_use_selected_point).pack(side='left')
        tk.Button(start_frame, text="Refresh", command=self._refresh_line_audit_point_choices).pack(side='left', padx=(6, 0))

        button_frame = tk.Frame(container)
        button_frame.pack(fill='x', pady=(0, 10))
        tk.Button(button_frame, text="Run Audit", command=self._run_line_audit_from_ui, bg='#4CAF50', fg='white', width=14).pack(side='left')
        tk.Button(button_frame, text="Clear Highlights", command=self.clear_line_audit_highlights, width=14).pack(side='left', padx=(8, 0))

        results_frame = tk.LabelFrame(container, text="Routes")
        results_frame.pack(fill='both', expand=True)

        columns = ('endpoint', 'route')
        tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=12)
        tree.heading('endpoint', text='Endpoint')
        tree.heading('route', text='Route')
        tree.column('endpoint', width=80, anchor='center')
        tree.column('route', width=440, anchor='w')
        vsb = ttk.Scrollbar(results_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.line_audit_results_tv = tree

        summary = tk.Label(container, text="Run the audit to see reachable endpoints.", anchor='w')
        summary.pack(fill='x', pady=(8, 0))
        self._line_audit_summary_label = summary

        info = tk.Label(
            container,
            text="Routes are highlighted in bright magenta. Click points in 3D view to auto-audit.",
            anchor='w',
            fg='#555555'
        )
        info.pack(fill='x', pady=(4, 0))
        
        # Position window to the right side of the screen for easy access
        try:
            win.update_idletasks()
            screen_width = win.winfo_screenwidth()
            win.geometry(f"+{screen_width - 640}+50")
        except Exception:
            pass

    def _refresh_line_audit_point_choices(self):
        if not self._line_audit_point_combo:
            return
        choices = [
            str(p.get('id'))
            for p in sorted(self.user_points, key=lambda entry: entry.get('id', 0))
            if p.get('id') is not None
        ]
        self._line_audit_point_combo['values'] = choices
        if choices and not (self._line_audit_start_var.get() or "").strip():
            self._line_audit_start_var.set(choices[0])

    def _line_audit_use_selected_point(self):
        if not self.points_tv:
            return
        selection = self.points_tv.selection()
        if not selection:
            messagebox.showinfo("Line Audit", "Select a point in the Editor tab first or enter an ID manually.")
            return
        try:
            pid = int(self.points_tv.item(selection[0], 'values')[0])
        except Exception:
            messagebox.showerror("Line Audit", "Could not determine the selected point ID.")
            return
        if self._line_audit_start_var:
            self._line_audit_start_var.set(str(pid))

    def _run_line_audit_from_ui(self):
        if not self._line_audit_start_var:
            return
        raw_value = (self._line_audit_start_var.get() or "").strip()
        if not raw_value:
            messagebox.showwarning("Line Audit", "Enter a starting point ID.")
            return
        try:
            start_id = int(raw_value)
        except ValueError:
            messagebox.showerror("Line Audit", "Start point ID must be an integer.")
            return

        try:
            result = self.perform_line_audit(start_id)
        except ValueError as exc:
            messagebox.showerror("Line Audit", str(exc))
            return

        self._line_audit_last_start = str(start_id)
        self._populate_line_audit_results(result)

        self._line_audit_highlights = {
            'lines': set(result.get('highlight_lines', set())),
            'curves': set(result.get('highlight_curves', set())),
            'endpoints': set(result.get('unique_endpoints', []))
        }
        try:
            self.update_3d_plot()
        except Exception:
            pass

        routes_count = len(result.get('routes', []))
        endpoints_count = len(result.get('unique_endpoints', []))
        self.update_status(f"Line audit found {endpoints_count} endpoint(s) across {routes_count} route(s).")

    def _populate_line_audit_results(self, result):
        tree = self.line_audit_results_tv
        if not tree:
            return
        for child in tree.get_children():
            tree.delete(child)

        start_id = result.get('start_point')
        routes = result.get('routes', [])
        for idx, route in enumerate(routes, start=1):
            endpoint = route.get('end_point')
            desc = self._format_line_audit_route(start_id, route.get('path', []))
            tree.insert('', 'end', iid=f"route_{idx}", values=(endpoint, desc))

        if self._line_audit_summary_label:
            routes_count = len(routes)
            endpoints_count = len(result.get('unique_endpoints', []))
            self._line_audit_summary_label.config(
                text=f"{routes_count} route(s), {endpoints_count} unique endpoint(s)"
            )

    def _format_line_audit_route(self, start_point_id, path):
        if not path:
            return f"Point {start_point_id} (no outgoing connections)"
        parts = [f"Point {start_point_id}"]
        current = start_point_id
        for edge in path:
            label = "Line" if edge.get('type') == 'line' else 'Curve'
            edge_id = edge.get('id', '?')
            target = edge.get('target')
            parts.append(f"{label} {edge_id} -> Point {target}")
            current = target
        return " -> ".join(parts)

    def _build_line_curve_adjacency(self, valid_point_ids=None):
        adjacency = {}
        for line in self.lines:
            if line.get('hidden', False):
                continue
            start_id = line.get('start_id')
            end_id = line.get('end_id')
            if start_id is None or end_id is None:
                continue
            if valid_point_ids is not None and (start_id not in valid_point_ids or end_id not in valid_point_ids):
                continue
            edge = {'type': 'line', 'id': line.get('id'), 'target': end_id, 'source': start_id}
            adjacency.setdefault(start_id, []).append(edge)

        for curve in self.curves:
            if curve.get('hidden', False):
                continue
            start_id = curve.get('start_id')
            end_id = curve.get('end_id')
            if start_id is None or end_id is None:
                continue
            if valid_point_ids is not None and (start_id not in valid_point_ids or end_id not in valid_point_ids):
                continue
            edge = {'type': 'curve', 'id': curve.get('id'), 'target': end_id, 'source': start_id}
            adjacency.setdefault(start_id, []).append(edge)

        for edges in adjacency.values():
            edges.sort(key=lambda e: (e.get('type'), e.get('id') or 0, e.get('target') or 0))
        return adjacency

    def perform_line_audit(self, start_point_id):
        if not self.user_points:
            raise ValueError("No points available to audit.")

        try:
            start_point_id = int(start_point_id)
        except (TypeError, ValueError):
            raise ValueError("Start point ID must be an integer.")

        valid_point_ids = {
            p.get('id') for p in self.user_points if p.get('id') is not None
        }
        if start_point_id not in valid_point_ids:
            raise ValueError(f"Point {start_point_id} does not exist.")

        adjacency = self._build_line_curve_adjacency(valid_point_ids)

        routes = []

        def dfs(current_point, path, visited):
            neighbors = adjacency.get(current_point, [])
            advanced = False
            for edge in neighbors:
                target = edge.get('target')
                if target is None or target in visited:
                    continue
                advanced = True
                path.append(edge)
                visited.add(target)
                dfs(target, path, visited)
                visited.remove(target)
                path.pop()
            if not advanced:
                routes.append({'end_point': current_point, 'path': list(path)})

        dfs(start_point_id, [], {start_point_id})

        highlight_lines = set()
        highlight_curves = set()
        unique_endpoints = set()
        for route in routes:
            unique_endpoints.add(route.get('end_point'))
            for edge in route.get('path', []):
                if edge.get('type') == 'line' and edge.get('id') is not None:
                    highlight_lines.add(edge['id'])
                elif edge.get('type') == 'curve' and edge.get('id') is not None:
                    highlight_curves.add(edge['id'])

        return {
            'start_point': start_point_id,
            'routes': routes,
            'unique_endpoints': sorted(unique_endpoints),
            'highlight_lines': highlight_lines,
            'highlight_curves': highlight_curves
        }

    def clear_line_audit_highlights(self, silent=False):
        self._line_audit_highlights = {'lines': set(), 'curves': set(), 'endpoints': set()}
        try:
            self.update_3d_plot()
        except Exception:
            pass
        if not silent:
            self.update_status("Line audit highlights cleared.")

    def _close_line_audit_window(self):
        try:
            if self._line_audit_window:
                self._line_audit_window.destroy()
        finally:
            self._line_audit_window = None
            self._line_audit_start_var = None
            self._line_audit_point_combo = None
            self.line_audit_results_tv = None
            self._line_audit_summary_label = None
            self.clear_line_audit_highlights(silent=True)


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


    def on_exit(self):
        """Handle application exit with save confirmation and backup cleanup."""
        # Only ask to save if project has been modified
        if self._modified:
            answer = messagebox.askyesnocancel(
                "Save Project?",
                "Do you want to save the project before exiting?",
                icon='question'
            )
            
            if answer is None:  # Cancel
                return
            
            if answer:  # Yes - save project
                self.save_project()
        
        # Always clean up backup file on exit
        if self._current_backup_file and os.path.exists(self._current_backup_file):
            try:
                os.remove(self._current_backup_file)
                print(f"Deleted backup: {self._current_backup_file}")
            except Exception as e:
                print(f"Could not delete backup file: {e}")
        
        self.master.destroy()

    def mark_modified(self):
        """Mark the project as modified (has unsaved changes)."""
        self._modified = True

    def clean_old_backups(self):
        """Show dialog to clean up accumulated .dig.bak.* files."""
        import glob
        from datetime import datetime
        
        # Find all backup files in the project directory
        backup_pattern = os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.dig.bak.*")
        backup_files = glob.glob(backup_pattern)
        
        if not backup_files:
            messagebox.showinfo("No Backups", "No backup files found in the project directory.")
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Clean Old Backups")
        dialog.geometry("700x400")
        dialog.transient(self.master)
        
        tk.Label(dialog, text="Select backup files to delete:", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Frame for listbox and scrollbar
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        listbox = tk.Listbox(list_frame, selectmode='multiple', yscrollcommand=scrollbar.set, font=('Courier', 9))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate listbox with file info
        file_data = []
        for backup_file in sorted(backup_files):
            try:
                stat_info = os.stat(backup_file)
                size_kb = stat_info.st_size / 1024
                mtime = datetime.fromtimestamp(stat_info.st_mtime)
                filename = os.path.basename(backup_file)
                display_text = f"{filename:<50} {size_kb:>8.1f} KB  {mtime.strftime('%Y-%m-%d %H:%M:%S')}"
                listbox.insert('end', display_text)
                file_data.append(backup_file)
            except Exception as e:
                print(f"Error reading {backup_file}: {e}")
        
        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def select_all():
            listbox.select_set(0, 'end')
        
        def delete_selected():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("No Selection", "Please select at least one backup file to delete.")
                return
            
            selected_files = [file_data[i] for i in selected_indices]
            count = len(selected_files)
            
            answer = messagebox.askyesno(
                "Confirm Deletion",
                f"Delete {count} backup file(s)?\n\nThis action cannot be undone.",
                icon='warning'
            )
            
            if answer:
                deleted_count = 0
                errors = []
                for backup_file in selected_files:
                    try:
                        os.remove(backup_file)
                        deleted_count += 1
                    except Exception as e:
                        errors.append(f"{os.path.basename(backup_file)}: {e}")
                
                # Refresh the list
                listbox.delete(0, 'end')
                file_data.clear()
                
                remaining_backups = glob.glob(backup_pattern)
                for backup_file in sorted(remaining_backups):
                    try:
                        stat_info = os.stat(backup_file)
                        size_kb = stat_info.st_size / 1024
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        filename = os.path.basename(backup_file)
                        display_text = f"{filename:<50} {size_kb:>8.1f} KB  {mtime.strftime('%Y-%m-%d %H:%M:%S')}"
                        listbox.insert('end', display_text)
                        file_data.append(backup_file)
                    except Exception as e:
                        print(f"Error reading {backup_file}: {e}")
                
                # Show result
                result_msg = f"Successfully deleted {deleted_count} backup file(s)."
                if errors:
                    result_msg += f"\n\nErrors:\n" + "\n".join(errors)
                
                messagebox.showinfo("Cleanup Complete", result_msg)
                
                if not remaining_backups:
                    dialog.destroy()
        
        tk.Button(button_frame, text="Select All", command=select_all, width=15).pack(side='left', padx=5)
        tk.Button(button_frame, text="Delete Selected", command=delete_selected, bg='#ff6666', fg='white', width=15).pack(side='left', padx=5)
        tk.Button(button_frame, text="Close", command=dialog.destroy, width=15).pack(side='left', padx=5)
        
        dialog.grab_set()

    def run(self):
        self.master.mainloop()