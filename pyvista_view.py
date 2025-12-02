"""
PyVista-based 3D visualization for the digitizer application.
"""
import tkinter as tk
try:
    import pyvista as pv
    from pyvistaqt import BackgroundPlotter
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False
    print("PyVista not available. Install with: pip install pyvista pyvistaqt")


class PyVistaViewMixin:
    """Mixin to add PyVista 3D view to the digitizer application."""
    
    def _init_pyvista_tab(self):
        """Initialize the PyVista 3D view tab."""
        if not PYVISTA_AVAILABLE:
            # Create placeholder frame
            self.pyvista_frame = tk.Frame(self.notebook)
            self.notebook.add(self.pyvista_frame, text="PyVista 3D (Not Available)")
            label = tk.Label(
                self.pyvista_frame,
                text="PyVista is not installed.\n\nInstall with:\npip install pyvista pyvistaqt",
                font=("Arial", 12),
                fg="red"
            )
            label.pack(expand=True)
            self._pyvista_initialized = False
            return
        
        # Create PyVista frame
        self.pyvista_frame = tk.Frame(self.notebook)
        self.notebook.add(self.pyvista_frame, text="PyVista 3D")
        
        # Toolbar at top
        self._pyvista_toolbar = tk.Frame(self.pyvista_frame, bg='lightgrey', padx=5, pady=5)
        self._pyvista_toolbar.pack(side='top', fill='x')
        
        # Initialize/Refresh button
        tk.Button(self._pyvista_toolbar, text='Initialize View', command=self._create_pyvista_plotter, 
                  bg='#4CAF50', fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=2)
        tk.Button(self._pyvista_toolbar, text='Refresh', command=self.update_pyvista_plot).pack(side='left', padx=2)
        
        tk.Button(self._pyvista_toolbar, text='Reset View', command=self.reset_pyvista_view).pack(side='left', padx=2)
        tk.Button(self._pyvista_toolbar, text='Top View', command=lambda: self.set_pyvista_view('xy')).pack(side='left', padx=2)
        tk.Button(self._pyvista_toolbar, text='Front View', command=lambda: self.set_pyvista_view('xz')).pack(side='left', padx=2)
        tk.Button(self._pyvista_toolbar, text='Side View', command=lambda: self.set_pyvista_view('yz')).pack(side='left', padx=2)
        tk.Button(self._pyvista_toolbar, text='Isometric', command=lambda: self.set_pyvista_view('iso')).pack(side='left', padx=2)
        
        tk.Label(self._pyvista_toolbar, text='  |  Point Size:', bg='lightgrey').pack(side='left', padx=(10, 2))
        tk.Button(self._pyvista_toolbar, text='-', command=self.decrease_pyvista_point_size, width=2).pack(side='left')
        tk.Button(self._pyvista_toolbar, text='+', command=self.increase_pyvista_point_size, width=2).pack(side='left')
        
        tk.Label(self._pyvista_toolbar, text='  Line Width:', bg='lightgrey').pack(side='left', padx=(10, 2))
        tk.Button(self._pyvista_toolbar, text='-', command=self.decrease_pyvista_line_width, width=2).pack(side='left')
        tk.Button(self._pyvista_toolbar, text='+', command=self.increase_pyvista_line_width, width=2).pack(side='left')
        
        # Initialize settings (plotter created on demand)
        self._pyvista_point_size = 8
        self._pyvista_line_width = 3
        self._pyvista_actors = {}  # Track actors for updates
        self._pyvista_plotter = None
        self._pyvista_initialized = False
        
        # Message prompting user to click Initialize
        msg_frame = tk.Frame(self.pyvista_frame)
        msg_frame.pack(expand=True, fill='both')
        tk.Label(msg_frame, text="Click 'Initialize View' to open PyVista 3D viewer in a separate window",
                 font=('Arial', 12), wraplength=400, justify='center').pack(expand=True)
        tk.Label(msg_frame, text="(The viewer will open as a standalone window with its own controls)",
                 font=('Arial', 9), fg='gray').pack()
    
    def _create_pyvista_plotter(self):
        """Create the PyVista plotter on demand."""
        if self._pyvista_initialized and self._pyvista_plotter is not None:
            # Already initialized, just refresh
            self.update_pyvista_plot()
            return
        
        try:
            print("Creating PyVista plotter in separate window...")
            # Create BackgroundPlotter in separate window (not embedded)
            # Pass None for app to let it create its own Qt application
            self._pyvista_plotter = BackgroundPlotter(
                window_size=(1000, 700),  # Must be tuple, not list
                title='PyVista 3D View',
                app=None,  # Let it create its own Qt app
                toolbar=True
            )
            
            # Configure plotter
            self._pyvista_plotter.set_background('white')
            self._pyvista_plotter.add_axes()
            
            # Enable point picking with LEFT click (not right click)
            # Use picker='point' for better point selection
            # We'll store the picked point index via the picker's result
            def pick_callback(point):
                if point is not None:
                    print(f"Picked point at: {point}")
                    # Access the picker to get the point index directly
                    picker = self._pyvista_plotter.iren.picker
                    if hasattr(picker, 'GetPointId') and picker.GetPointId() >= 0:
                        point_idx = picker.GetPointId()
                        print(f"Picked mesh point index: {point_idx}")
                        self._on_pyvista_pick(point, point_idx)
                    else:
                        self._on_pyvista_pick(point, None)
            
            self._pyvista_plotter.enable_point_picking(
                callback=pick_callback,
                show_message=False,  # Disable popup messages
                show_point=True,
                point_size=20,  # Larger visual feedback
                color='lime',
                tolerance=0.025,  # Tighter tolerance for more precise picking
                picker='point',  # Use point picker instead of cell picker
                use_picker=True,
                left_clicking=True  # Enable left click picking
            )
            
            self._pyvista_initialized = True
            print("PyVista plotter created successfully in separate window")
            
            # Initial plot
            self.update_pyvista_plot()
                
        except Exception as e:
            print(f"Failed to create PyVista plotter: {e}")
            import traceback
            traceback.print_exc()
            self._pyvista_plotter = None
            self._pyvista_initialized = False
    

    
    def _on_pyvista_pick(self, picked_point, point_idx=None):
        """Handle point picking in PyVista view.
        
        Args:
            picked_point: The 3D coordinates of the picked point
            point_idx: The mesh point index (if available from picker)
        """
        if picked_point is None:
            return
        
        # Get the visible points list (same as used in rendering)
        visible_points = [p for p in self.user_points if not p.get('hidden', False)]
        
        nearest_point = None
        
        # If we have the exact mesh point index, use it directly
        if point_idx is not None and 0 <= point_idx < len(visible_points):
            nearest_point = visible_points[point_idx]
            print(f"Using mesh index {point_idx} -> point ID {nearest_point.get('id')}")
        else:
            # Fallback: Find nearest user point to the picked location
            min_dist = float('inf')
            
            for point in visible_points:
                px = point.get('real_x', point.get('pdf_x', 0))
                py = -(point.get('real_y', point.get('pdf_y', 0)))
                pz = float(point.get('z', 0))
                
                dist = ((px - picked_point[0])**2 + 
                       (py - picked_point[1])**2 + 
                       (pz - picked_point[2])**2)**0.5
                
                if dist < min_dist:
                    min_dist = dist
                    nearest_point = point
            
            if nearest_point:
                print(f"Fallback search found point ID {nearest_point.get('id')} at distance {min_dist:.2f}")
        
        if nearest_point:
            self._3d_selected_point_id = nearest_point.get('id')
            
            # If line audit window is open, auto-run audit
            if self._line_audit_window and self._line_audit_window.winfo_exists():
                if self._line_audit_start_var:
                    self._line_audit_start_var.set(str(self._3d_selected_point_id))
                    try:
                        self._run_line_audit_from_ui()
                    except Exception as e:
                        print(f"Auto-run audit failed: {e}")
            
            self.update_status(f"Selected point {self._3d_selected_point_id} in PyVista view")
            self.update_pyvista_plot()

    
    def update_pyvista_plot(self):
        """Update the PyVista 3D visualization."""
        if not PYVISTA_AVAILABLE:
            return
        
        # Don't auto-create plotter - only update if already created
        if not self._pyvista_initialized or self._pyvista_plotter is None:
            return
        
        # Check if plotter window was closed
        try:
            # Try to access the plotter - if closed, this will fail
            if hasattr(self._pyvista_plotter, 'ren_win') and self._pyvista_plotter.ren_win is None:
                # Window was closed, reset state
                self._pyvista_initialized = False
                self._pyvista_plotter = None
                print("PyVista window was closed, reinitialize to reopen")
                return
        except Exception:
            # Window was closed or is invalid
            self._pyvista_initialized = False
            self._pyvista_plotter = None
            print("PyVista window is no longer valid, reinitialize to reopen")
            return
        
        try:
            print(f"Updating PyVista plot with {len(self.user_points)} points, {len(self.lines)} lines, {len(self.curves)} curves")
            plotter = self._pyvista_plotter
            
            # Clear existing actors - use clear() instead of clear_actors()
            plotter.clear()
            
            # Re-add axes after clearing
            plotter.add_axes()
            
            # Get highlight info
            highlight_info = getattr(self, '_line_audit_highlights', None) or {}
            highlight_line_ids = set(highlight_info.get('lines', set()))
            highlight_curve_ids = set(highlight_info.get('curves', set()))
            highlight_endpoints = set(highlight_info.get('endpoints', set()))
            selected_point_id = getattr(self, '_3d_selected_point_id', None)
            
            # Plot points
            visible_points = [p for p in self.user_points if not p.get('hidden', False)]
            if visible_points:
                points_coords = []
                point_colors = []
                point_sizes = []
                
                for point in visible_points:
                    px = point.get('real_x', point.get('pdf_x', 0))
                    py = -(point.get('real_y', point.get('pdf_y', 0)))
                    pz = float(point.get('z', 0))
                    points_coords.append([px, py, pz])
                
                # Create point cloud with per-point colors
                point_cloud = pv.PolyData(points_coords)
                
                # Assign colors efficiently
                colors_rgb = []
                for point in visible_points:
                    pid = point.get('id')
                    if pid == selected_point_id:
                        colors_rgb.append([0, 255, 0])  # lime
                    elif pid in highlight_endpoints:
                        colors_rgb.append([255, 0, 255])  # magenta
                    else:
                        colors_rgb.append([0, 0, 255])  # blue
                
                point_cloud['colors'] = colors_rgb
                
                plotter.add_points(
                    point_cloud,
                    scalars='colors',
                    rgb=True,
                    point_size=self._pyvista_point_size,
                    render_points_as_spheres=False  # Much faster
                )
                
                # Add labels ONLY for selected and highlighted points
                labels_coords = []
                labels_text = []
                for i, point in enumerate(visible_points):
                    pid = point.get('id')
                    if pid and (pid == selected_point_id or pid in highlight_endpoints):
                        labels_coords.append(points_coords[i])
                        labels_text.append(str(pid))
                
                if labels_coords:
                    plotter.add_point_labels(
                        labels_coords,
                        labels_text,
                        font_size=10,
                        text_color='black',
                        point_size=0,
                        shape_opacity=0.7,
                        fill_shape=True,
                        margin=3
                    )
            
            # Plot lines
            for line in self.lines:
                if line.get('hidden', False):
                    continue
                
                try:
                    start = next(p for p in self.user_points if p['id'] == line['start_id'])
                    end = next(p for p in self.user_points if p['id'] == line['end_id'])
                    
                    sx = start.get('real_x', start.get('pdf_x', 0))
                    sy = -(start.get('real_y', start.get('pdf_y', 0)))
                    sz = float(start.get('z', 0))
                    
                    ex = end.get('real_x', end.get('pdf_x', 0))
                    ey = -(end.get('real_y', end.get('pdf_y', 0)))
                    ez = float(end.get('z', 0))
                    
                    line_points = [[sx, sy, sz], [ex, ey, ez]]
                    line_poly = pv.Line(*line_points)
                    
                    is_highlighted = line.get('id') in highlight_line_ids
                    color = 'magenta' if is_highlighted else 'orange'
                    width = self._pyvista_line_width * 2 if is_highlighted else self._pyvista_line_width
                    
                    plotter.add_mesh(line_poly, color=color, line_width=width)
                except (StopIteration, KeyError):
                    continue
            
            # Plot curves
            for curve in self.curves:
                if curve.get('hidden', False):
                    continue
                
                pts = []
                if curve.get('arc_points_real'):
                    arc = curve['arc_points_real']
                    if all(len(t) > 2 for t in arc):
                        pts = [[t[0], -t[1], float(t[2])] for t in arc]
                    else:
                        ids = curve.get('arc_point_ids', [])
                        for i, t in enumerate(arc):
                            x, y = t[0], t[1]
                            z = None
                            if i < len(ids):
                                pid = ids[i]
                                p = next((u for u in self.user_points if u['id'] == pid), None)
                                if p:
                                    z = float(p.get('z', 0))
                            if z is None:
                                z = float(curve.get('z_level', curve.get('z', 0)))
                            pts.append([x, -y, z])
                else:
                    for pid in curve.get('arc_point_ids', []):
                        p = next((u for u in self.user_points if u['id'] == pid), None)
                        if p:
                            pts.append([
                                p.get('real_x', p.get('pdf_x')),
                                -(p.get('real_y', p.get('pdf_y'))),
                                float(p.get('z', 0))
                            ])
                
                if len(pts) > 1:
                    curve_line = pv.Spline(pts, n_points=len(pts) * 3)
                    
                    is_highlighted = curve.get('id') in highlight_curve_ids
                    color = 'magenta' if is_highlighted else 'purple'
                    width = self._pyvista_line_width * 2 if is_highlighted else self._pyvista_line_width
                    
                    plotter.add_mesh(curve_line, color=color, line_width=width)
            
            # Highlight selected point with label only (already colored in point cloud)
            if selected_point_id:
                selected_pt = next((p for p in self.user_points if p.get('id') == selected_point_id), None)
                if selected_pt and not selected_pt.get('hidden', False):
                    sx = selected_pt.get('real_x', selected_pt.get('pdf_x', 0))
                    sy = -(selected_pt.get('real_y', selected_pt.get('pdf_y', 0)))
                    sz = float(selected_pt.get('z', 0))
                    
                    plotter.add_point_labels(
                        [[sx, sy, sz + 0.02]],
                        [f"Selected: {selected_point_id}"],
                        font_size=12,
                        text_color='green',
                        point_size=0,
                        bold=True
                    )
            
            # Reset camera to fit all data
            plotter.reset_camera()
            print("PyVista plot updated successfully")
        except Exception as e:
            print(f"PyVista plot update error: {e}")
            import traceback
            traceback.print_exc()
    
    def reset_pyvista_view(self):
        """Reset PyVista camera to default view."""
        if self._pyvista_plotter:
            self._pyvista_plotter.reset_camera()
            self._pyvista_plotter.view_isometric()
    
    def set_pyvista_view(self, view_type):
        """Set PyVista camera to a specific view."""
        if not self._pyvista_plotter:
            return
        
        if view_type == 'xy':
            self._pyvista_plotter.view_xy()
        elif view_type == 'xz':
            self._pyvista_plotter.view_xz()
        elif view_type == 'yz':
            self._pyvista_plotter.view_yz()
        elif view_type == 'iso':
            self._pyvista_plotter.view_isometric()
    
    def increase_pyvista_point_size(self):
        """Increase point size in PyVista view."""
        self._pyvista_point_size = min(50, self._pyvista_point_size + 2)
        self.update_pyvista_plot()
    
    def decrease_pyvista_point_size(self):
        """Decrease point size in PyVista view."""
        self._pyvista_point_size = max(2, self._pyvista_point_size - 2)
        self.update_pyvista_plot()
    
    def increase_pyvista_line_width(self):
        """Increase line width in PyVista view."""
        self._pyvista_line_width = min(20, self._pyvista_line_width + 1)
        self.update_pyvista_plot()
    
    def decrease_pyvista_line_width(self):
        """Decrease line width in PyVista view."""
        self._pyvista_line_width = max(1, self._pyvista_line_width - 1)
        self.update_pyvista_plot()
