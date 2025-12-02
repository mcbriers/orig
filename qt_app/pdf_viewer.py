"""
PDF viewer widget with interactive point selection.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QScrollArea, QSpinBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QMouseEvent
import fitz  # PyMuPDF


class PDFViewer(QWidget):
    """PDF viewer with click handling for point creation."""
    
    # Signals
    pdf_clicked = pyqtSignal(float, float, float, float)  # canvas_x, canvas_y, pdf_x, pdf_y
    point_identify_requested = pyqtSignal(int)  # point_id
    point_duplicate_requested = pyqtSignal(int)  # point_id
    point_delete_requested = pyqtSignal(int)  # point_id
    line_identify_requested = pyqtSignal(int)  # line_id
    line_duplicate_requested = pyqtSignal(int)  # line_id
    line_delete_requested = pyqtSignal(int)  # line_id
    line_trace_requested = pyqtSignal(int)  # line_id
    curve_identify_requested = pyqtSignal(int)  # curve_id
    curve_duplicate_requested = pyqtSignal(int)  # curve_id
    curve_delete_requested = pyqtSignal(int)  # curve_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.pdf_doc = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.current_pixmap = None
        self.project = None  # Reference to project data for curve detection
        
        # Drawing overlays
        self.point_markers = {}  # {point_id: (x, y)}
        self.calibration_markers = []  # [(x, y), ...]
        self.line_segments = []  # [(line_id, x1, y1, x2, y2), ...]
        self.curve_polylines = []  # [(curve_id, [(x1,y1), (x2,y2), ...]), ...]
        
        # Highlighted items for trace visualization
        self.highlighted_points = set()  # {point_id, ...}
        self.highlighted_lines = set()  # {line_id, ...}
        self.highlighted_curves = set()  # {curve_id, ...}
        
        # Render settings
        self.point_color = (0, 0, 255)
        self.point_size = 5
        self.line_color = (0, 200, 0)
        self.line_width = 2
        self.curve_color = (200, 0, 200)
        self.curve_width = 2
        self.calibration_color = (255, 0, 0)
        self.calibration_size = 8
        
        # Click tolerances (in pixels)
        self.point_tolerance = 30
        self.line_tolerance = 30
        self.curve_tolerance = 30
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.page_label = QLabel("No PDF loaded")
        toolbar.addWidget(self.page_label)
        
        toolbar.addStretch()
        
        self.prev_btn = QPushButton("< Prev")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        toolbar.addWidget(self.prev_btn)
        
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.goto_page)
        self.page_spin.setEnabled(False)
        toolbar.addWidget(self.page_spin)
        
        self.next_btn = QPushButton("Next >")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        toolbar.addWidget(self.next_btn)
        
        toolbar.addStretch()
        
        zoom_out_btn = QPushButton("Zoom -")
        zoom_out_btn.clicked.connect(lambda: self.set_zoom(self.zoom_level - 0.2))
        toolbar.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel("100%")
        toolbar.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(lambda: self.set_zoom(self.zoom_level + 0.2))
        toolbar.addWidget(zoom_in_btn)
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.clicked.connect(lambda: self.set_zoom(1.0))
        toolbar.addWidget(zoom_reset_btn)
        
        layout.addLayout(toolbar)
        
        # Scroll area for PDF content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_label.setText("No PDF loaded\n\nUse File → Load PDF to begin")
        self.pdf_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 20px; }")
        self.pdf_label.mousePressEvent = self._on_label_click
        self.pdf_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pdf_label.customContextMenuRequested.connect(self._show_context_menu)
        
        # Install event filter for wheel events
        self.scroll_area.viewport().installEventFilter(self)
        
        self.scroll_area.setWidget(self.pdf_label)
        layout.addWidget(self.scroll_area)
    
    def load_pdf(self, file_path: str) -> bool:
        """Load a PDF file."""
        try:
            # Check if file exists first
            import os
            if not os.path.exists(file_path):
                print(f"PDF file not found: {file_path}")
                return False
            
            self.pdf_doc = fitz.open(file_path)
            self.total_pages = len(self.pdf_doc)
            self.current_page = 0
            
            self.page_spin.setMaximum(self.total_pages)
            self.page_spin.setValue(1)
            self.page_spin.setEnabled(True)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(self.total_pages > 1)
            
            self.render_page()
            return True
        except Exception as e:
            print(f"Failed to load PDF: {e}")
            return False
    
    def set_project(self, project):
        """Set the project reference for curve detection."""
        self.project = project
    
    def render_page(self):
        """Render the current PDF page."""
        if not self.pdf_doc:
            return
        
        try:
            page = self.pdf_doc[self.current_page]
            
            # Render at zoom level
            mat = fitz.Matrix(self.zoom_level, self.zoom_level)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to QImage
            img_format = QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format)
            
            # Convert to QPixmap
            self.current_pixmap = QPixmap.fromImage(qimage)
            
            # Draw overlays
            self._draw_overlays()
            
            # Update display
            self.pdf_label.setPixmap(self.current_pixmap)
            self.page_label.setText(f"Page {self.current_page + 1} of {self.total_pages}")
            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
            
            # Update navigation buttons
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
            
        except Exception as e:
            print(f"Failed to render page: {e}")
    
    def _draw_overlays(self):
        """Draw point markers and calibration markers on the pixmap."""
        if not self.current_pixmap:
            return
        
        painter = QPainter(self.current_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw calibration markers
        if self.calibration_markers:
            pen = QPen(QColor(*self.calibration_color), 3)
            painter.setPen(pen)
            for x, y in self.calibration_markers:
                cx = x * self.zoom_level
                cy = y * self.zoom_level
                painter.drawEllipse(QPointF(cx, cy), self.calibration_size, self.calibration_size)
        
        # Draw line segments
        for line_data in self.line_segments:
            if len(line_data) >= 5:
                line_id, x1, y1, x2, y2 = line_data
                # Highlight traced lines
                if line_id in self.highlighted_lines:
                    pen = QPen(QColor(255, 165, 0), self.line_width * 3)  # Orange, thicker
                else:
                    pen = QPen(QColor(*self.line_color), self.line_width)
                painter.setPen(pen)
                painter.drawLine(
                    int(x1 * self.zoom_level), int(y1 * self.zoom_level),
                    int(x2 * self.zoom_level), int(y2 * self.zoom_level)
                )
        
        # Draw curve polylines
        for curve_data in self.curve_polylines:
            if len(curve_data) >= 2:
                curve_id, polyline = curve_data
                # Highlight traced curves
                if curve_id in self.highlighted_curves:
                    pen = QPen(QColor(255, 165, 0), self.curve_width * 3)  # Orange, thicker
                else:
                    pen = QPen(QColor(*self.curve_color), self.curve_width)
                painter.setPen(pen)
                for i in range(len(polyline) - 1):
                    x1, y1 = polyline[i]
                    x2, y2 = polyline[i + 1]
                    painter.drawLine(
                        int(x1 * self.zoom_level), int(y1 * self.zoom_level),
                        int(x2 * self.zoom_level), int(y2 * self.zoom_level)
                    )
        
        # Draw point markers
        for point_id, (x, y) in self.point_markers.items():
            cx = x * self.zoom_level
            cy = y * self.zoom_level
            # Highlight traced points
            if point_id in self.highlighted_points:
                pen = QPen(QColor(255, 165, 0), 4)  # Orange, thicker
                painter.setPen(pen)
                painter.drawEllipse(QPointF(cx, cy), self.point_size * 1.5, self.point_size * 1.5)
            else:
                pen = QPen(QColor(*self.point_color), 2)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(cx, cy), self.point_size, self.point_size)
        
        painter.end()
    
    def _on_label_click(self, event):
        """Handle mouse clicks on the PDF."""
        if not self.pdf_doc:
            return
        
        # Only handle left clicks for point creation
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        # Get click position relative to label
        click_pos = event.pos()
        
        # Account for label alignment - pixmap may be centered in label
        # Calculate offset if label is larger than pixmap
        if self.current_pixmap:
            label_width = self.pdf_label.width()
            label_height = self.pdf_label.height()
            pixmap_width = self.current_pixmap.width()
            pixmap_height = self.current_pixmap.height()
            
            # Calculate centering offset
            offset_x = max(0, (label_width - pixmap_width) / 2.0)
            offset_y = max(0, (label_height - pixmap_height) / 2.0)
            
            # Adjust click position to pixmap coordinates
            canvas_x = float(click_pos.x()) - offset_x
            canvas_y = float(click_pos.y()) - offset_y
            
            # Check if click is outside pixmap bounds
            if canvas_x < 0 or canvas_y < 0 or canvas_x >= pixmap_width or canvas_y >= pixmap_height:
                return
            
            # Convert to PDF coordinates (account for zoom)
            pdf_x = canvas_x / self.zoom_level
            pdf_y = canvas_y / self.zoom_level
            
            # Emit signal
            self.pdf_clicked.emit(canvas_x, canvas_y, pdf_x, pdf_y)
    
    def eventFilter(self, obj, event):
        """Handle mouse wheel events for zoom and scroll."""
        if obj == self.scroll_area.viewport() and event.type() == event.Type.Wheel:
            modifiers = event.modifiers()
            
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                # Ctrl + Wheel = Zoom at cursor
                delta = event.angleDelta().y()
                if delta != 0:
                    # Get cursor position relative to viewport
                    cursor_pos = event.position()
                    
                    # Get scroll bar positions before zoom
                    h_scroll = self.scroll_area.horizontalScrollBar()
                    v_scroll = self.scroll_area.verticalScrollBar()
                    old_h = h_scroll.value()
                    old_v = v_scroll.value()
                    
                    # Calculate zoom factor
                    zoom_factor = 1.1 if delta > 0 else 0.9
                    new_zoom = self.zoom_level * zoom_factor
                    new_zoom = max(0.2, min(5.0, new_zoom))
                    
                    # Apply zoom
                    old_zoom = self.zoom_level
                    self.zoom_level = new_zoom
                    self.render_page()
                    
                    # Adjust scroll to keep cursor position stable
                    zoom_ratio = new_zoom / old_zoom
                    h_scroll.setValue(int(old_h * zoom_ratio + cursor_pos.x() * (zoom_ratio - 1)))
                    v_scroll.setValue(int(old_v * zoom_ratio + cursor_pos.y() * (zoom_ratio - 1)))
                    
                    return True
            
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Shift + Wheel = Scroll horizontally
                delta = event.angleDelta().y()
                h_scroll = self.scroll_area.horizontalScrollBar()
                h_scroll.setValue(h_scroll.value() - delta)
                return True
            
            else:
                # Plain wheel = Scroll vertically (default behavior, let it pass through)
                return False
        
        return super().eventFilter(obj, event)
    
    def _show_context_menu(self, pos: QPoint):
        """Show context menu on right-click."""
        if not self.pdf_doc:
            return
        
        # Convert to PDF coordinates
        canvas_x = pos.x()
        canvas_y = pos.y()
        pdf_x = canvas_x / self.zoom_level
        pdf_y = canvas_y / self.zoom_level
        
        # Check what's under the cursor (in order of priority: point, line, curve)
        point_id = self._find_point_at(pdf_x, pdf_y, tolerance=self.point_tolerance)
        line_id = None if point_id else self._find_line_at(pdf_x, pdf_y, tolerance=self.line_tolerance)
        curve_id = None if (point_id or line_id) else self._find_curve_at(pdf_x, pdf_y, tolerance=self.curve_tolerance)
        
        # Check if picked point/line belongs to curve(s)
        curves_for_point = []
        curves_for_line = []
        
        if point_id is not None and self.project:
            # Find curves that contain this point in their arc_point_ids
            curves_for_point = [c for c in self.project.curves 
                               if point_id in c.arc_point_ids and not c.hidden]
        
        if line_id is not None and self.project:
            # Find curves that use this line as their base_line_id
            curves_for_line = [c for c in self.project.curves 
                              if hasattr(c, 'base_line_id') and c.base_line_id == line_id and not c.hidden]
        
        # Decide what to show based on what was picked and curve associations
        if curve_id is not None:
            # Directly picked a curve
            self._show_curve_menu(curve_id, pos)
        elif point_id is not None:
            # Check if this point is a curve endpoint
            curves_with_endpoint = [c for c in self.project.curves 
                                   if not c.hidden and (point_id == c.start_id or point_id == c.end_id)]
            
            if curves_with_endpoint:
                # Point is a curve endpoint - show combined menu with curve ops
                self._show_curve_endpoint_menu(point_id, curves_with_endpoint, pos)
            elif curves_for_point:
                # Point is an arc point (not endpoint) of curve(s) - only show curve menu
                if len(curves_for_point) == 1:
                    self._show_curve_menu(curves_for_point[0].id, pos)
                else:
                    # Multiple curves - show selection dialog
                    self._show_multi_choice_menu(pos, None, None, [c.id for c in curves_for_point])
            else:
                # Just a point - show point menu
                self._show_point_menu(point_id, pos)
        elif line_id is not None:
            if curves_for_line:
                # Line is base of curve(s) - only show curve menu
                if len(curves_for_line) == 1:
                    self._show_curve_menu(curves_for_line[0].id, pos)
                else:
                    # Multiple curves - show selection dialog
                    self._show_multi_choice_menu(pos, None, None, [c.id for c in curves_for_line])
            else:
                # Just a line, no curve
                self._show_line_menu(line_id, pos)
    
    def _show_point_menu(self, point_id: int, pos: QPoint):
        """Show context menu for a point."""
        menu = QMenu(f"Point {point_id}", self)
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.point_identify_requested.emit(point_id))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.point_duplicate_requested.emit(point_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.point_delete_requested.emit(point_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _show_line_menu(self, line_id: int, pos: QPoint):
        """Show context menu for a line."""
        menu = QMenu(f"Line {line_id}", self)
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.line_identify_requested.emit(line_id))
        
        trace_action = menu.addAction("Line Trace")
        trace_action.triggered.connect(lambda: self.line_trace_requested.emit(line_id))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.line_duplicate_requested.emit(line_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.line_delete_requested.emit(line_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _show_curve_menu(self, curve_id: int, pos: QPoint):
        """Show context menu for a curve."""
        menu = QMenu(f"Curve {curve_id}", self)
        
        identify_action = menu.addAction("Properties")
        identify_action.triggered.connect(lambda: self.curve_identify_requested.emit(curve_id))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.curve_duplicate_requested.emit(curve_id))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.curve_delete_requested.emit(curve_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _show_curve_endpoint_menu(self, point_id: int, curve_ids: list, pos: QPoint):
        """Show combined context menu for a curve endpoint with both curve and line drawing options."""
        # If multiple curves, show selection first
        if len(curve_ids) > 1:
            menu = QMenu(f"Point {point_id} (Curve Endpoint)", self)
            for cid in curve_ids:
                curve_action = menu.addAction(f"Curve {cid} Options")
                curve_action.triggered.connect(lambda checked, c=cid, p=pos: self._show_curve_menu(c, p))
        else:
            # Single curve - show combined menu
            curve_id = curve_ids[0]
            menu = QMenu(f"Point {point_id} (Curve {curve_id} Endpoint)", self)
            
            # Curve operations section
            curve_props_action = menu.addAction(f"Curve {curve_id} Properties")
            curve_props_action.triggered.connect(lambda: self.curve_identify_requested.emit(curve_id))
            
            duplicate_action = menu.addAction(f"Duplicate Curve {curve_id}")
            duplicate_action.triggered.connect(lambda: self.curve_duplicate_requested.emit(curve_id))
            
            delete_action = menu.addAction(f"Delete Curve {curve_id}")
            delete_action.triggered.connect(lambda: self.curve_delete_requested.emit(curve_id))
            
            menu.addSeparator()
            
            # Point operations
            point_props_action = menu.addAction(f"Point {point_id} Properties")
            point_props_action.triggered.connect(lambda: self.point_identify_requested.emit(point_id))
            
            dup_point_action = menu.addAction(f"Duplicate Point {point_id}")
            dup_point_action.triggered.connect(lambda: self.point_duplicate_requested.emit(point_id))
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Clear Highlighting")
        clear_action.triggered.connect(self.clear_highlighted)
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _show_choice_menu(self, pos: QPoint, point_id: int = None, line_id: int = None, curve_id: int = None):
        """Show menu to choose between point/line and curve."""
        menu = QMenu("Select Item", self)
        
        if point_id is not None:
            point_action = menu.addAction(f"Point {point_id}")
            point_action.triggered.connect(lambda: self._show_point_menu(point_id, pos))
        
        if line_id is not None:
            line_action = menu.addAction(f"Line {line_id}")
            line_action.triggered.connect(lambda: self._show_line_menu(line_id, pos))
        
        if curve_id is not None:
            curve_action = menu.addAction(f"Curve {curve_id}")
            curve_action.triggered.connect(lambda: self._show_curve_menu(curve_id, pos))
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _show_multi_choice_menu(self, pos: QPoint, point_id: int = None, line_id: int = None, curve_ids: list = None):
        """Show menu to choose between point/line and multiple curves."""
        menu = QMenu("Select Item", self)
        
        if point_id is not None:
            point_action = menu.addAction(f"Point {point_id}")
            point_action.triggered.connect(lambda: self._show_point_menu(point_id, pos))
        
        if line_id is not None:
            line_action = menu.addAction(f"Line {line_id}")
            line_action.triggered.connect(lambda: self._show_line_menu(line_id, pos))
        
        if curve_ids:
            menu.addSeparator()
            for cid in curve_ids:
                curve_action = menu.addAction(f"Curve {cid}")
                curve_action.triggered.connect(lambda checked, c=cid, p=pos: self._show_curve_menu(c, p))
        
        menu.exec(self.pdf_label.mapToGlobal(pos))
    
    def _find_point_at(self, pdf_x: float, pdf_y: float, tolerance: float = 10.0) -> int:
        """Find a point near the given coordinates."""
        tolerance_scaled = tolerance / self.zoom_level
        
        closest_id = None
        closest_dist = float('inf')
        
        for point_id, (px, py) in self.point_markers.items():
            dx = px - pdf_x
            dy = py - pdf_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance <= tolerance_scaled and distance < closest_dist:
                closest_id = point_id
                closest_dist = distance
        
        return closest_id
    
    def _find_line_at(self, pdf_x: float, pdf_y: float, tolerance: float = 8.0) -> int:
        """Find a line near the given coordinates."""
        tolerance_scaled = tolerance / self.zoom_level
        
        closest_id = None
        closest_dist = float('inf')
        
        for line_data in self.line_segments:
            if len(line_data) < 5:
                continue
            line_id, x1, y1, x2, y2 = line_data
            
            # Distance from point to line segment
            dist = self._point_to_segment_distance(pdf_x, pdf_y, x1, y1, x2, y2)
            
            if dist <= tolerance_scaled and dist < closest_dist:
                closest_id = line_id
                closest_dist = dist
        
        return closest_id
    
    def _find_curve_at(self, pdf_x: float, pdf_y: float, tolerance: float = 8.0) -> int:
        """Find a curve near the given coordinates."""
        tolerance_scaled = tolerance / self.zoom_level
        
        closest_id = None
        closest_dist = float('inf')
        
        for curve_data in self.curve_polylines:
            if len(curve_data) < 2:
                continue
            curve_id, points = curve_data
            
            # Check distance to each segment of the polyline
            min_dist = float('inf')
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                dist = self._point_to_segment_distance(pdf_x, pdf_y, x1, y1, x2, y2)
                min_dist = min(min_dist, dist)
            
            if min_dist <= tolerance_scaled and min_dist < closest_dist:
                closest_id = curve_id
                closest_dist = min_dist
        
        return closest_id
    
    def _point_to_segment_distance(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        """Calculate distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Degenerate segment
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        
        # Parameter t of closest point on the line
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5
    
    def set_render_settings(self, point_color=None, point_size=None, line_color=None, 
                           line_width=None, curve_color=None, curve_width=None,
                           calibration_color=None, calibration_size=None,
                           point_tolerance=None, line_tolerance=None, curve_tolerance=None):
        """Update render settings."""
        if point_color is not None:
            self.point_color = point_color
        if point_size is not None:
            self.point_size = point_size
        if line_color is not None:
            self.line_color = line_color
        if line_width is not None:
            self.line_width = line_width
        if curve_color is not None:
            self.curve_color = curve_color
        if curve_width is not None:
            self.curve_width = curve_width
        if calibration_color is not None:
            self.calibration_color = calibration_color
        if calibration_size is not None:
            self.calibration_size = calibration_size
        if point_tolerance is not None:
            self.point_tolerance = point_tolerance
        if line_tolerance is not None:
            self.line_tolerance = line_tolerance
        if curve_tolerance is not None:
            self.curve_tolerance = curve_tolerance
    
    def add_point_marker(self, point_id: int, pdf_x: float, pdf_y: float):
        """Add a point marker at PDF coordinates."""
        self.point_markers[point_id] = (pdf_x, pdf_y)
        # Don't re-render immediately for bulk additions
    
    def refresh_markers(self):
        """Refresh the display with all markers (call after bulk additions)."""
        if self.current_pixmap:
            self.render_page()
    
    def set_highlighted(self, points=None, lines=None, curves=None):
        """Set highlighted items for trace visualization."""
        self.highlighted_points = set(points) if points else set()
        self.highlighted_lines = set(lines) if lines else set()
        self.highlighted_curves = set(curves) if curves else set()
        self.refresh_markers()
    
    def clear_highlighted(self):
        """Clear all highlighted items."""
        self.highlighted_points.clear()
        self.highlighted_lines.clear()
        self.highlighted_curves.clear()
        self.refresh_markers()
    
    def remove_point_marker(self, point_id: int):
        """Remove a point marker."""
        if point_id in self.point_markers:
            del self.point_markers[point_id]
            self.render_page()
    
    def clear_point_markers(self):
        """Clear all point markers."""
        self.point_markers.clear()
        self.render_page()
    
    def add_calibration_marker(self, pdf_x: float, pdf_y: float):
        """Add a calibration marker."""
        self.calibration_markers.append((pdf_x, pdf_y))
        self.render_page()
    
    def clear_calibration_markers(self):
        """Clear calibration markers."""
        self.calibration_markers.clear()
        self.render_page()
    
    def set_lines(self, lines_data):
        """Set line segments to draw. Format: [(x1, y1, x2, y2), ...]"""
        self.line_segments = lines_data
    
    def set_curves(self, curves_data):
        """Set curve polylines to draw. Format: [[(x1,y1), (x2,y2), ...], ...]"""
        self.curve_polylines = curves_data
    
    def set_zoom(self, zoom: float):
        """Set zoom level."""
        self.zoom_level = max(0.2, min(5.0, zoom))
        self.render_page()
    
    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.page_spin.setValue(self.current_page + 1)
            self.render_page()
    
    def next_page(self):
        """Go to next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.page_spin.setValue(self.current_page + 1)
            self.render_page()
    
    def goto_page(self, page_num: int):
        """Go to specific page (1-indexed)."""
        new_page = page_num - 1
        if 0 <= new_page < self.total_pages:
            self.current_page = new_page
            self.render_page()
