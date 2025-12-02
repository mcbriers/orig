"""
3D viewer widget using VTK for visualizing track layouts.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu
from PyQt6.QtCore import pyqtSignal, QPoint
from PyQt6.QtGui import QCursor

try:
    import vtk
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    VTK_AVAILABLE = True
except ImportError:
    VTK_AVAILABLE = False
    print("VTK not available. 3D view will be disabled.")


class Viewer3D(QWidget):
    """3D visualization widget using VTK."""
    
    # Signals
    point_selected = pyqtSignal(int)  # point_id
    point_identify_requested = pyqtSignal(int)  # point_id
    point_duplicate_requested = pyqtSignal(int)  # point_id
    point_delete_requested = pyqtSignal(int)  # point_id
    line_identify_requested = pyqtSignal(int)  # line_id
    line_duplicate_requested = pyqtSignal(int)  # line_id
    line_delete_requested = pyqtSignal(int)  # line_id
    line_trace_requested = pyqtSignal(int)  # line_id
    line_reverse_requested = pyqtSignal(int)  # line_id
    curve_identify_requested = pyqtSignal(int)  # curve_id
    curve_duplicate_requested = pyqtSignal(int)  # curve_id
    curve_delete_requested = pyqtSignal(int)  # curve_id
    curve_reverse_requested = pyqtSignal(int)  # curve_id
    
    line_create_requested = pyqtSignal(int, int)  # start_point_id, end_point_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.project = None
        self.vtk_available = VTK_AVAILABLE
        self.z_scale = 1.0  # Scale factor for Z axis to make it more visible
        self.center_x = 0.0  # Center offset for X
        self.center_y = 0.0  # Center offset for Y
        
        # Highlighted items (for trace visualization)
        self.highlighted_points = set()
        self.highlighted_lines = set()
        self.highlighted_curves = set()
        
        # Track if camera has been initialized
        self._camera_initialized = False
        
        # Line drawing mode
        self.line_start_point_id = None  # Point ID where line drawing started
        
        # Render settings (RGB 0-255)
        self.point_color = (51, 102, 255)  # Blue
        self.point_radius = 50.0
        self.line_color = (51, 204, 51)  # Green
        self.line_radius = 20.0
        self.curve_color = (204, 51, 204)  # Magenta
        self.curve_radius = 20.0
        
        if self.vtk_available:
            self._setup_vtk_ui()
        else:
            self._setup_fallback_ui()
    
    def _setup_vtk_ui(self):
        """Set up VTK-based 3D viewer."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_camera)
        toolbar.addWidget(reset_btn)
        
        top_btn = QPushButton("Top View")
        top_btn.clicked.connect(lambda: self.set_view('top'))
        toolbar.addWidget(top_btn)
        
        side_btn = QPushButton("Side View")
        side_btn.clicked.connect(lambda: self.set_view('side'))
        toolbar.addWidget(side_btn)
        
        front_btn = QPushButton("Front View")
        front_btn.clicked.connect(lambda: self.set_view('front'))
        toolbar.addWidget(front_btn)
        
        toolbar.addStretch()
        
        self.z_scale_label = QLabel(f"Z Scale: {self.z_scale}x")
        toolbar.addWidget(self.z_scale_label)
        
        z_up_btn = QPushButton("Z +")
        z_up_btn.clicked.connect(lambda: self.adjust_z_scale(2.0))
        toolbar.addWidget(z_up_btn)
        
        z_down_btn = QPushButton("Z -")
        z_down_btn.clicked.connect(lambda: self.adjust_z_scale(0.5))
        toolbar.addWidget(z_down_btn)
        
        toolbar.addStretch()
        
        self.info_label = QLabel("Points: 0 | Lines: 0 | Curves: 0")
        toolbar.addWidget(self.info_label)
        
        layout.addLayout(toolbar)
        
        # VTK widget
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self.vtk_widget)
        
        # VTK setup
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.1, 0.1, 0.15)  # Dark blue background
        
        self.render_window = self.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        
        self.interactor = self.render_window.GetInteractor()
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
        
        # Setup picker for context menu
        self.picker = vtk.vtkPropPicker()
        self.interactor.SetPicker(self.picker)
        
        # Connect right-click event
        self.interactor.AddObserver("RightButtonPressEvent", self._on_right_click)
        
        # Track if we're in context menu mode
        self._in_context_menu = False
        
        # Actors storage
        self.point_actors = []
        self.line_actors = []
        self.curve_actors = []
        
        # Maps to track which actor belongs to which ID
        self.actor_to_point_id = {}
        self.actor_to_line_id = {}
        self.actor_to_curve_id = {}
        
        # Don't add axes - removed for cleaner view
        # self._add_axes()
        
        # Initialize interactor (but don't call Start() - it conflicts with Qt event loop)
        self.interactor.Initialize()
    
    def _setup_fallback_ui(self):
        """Set up fallback UI when VTK is not available."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        label = QLabel(
            "3D View - VTK not available\n\n"
            "To enable 3D visualization, install VTK:\n"
            "pip install vtk\n\n"
            "VTK provides interactive 3D rendering of your track layout."
        )
        label.setStyleSheet("QLabel { padding: 40px; }")
        layout.addWidget(label)
    
    def _add_axes(self):
        """Add coordinate axes to the scene."""
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(1000, 1000, 1000)  # Larger axes for scale
        axes.SetShaftTypeToCylinder()
        axes.SetCylinderRadius(0.02)
        
        self.renderer.AddActor(axes)
    
    def set_project(self, project):
        """Set the project to visualize."""
        if not self.vtk_available:
            return
        
        self.project = project
        self.update_view()
    
    def update_view(self):
        """Update the 3D view with current project data."""
        if not self.vtk_available or not self.project:
            return
        
        # Calculate center point from all visible points
        visible_points = [p for p in self.project.points if not p.hidden]
        if visible_points:
            self.center_x = sum(p.real_x for p in visible_points) / len(visible_points)
            self.center_y = sum(p.real_y for p in visible_points) / len(visible_points)
        else:
            self.center_x = 0.0
            self.center_y = 0.0
        
        # Clear existing actors
        for actor in self.point_actors + self.line_actors + self.curve_actors:
            self.renderer.RemoveActor(actor)
        
        self.point_actors.clear()
        self.line_actors.clear()
        self.curve_actors.clear()
        self.actor_to_point_id.clear()
        self.actor_to_line_id.clear()
        self.actor_to_curve_id.clear()
        
        # Add points
        for point in self.project.points:
            if not point.hidden:
                actor = self._create_point_actor(point)
                self.renderer.AddActor(actor)
                self.point_actors.append(actor)
                self.actor_to_point_id[actor] = point.id
        
        # Add lines
        for line in self.project.lines:
            if not line.hidden:
                start = self.project.get_point(line.start_id)
                end = self.project.get_point(line.end_id)
                if start and end:
                    line_actor, arrow_actor = self._create_line_actor(start, end, line.id)
                    self.renderer.AddActor(line_actor)
                    self.line_actors.append(line_actor)
                    self.actor_to_line_id[line_actor] = line.id
                    if arrow_actor:
                        self.renderer.AddActor(arrow_actor)
                        self.line_actors.append(arrow_actor)
                        self.actor_to_line_id[arrow_actor] = line.id
        
        # Skip curves - only render base lines and points
        # Curves are not added to the 3D view
        
        # Update info label
        self.info_label.setText(
            f"Points: {len(self.point_actors)} | "
            f"Lines: {len(self.line_actors)} | "
            f"Curves: {len(self.curve_actors)}"
        )
        
        # Reset camera only on first load
        if not self._camera_initialized:
            self.renderer.ResetCamera()
            self._camera_initialized = True
        
        # Render the scene
        self.render_window.Render()
    
    def set_highlighted(self, points=None, lines=None, curves=None):
        """Set highlighted items for trace visualization.
        
        Args:
            points: Set or list of point IDs to highlight
            lines: Set or list of line IDs to highlight
            curves: Set or list of curve IDs to highlight (not rendered in 3D view)
        """
        self.highlighted_points = set(points) if points else set()
        self.highlighted_lines = set(lines) if lines else set()
        self.highlighted_curves = set(curves) if curves else set()
        
        # Refresh the view to show highlighted items
        self.update_view()
    
    def clear_highlighted(self):
        """Clear all highlighted items."""
        self.highlighted_points.clear()
        self.highlighted_lines.clear()
        self.highlighted_curves.clear()
        
        # Refresh the view
        self.update_view()
    
    def _create_point_actor(self, point):
        """Create a VTK actor for a point."""
        # Determine if this point is highlighted
        is_highlighted = point.id in self.highlighted_points
        
        # Create sphere for point with centered coordinates and scaled Z
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(
            point.real_x - self.center_x,
            -(point.real_y - self.center_y),
            point.z * self.z_scale
        )
        # Use larger radius for highlighted points
        sphere.SetRadius(self.point_radius * 1.5 if is_highlighted else self.point_radius)
        sphere.SetThetaResolution(16)
        sphere.SetPhiResolution(16)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # Use orange for highlighted, normal color otherwise
        if is_highlighted:
            color = (255 / 255.0, 165 / 255.0, 0 / 255.0)  # Orange
        else:
            color = (self.point_color[0] / 255.0,
                     self.point_color[1] / 255.0,
                     self.point_color[2] / 255.0)
        actor.GetProperty().SetColor(*color)
        
        return actor
    
    def _create_line_actor(self, start_point, end_point, line_id=None):
        """Create a VTK actor for a line with an arrowhead showing direction."""
        # Determine if this line is highlighted
        is_highlighted = line_id and line_id in self.highlighted_lines
        
        # Transform coordinates
        p1 = (start_point.real_x - self.center_x,
              -(start_point.real_y - self.center_y),
              start_point.z * self.z_scale)
        p2 = (end_point.real_x - self.center_x,
              -(end_point.real_y - self.center_y),
              end_point.z * self.z_scale)
        
        # Create line with centered coordinates and scaled Z
        line = vtk.vtkLineSource()
        line.SetPoint1(*p1)
        line.SetPoint2(*p2)
        
        # Create tube for better visibility
        tube = vtk.vtkTubeFilter()
        tube.SetInputConnection(line.GetOutputPort())
        # Use thicker tube for highlighted lines
        tube.SetRadius(self.line_radius * 1.5 if is_highlighted else self.line_radius)
        tube.SetNumberOfSides(12)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube.GetOutputPort())
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # Use orange for highlighted, green otherwise
        if is_highlighted:
            color = (255 / 255.0, 165 / 255.0, 0 / 255.0)  # Orange
        else:
            color = (self.line_color[0] / 255.0,
                     self.line_color[1] / 255.0,
                     self.line_color[2] / 255.0)
        actor.GetProperty().SetColor(*color)
        
        # Create arrowhead at endpoint
        import math
        
        # Calculate direction vector
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        length = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if length > 0:
            # Normalize direction
            dx /= length
            dy /= length
            dz /= length
            
            # Create cone for arrowhead
            arrow = vtk.vtkConeSource()
            arrow.SetResolution(12)
            arrow_height = self.line_radius * 8
            arrow_radius = self.line_radius * 3
            arrow.SetHeight(arrow_height)
            arrow.SetRadius(arrow_radius)
            arrow.SetDirection(dx, dy, dz)
            
            # Position at endpoint
            arrow.SetCenter(p2[0], p2[1], p2[2])
            
            arrow_mapper = vtk.vtkPolyDataMapper()
            arrow_mapper.SetInputConnection(arrow.GetOutputPort())
            
            arrow_actor = vtk.vtkActor()
            arrow_actor.SetMapper(arrow_mapper)
            arrow_actor.GetProperty().SetColor(*color)
            
            return (actor, arrow_actor)
        
        return (actor, None)
    
    def _create_curve_actor(self, curve):
        """Create a VTK actor for a curve (polyline through arc points)."""
        # Create points with centered coordinates and scaled Z
        points = vtk.vtkPoints()
        for x, y, z in curve.arc_points_real:
            points.InsertNextPoint(
                x - self.center_x,
                y - self.center_y,
                z * self.z_scale
            )
        
        # Create polyline
        polyline = vtk.vtkPolyLine()
        polyline.GetPointIds().SetNumberOfIds(len(curve.arc_points_real))
        for i in range(len(curve.arc_points_real)):
            polyline.GetPointIds().SetId(i, i)
        
        # Create cell array
        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polyline)
        
        # Create polydata
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(cells)
        
        # Create tube for better visibility
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(polydata)
        tube.SetRadius(self.curve_radius)
        tube.SetNumberOfSides(12)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube.GetOutputPort())
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # Convert RGB 0-255 to 0-1 for VTK
        actor.GetProperty().SetColor(
            self.curve_color[0] / 255.0,
            self.curve_color[1] / 255.0,
            self.curve_color[2] / 255.0
        )
        
        return actor
    
    def set_render_settings(self, point_color=None, point_radius=None, 
                           line_color=None, line_radius=None,
                           curve_color=None, curve_radius=None):
        """Update render settings and refresh view."""
        if not self.vtk_available:
            return
        
        if point_color is not None:
            self.point_color = point_color
        if point_radius is not None:
            self.point_radius = point_radius
        if line_color is not None:
            self.line_color = line_color
        if line_radius is not None:
            self.line_radius = line_radius
        if curve_color is not None:
            self.curve_color = curve_color
        if curve_radius is not None:
            self.curve_radius = curve_radius
        
        # Refresh view to apply new settings
        self.update_view()
    
    def adjust_z_scale(self, factor):
        """Adjust Z scale by multiplying by factor."""
        if not self.vtk_available:
            return
        
        self.z_scale *= factor
        self.z_scale = max(1.0, min(1000.0, self.z_scale))  # Clamp between 1 and 1000
        self.z_scale_label.setText(f"Z Scale: {self.z_scale:.1f}x")
        self.update_view()
    
    def reset_camera(self):
        """Reset camera to show all objects."""
        if not self.vtk_available:
            return
        
        self.renderer.ResetCamera()
        self.render_window.Render()
    
    def set_view(self, view_type):
        """Set predefined camera view."""
        if not self.vtk_available:
            return
        
        camera = self.renderer.GetActiveCamera()
        
        # Get center of scene
        self.renderer.ComputeVisiblePropBounds()
        bounds = self.renderer.ComputeVisiblePropBounds()
        
        # Calculate center and size of scene
        center_x = (bounds[0] + bounds[1]) / 2
        center_y = (bounds[2] + bounds[3]) / 2
        center_z = (bounds[4] + bounds[5]) / 2
        
        # Calculate distance based on scene size
        size_x = abs(bounds[1] - bounds[0])
        size_y = abs(bounds[3] - bounds[2])
        size_z = abs(bounds[5] - bounds[4])
        distance = max(size_x, size_y, size_z) * 1.5
        
        if view_type == 'top':
            camera.SetPosition(center_x, center_y, center_z + distance)
            camera.SetViewUp(0, 1, 0)
        elif view_type == 'side':
            camera.SetPosition(center_x + distance, center_y, center_z)
            camera.SetViewUp(0, 0, 1)
        elif view_type == 'front':
            camera.SetPosition(center_x, center_y + distance, center_z)
            camera.SetViewUp(0, 0, 1)
        
        camera.SetFocalPoint(center_x, center_y, center_z)
        self.renderer.ResetCamera()
        self.render_window.Render()
    
    def refresh(self):
        """Refresh the 3D view."""
        self.update_view()
    
    def _on_right_click(self, obj, event):
        """Handle right-click for context menu."""
        if not self.project:
            return
        
        # Get click position
        click_pos = self.interactor.GetEventPosition()
        
        # Store for menu positioning
        self._last_click_pos = click_pos
        
        # Pick at the click position
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        picked_actor = self.picker.GetActor()
        
        if not picked_actor:
            return
        
        # Determine what was clicked
        point_id = self.actor_to_point_id.get(picked_actor)
        line_id = self.actor_to_line_id.get(picked_actor)
        curve_id = self.actor_to_curve_id.get(picked_actor)
        
        # Check if picked point/line belongs to curve(s)
        curves_for_point = []
        curves_for_line = []
        
        if point_id is not None:
            # Find curves that contain this point in their arc_point_ids
            curves_for_point = [c for c in self.project.curves 
                               if point_id in c.arc_point_ids and not c.hidden]
        
        if line_id is not None:
            # Find curves that use this line as their base_line_id
            curves_for_line = [c for c in self.project.curves 
                              if hasattr(c, 'base_line_id') and c.base_line_id == line_id and not c.hidden]
        
        # Decide what to show based on what was picked and curve associations
        if curve_id is not None:
            # Directly picked a curve
            self._show_curve_context_menu(curve_id)
        elif point_id is not None:
            # Check if this point is a curve endpoint
            curves_with_endpoint = [c for c in self.project.curves 
                                   if not c.hidden and (point_id == c.start_id or point_id == c.end_id)]
            
            if curves_with_endpoint:
                # Point is a curve endpoint - show combined menu with curve ops and line drawing
                self._show_curve_endpoint_context_menu(point_id, curves_with_endpoint)
            elif curves_for_point:
                # Point is an arc point (not endpoint) of curve(s) - only show curve menu
                if len(curves_for_point) == 1:
                    self._show_curve_context_menu(curves_for_point[0].id)
                else:
                    # Multiple curves - show selection dialog
                    self._show_multi_choice_menu(None, None, [c.id for c in curves_for_point])
            else:
                # Just a point - show point menu with line options
                self._show_point_context_menu(point_id)
        elif line_id is not None:
            if curves_for_line:
                # Line is base of curve(s) - only show curve menu
                if len(curves_for_line) == 1:
                    self._show_curve_context_menu(curves_for_line[0].id)
                else:
                    # Multiple curves - show selection dialog
                    self._show_multi_choice_menu(None, None, [c.id for c in curves_for_line])
            else:
                # Just a line, no curve
                self._show_line_context_menu(line_id)
    
    def _show_point_context_menu(self, point_id: int):
        """Show context menu for a point."""
        menu = QMenu(f"Point {point_id}")
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.point_identify_requested.emit(point_id))
        
        menu.addSeparator()
        
        # Check if this point is an arc point (intermediate point) of any curve
        # Note: arc_point_ids contains center and intermediate points, NOT start/end
        is_arc_point = False
        for curve in self.project.curves:
            if point_id in curve.arc_point_ids:
                is_arc_point = True
                break
        
        # Line drawing options (exclude arc points, but allow curve endpoints)
        if not is_arc_point:
            if self.line_start_point_id is None:
                line_from_action = menu.addAction("Line from here")
                line_from_action.triggered.connect(lambda: self._start_line_from(point_id))
            elif self.line_start_point_id == point_id:
                cancel_action = menu.addAction("Cancel line drawing")
                cancel_action.triggered.connect(self._cancel_line_drawing)
            else:
                line_to_action = menu.addAction(f"Line to here (from Point {self.line_start_point_id})")
                line_to_action.triggered.connect(lambda: self._finish_line_to(point_id))
                
                cancel_action = menu.addAction("Cancel line drawing")
                cancel_action.triggered.connect(self._cancel_line_drawing)
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.point_duplicate_requested.emit(point_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.point_delete_requested.emit(point_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        # Convert VTK event position to global coordinates
        # VTK uses bottom-left origin, Qt uses top-left, so we need to flip Y
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
    
    def _show_line_context_menu(self, line_id: int):
        """Show context menu for a line."""
        menu = QMenu(f"Line {line_id}")
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.line_identify_requested.emit(line_id))
        
        trace_action = menu.addAction("Line Trace")
        trace_action.triggered.connect(lambda: self.line_trace_requested.emit(line_id))
        
        menu.addSeparator()
        
        reverse_action = menu.addAction("Reverse Direction")
        reverse_action.triggered.connect(lambda: self.line_reverse_requested.emit(line_id))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.line_duplicate_requested.emit(line_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.line_delete_requested.emit(line_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        # Convert VTK event position to global coordinates
        # VTK uses bottom-left origin, Qt uses top-left, so we need to flip Y
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
    
    def _show_curve_context_menu(self, curve_id: int):
        """Show context menu for a curve."""
        menu = QMenu(f"Curve {curve_id}")
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.curve_identify_requested.emit(curve_id))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.curve_duplicate_requested.emit(curve_id))
        
        reverse_action = menu.addAction("Reverse Direction")
        reverse_action.triggered.connect(lambda: self.curve_reverse_requested.emit(curve_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.curve_delete_requested.emit(curve_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        # Convert VTK event position to global coordinates
        # VTK uses bottom-left origin, Qt uses top-left, so we need to flip Y
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
    
    def _show_curve_endpoint_context_menu(self, point_id: int, curve_ids: list):
        """Show combined context menu for a curve endpoint with both curve and line drawing options."""
        # If multiple curves, show selection first
        if len(curve_ids) > 1:
            menu = QMenu("Curve Endpoint")
            for cid in curve_ids:
                curve_action = menu.addAction(f"Curve {cid}")
                curve_action.triggered.connect(lambda checked, c=cid: self._show_curve_context_menu(c))
        else:
            # Single curve - show combined menu
            curve_id = curve_ids[0]
            menu = QMenu(f"Curve {curve_id} Endpoint")
            
            # Curve operations section
            curve_props_action = menu.addAction("Properties")
            curve_props_action.triggered.connect(lambda: self.curve_identify_requested.emit(curve_id))
            
            duplicate_action = menu.addAction("Duplicate")
            duplicate_action.triggered.connect(lambda: self.curve_duplicate_requested.emit(curve_id))
            
            reverse_action = menu.addAction("Reverse Direction")
            reverse_action.triggered.connect(lambda: self.curve_reverse_requested.emit(curve_id))
            
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.curve_delete_requested.emit(curve_id))
        
        menu.addSeparator()
        
        # Line drawing options (same as point menu)
        if self.line_start_point_id is None:
            line_from_action = menu.addAction("Line from here")
            line_from_action.triggered.connect(lambda: self._start_line_from(point_id))
        elif self.line_start_point_id == point_id:
            cancel_action = menu.addAction("Cancel line drawing")
            cancel_action.triggered.connect(self._cancel_line_drawing)
        else:
            line_to_action = menu.addAction("Line to here")
            line_to_action.triggered.connect(lambda: self._finish_line_to(point_id))
            
            cancel_action = menu.addAction("Cancel line drawing")
            cancel_action.triggered.connect(self._cancel_line_drawing)
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        # Convert VTK event position to global coordinates
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
    
    def _show_choice_menu(self, point_id: int = None, line_id: int = None, curve_id: int = None):
        """Show menu to choose between point/line and curve."""
        menu = QMenu("Select Item")
        
        if point_id is not None:
            point_action = menu.addAction(f"Point {point_id}")
            point_action.triggered.connect(lambda: self._show_point_context_menu(point_id))
        
        if line_id is not None:
            line_action = menu.addAction(f"Line {line_id}")
            line_action.triggered.connect(lambda: self._show_line_context_menu(line_id))
        
        if curve_id is not None:
            curve_action = menu.addAction(f"Curve {curve_id}")
            curve_action.triggered.connect(lambda: self._show_curve_context_menu(curve_id))
        
        # Convert VTK event position to global coordinates
        # VTK uses bottom-left origin, Qt uses top-left, so we need to flip Y
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
    
    def _start_line_from(self, point_id: int):
        """Start line drawing mode from a point."""
        self.line_start_point_id = point_id
    
    def _finish_line_to(self, point_id: int):
        """Finish line drawing to a point."""
        if self.line_start_point_id is not None:
            self.line_create_requested.emit(self.line_start_point_id, point_id)
            self.line_start_point_id = None
    
    def _cancel_line_drawing(self):
        """Cancel line drawing mode."""
        if self.line_start_point_id is not None:
            self.line_start_point_id = None
    
    def _show_multi_choice_menu(self, point_id: int = None, line_id: int = None, curve_ids: list = None):
        """Show menu to choose between point/line and multiple curves."""
        menu = QMenu("Select Item")
        
        if point_id is not None:
            point_action = menu.addAction(f"Point {point_id}")
            point_action.triggered.connect(lambda: self._show_point_context_menu(point_id))
        
        if line_id is not None:
            line_action = menu.addAction(f"Line {line_id}")
            line_action.triggered.connect(lambda: self._show_line_context_menu(line_id))
        
        if curve_ids:
            menu.addSeparator()
            for cid in curve_ids:
                curve_action = menu.addAction(f"Curve {cid}")
                curve_action.triggered.connect(lambda checked, c=cid: self._show_curve_context_menu(c))
        
        # Convert VTK event position to global coordinates
        # VTK uses bottom-left origin, Qt uses top-left, so we need to flip Y
        if hasattr(self, '_last_click_pos'):
            widget_height = self.vtk_widget.height()
            local_pos = QPoint(self._last_click_pos[0], widget_height - self._last_click_pos[1])
            global_pos = self.vtk_widget.mapToGlobal(local_pos)
            menu.exec(global_pos)
        else:
            menu.exec(QCursor.pos())
        
        # Simulate button release to VTK to prevent stuck state
        self.interactor.InvokeEvent("RightButtonReleaseEvent")
