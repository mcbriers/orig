"""
Main window for the Qt-based 3D digitizer application.
"""
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar, QMenuBar,
                             QMenu, QFileDialog, QMessageBox, QWidget, QVBoxLayout,
                             QToolBar, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                             QDockWidget, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from pathlib import Path

from .models import ProjectData
from .geometry import GeometryEngine
from .operations import Operations
from .audit import LineAudit
from .import_export import ImportExport
from .pdf_viewer import PDFViewer
from .editor_widget import EditorWidget
from .viewer_3d import Viewer3D


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    project_loaded = pyqtSignal()
    project_saved = pyqtSignal()
    project_modified = pyqtSignal()
    mode_changed = pyqtSignal(str)  # 'calibration', 'coordinates', 'lines', 'curves'
    
    def __init__(self):
        super().__init__()
        
        # Core data and logic
        self.project = ProjectData()
        self.geometry = GeometryEngine()
        self.operations = Operations(self.project, self.geometry)
        self.audit = LineAudit(self.project)
        self.import_export = ImportExport()
        
        # UI state
        self.current_mode = 'calibration'
        self.current_z = 0.0
        
        # View settings
        self.show_points = True
        self.show_lines = True
        self.show_curves = True
        self.show_hidden = False
        
        # Render settings (RGB tuples and widths)
        self.point_color = (0, 0, 255)  # Blue
        self.point_size = 5
        self.line_color = (0, 200, 0)  # Green
        self.line_width = 2
        self.curve_color = (200, 0, 200)  # Magenta
        self.curve_width = 2
        self.calibration_color = (255, 0, 0)  # Red
        self.calibration_size = 8
        
        # Click tolerances (in pixels)
        self.point_tolerance = 30
        self.line_tolerance = 30
        self.curve_tolerance = 30
        
        # Last Z levels for duplication (remembered across operations)
        self.last_z_levels = "250"
        
        # Theme preference ("system", "light", "dark")
        self.theme_mode = "system"
        
        self.setWindowTitle("3D Maker Digitizer - Qt")
        self.resize(1400, 900)
        
        self._setup_ui()
        self._create_menus()
        self._create_statusbar()
        self._create_toolbar()
        
        # Auto-load calibrated.dig if it exists
        self._autoload_project()
        
        self.showMaximized()
    
    def _setup_ui(self):
        """Set up the main UI layout."""
        # Central widget with tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        
        # PDF viewer tab
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.set_project(self.project)
        self.pdf_viewer.pdf_clicked.connect(self._handle_pdf_click)
        self.pdf_viewer.point_identify_requested.connect(self._identify_point)
        self.pdf_viewer.point_duplicate_requested.connect(self._duplicate_point)
        self.pdf_viewer.point_delete_requested.connect(self._delete_point)
        self.pdf_viewer.line_identify_requested.connect(self._identify_line)
        self.pdf_viewer.line_duplicate_requested.connect(self._duplicate_line)
        self.pdf_viewer.line_delete_requested.connect(self._delete_line)
        self.pdf_viewer.line_trace_requested.connect(self._trace_from_line)
        self.pdf_viewer.curve_identify_requested.connect(self._identify_curve)
        self.pdf_viewer.curve_duplicate_requested.connect(self._duplicate_curve)
        self.pdf_viewer.curve_delete_requested.connect(self._delete_curve)
        self.tabs.addTab(self.pdf_viewer, "PDF Viewer")
        
        # Editor tab
        self.editor = EditorWidget(self.project)
        self.editor.duplicate_point_requested.connect(self._duplicate_point)
        self.editor.delete_point_requested.connect(self._delete_point)
        self.editor.delete_points_requested.connect(self._delete_points)
        self.editor.duplicate_line_requested.connect(self._duplicate_line)
        self.editor.delete_line_requested.connect(self._delete_line)
        self.editor.delete_lines_requested.connect(self._delete_lines)
        self.editor.duplicate_curve_requested.connect(self._duplicate_curve)
        self.editor.delete_curve_requested.connect(self._delete_curve)
        self.editor.delete_curves_requested.connect(self._delete_curves)
        self.editor.show_references_requested.connect(self._show_point_references)
        self.tabs.addTab(self.editor, "2D Editor")
        
        # 3D view tab
        self.viewer_3d = Viewer3D()
        self.viewer_3d.set_project(self.project)
        self.viewer_3d.point_identify_requested.connect(self._identify_point)
        self.viewer_3d.point_duplicate_requested.connect(self._duplicate_point)
        self.viewer_3d.point_delete_requested.connect(self._delete_point)
        self.viewer_3d.line_identify_requested.connect(self._identify_line)
        self.viewer_3d.line_duplicate_requested.connect(self._duplicate_line)
        self.viewer_3d.line_delete_requested.connect(self._delete_line)
        self.viewer_3d.line_trace_requested.connect(self._trace_from_line)
        self.viewer_3d.line_reverse_requested.connect(self._reverse_line)
        self.viewer_3d.curve_identify_requested.connect(self._identify_curve)
        self.viewer_3d.curve_duplicate_requested.connect(self._duplicate_curve)
        self.viewer_3d.curve_delete_requested.connect(self._delete_curve)
        self.viewer_3d.curve_reverse_requested.connect(self._reverse_curve)
        self.viewer_3d.line_create_requested.connect(self._create_line_from_3d)
        self.tabs.addTab(self.viewer_3d, "3D View")
        
        # Track if 3D view has been initialized
        self._3d_view_initialized = False
    
    def _on_tab_changed(self, index: int):
        """Handle tab change - initialize 3D view when first accessed."""
        # Check if the 3D View tab was selected (it's the third tab, index 2)
        if index == 2 and not self._3d_view_initialized:
            self._3d_view_initialized = True
            # Reset the camera initialization flag to force camera reset
            self.viewer_3d._camera_initialized = False
            self.viewer_3d.update_view()
    
    def _set_theme(self, mode: str):
        """Set application theme."""
        from PyQt6.QtGui import QPalette, QColor
        from PyQt6.QtCore import Qt
        
        self.theme_mode = mode
        app = QApplication.instance()
        
        if mode == "system":
            # Reset to system default
            app.setStyleSheet("")
            app.setPalette(app.style().standardPalette())
        elif mode == "light":
            # Light theme
            app.setStyleSheet("""
                QWidget {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QTableView {
                    background-color: #ffffff;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section {
                    background-color: #e0e0e0;
                    color: #000000;
                }
                QMenuBar {
                    background-color: #f0f0f0;
                }
                QMenu {
                    background-color: #ffffff;
                }
            """)
        elif mode == "dark":
            # Dark theme
            app.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTableView {
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                }
                QHeaderView::section {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                }
                QMenu {
                    background-color: #2b2b2b;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                }
                QPushButton:hover {
                    background-color: #4c4c4c;
                }
            """)
    
    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New Project", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open Project...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save Project &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        load_pdf_action = QAction("Load &PDF...", self)
        load_pdf_action.triggered.connect(self.load_pdf)
        file_menu.addAction(load_pdf_action)
        
        file_menu.addSeparator()
        
        export_menu = file_menu.addMenu("&Export")
        
        export_points_action = QAction("Points to CSV...", self)
        export_points_action.triggered.connect(self.export_points_csv)
        export_menu.addAction(export_points_action)
        
        export_lines_action = QAction("Lines to CSV...", self)
        export_lines_action.triggered.connect(self.export_lines_csv)
        export_menu.addAction(export_lines_action)
        
        export_curves_action = QAction("Curves to CSV...", self)
        export_curves_action.triggered.connect(self.export_curves_csv)
        export_menu.addAction(export_curves_action)
        
        export_grass_action = QAction("GRASS ASCII Format...", self)
        export_grass_action.triggered.connect(self.export_grass)
        export_menu.addAction(export_grass_action)
        
        export_sql_action = QAction("SQL Insert Script...", self)
        export_sql_action.triggered.connect(self.export_sql)
        export_menu.addAction(export_sql_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        calibrate_action = QAction("&Calibrate", self)
        calibrate_action.triggered.connect(self.start_calibration)
        tools_menu.addAction(calibrate_action)
        
        audit_action = QAction("&Line Audit...", self)
        audit_action.triggered.connect(self.show_line_audit)
        tools_menu.addAction(audit_action)
        
        validate_action = QAction("&Validate Project...", self)
        validate_action.triggered.connect(self.validate_project)
        tools_menu.addAction(validate_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Theme submenu
        theme_menu = view_menu.addMenu("&Theme")
        
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        
        system_theme_action = QAction("&System Default", self, checkable=True)
        system_theme_action.setChecked(True)
        system_theme_action.triggered.connect(lambda: self._set_theme("system"))
        theme_group.addAction(system_theme_action)
        theme_menu.addAction(system_theme_action)
        
        light_theme_action = QAction("&Light", self, checkable=True)
        light_theme_action.triggered.connect(lambda: self._set_theme("light"))
        theme_group.addAction(light_theme_action)
        theme_menu.addAction(light_theme_action)
        
        dark_theme_action = QAction("&Dark", self, checkable=True)
        dark_theme_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_group.addAction(dark_theme_action)
        theme_menu.addAction(dark_theme_action)
        
        view_menu.addSeparator()
        
        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self.show_settings)
        view_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Mode selection
        toolbar.addWidget(QLabel("Mode: "))
        
        calib_btn = QPushButton("Calibration")
        calib_btn.setCheckable(True)
        calib_btn.setToolTip("Calibration mode")
        calib_btn.clicked.connect(lambda: self.set_mode('calibration'))
        toolbar.addWidget(calib_btn)
        self.calib_btn = calib_btn
        
        coord_btn = QPushButton("Coordinates (1)")
        coord_btn.setCheckable(True)
        coord_btn.setToolTip("Place points mode (Press 1 in PDF view)")
        coord_btn.clicked.connect(lambda: self.set_mode('coordinates'))
        toolbar.addWidget(coord_btn)
        self.coord_btn = coord_btn
        
        lines_btn = QPushButton("Lines (2)")
        lines_btn.setCheckable(True)
        lines_btn.setToolTip("Draw lines mode (Press 2 in PDF view)")
        lines_btn.clicked.connect(lambda: self.set_mode('lines'))
        toolbar.addWidget(lines_btn)
        self.lines_btn = lines_btn
        
        curves_btn = QPushButton("Curves (3)")
        curves_btn.setCheckable(True)
        curves_btn.setToolTip("Draw curves mode (Press 3 in PDF view)")
        curves_btn.clicked.connect(lambda: self.set_mode('curves'))
        toolbar.addWidget(curves_btn)
        self.curves_btn = curves_btn
        
        toolbar.addSeparator()
        
        # Clear highlighting button
        clear_highlight_btn = QPushButton("Clear Highlighting")
        clear_highlight_btn.setToolTip("Clear all highlighting (Press Esc)")
        clear_highlight_btn.clicked.connect(self._clear_highlighting)
        toolbar.addWidget(clear_highlight_btn)
        
        toolbar.addSeparator()
        
        # Z level control
        toolbar.addWidget(QLabel("  Z Level: "))
        self.z_input = QLineEdit("0.0")
        self.z_input.setMaximumWidth(80)
        toolbar.addWidget(self.z_input)
        
        # Set initial mode
        self.set_mode('calibration')
    
    def _create_statusbar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def set_mode(self, mode: str):
        """Change the current input mode."""
        self.current_mode = mode
        
        # Update button states
        self.calib_btn.setChecked(mode == 'calibration')
        self.coord_btn.setChecked(mode == 'coordinates')
        self.lines_btn.setChecked(mode == 'lines')
        self.curves_btn.setChecked(mode == 'curves')
        
        self.mode_changed.emit(mode)
        self.status_bar.showMessage(f"Mode: {mode.capitalize()}")
    
    def update_status(self, message: str):
        """Update status bar message."""
        self.status_bar.showMessage(message)
    
    # ==================== FILE OPERATIONS ====================
    
    def new_project(self):
        """Create a new project."""
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Current project has unsaved changes. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        self.project.clear()
        self.geometry.transformation_matrix = None
        
        # Clear UI
        self.pdf_viewer.clear_point_markers()
        self.pdf_viewer.clear_calibration_markers()
        self._refresh_all_views()
        self.set_mode('calibration')
        
        self.project_loaded.emit()
        self.update_status("New project created")
    
    def open_project(self):
        """Open an existing project."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Digitizer Files (*.dig);;JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if self.import_export.load_project(self.project, file_path):
                self.geometry.transformation_matrix = self.project.transformation_matrix
                
                # Update PDF viewer if PDF path exists
                if self.project.pdf_path:
                    if self.pdf_viewer.load_pdf(self.project.pdf_path):
                        # PDF loaded successfully, now add markers
                        self._refresh_pdf_markers()
                        
                        # Update calibration markers
                        if self.project.reference_points_pdf:
                            self.pdf_viewer.clear_calibration_markers()
                            for pt in self.project.reference_points_pdf:
                                self.pdf_viewer.add_calibration_marker(pt[0], pt[1])
                    else:
                        QMessageBox.warning(self, "PDF Not Found", 
                                          f"Could not load PDF: {self.project.pdf_path}")
                
                # Refresh editor tables
                self._refresh_all_views()
                
                # Switch to coordinates mode if calibrated
                if self.project.transformation_matrix is not None:
                    self.set_mode('coordinates')
                
                self.project_loaded.emit()
                self.update_status(f"Loaded: {Path(file_path).name} - {len(self.project.points)} points, {len(self.project.lines)} lines, {len(self.project.curves)} curves")
            else:
                QMessageBox.critical(self, "Error", "Failed to load project")
    
    def save_project(self):
        """Save current project."""
        if self.project.project_path:
            if self.import_export.save_project(self.project, self.project.project_path):
                self.project_saved.emit()
                self.update_status("Project saved")
            else:
                QMessageBox.critical(self, "Error", "Failed to save project")
        else:
            self.save_project_as()
    
    def save_project_as(self):
        """Save project with new file name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "Digitizer Files (*.dig);;JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if not file_path.endswith('.dig') and not file_path.endswith('.json'):
                file_path += '.dig'
            
            if self.import_export.save_project(self.project, file_path):
                self.project_saved.emit()
                self.update_status(f"Saved: {Path(file_path).name}")
            else:
                QMessageBox.critical(self, "Error", "Failed to save project")
    
    def load_pdf(self):
        """Load a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            if self.pdf_viewer.load_pdf(file_path):
                self.project.pdf_path = file_path
                self.update_status(f"PDF loaded: {Path(file_path).name}")
                self._refresh_pdf_markers()
            else:
                QMessageBox.critical(self, "Error", "Failed to load PDF")
    
    # ==================== EXPORT OPERATIONS ====================
    
    def export_points_csv(self):
        """Export points to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Points", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            if self.import_export.export_points_csv(self.project, file_path):
                self.update_status("Points exported")
            else:
                QMessageBox.critical(self, "Error", "Failed to export points")
    
    def export_lines_csv(self):
        """Export lines to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Lines", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            if self.import_export.export_lines_csv(self.project, file_path):
                self.update_status("Lines exported")
            else:
                QMessageBox.critical(self, "Error", "Failed to export lines")
    
    def export_curves_csv(self):
        """Export curves to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Curves", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            if self.import_export.export_curves_csv(self.project, file_path):
                self.update_status("Curves exported")
            else:
                QMessageBox.critical(self, "Error", "Failed to export curves")
    
    def export_grass(self):
        """Export to GRASS ASCII format."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export GRASS ASCII", "", "All Files (*)"
        )
        if file_path:
            if self.import_export.export_grass_ascii(self.project, file_path):
                self.update_status("GRASS ASCII exported")
            else:
                QMessageBox.critical(self, "Error", "Failed to export GRASS ASCII")
    
    def export_sql(self):
        """Export to SQL insert script."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export SQL Script", "", "SQL Files (*.sql);;All Files (*)"
        )
        if file_path:
            if self.import_export.export_sql(self.project, file_path):
                self.update_status("SQL script exported")
            else:
                QMessageBox.critical(self, "Error", "Failed to export SQL script")
    
    # ==================== TOOL OPERATIONS ====================
    
    def start_calibration(self):
        """Start calibration process."""
        self.set_mode('calibration')
        self.update_status("Click two reference points on PDF")
    
    def show_line_audit(self):
        """Show line audit dialog."""
        # TODO: Implement audit dialog
        self.update_status("Line audit (to be implemented)")
    
    def validate_project(self):
        """Run project validation."""
        report = self.audit.validate_project()
        
        message = f"Validation Report:\n\n"
        message += f"Total Points: {report['total_points']}\n"
        message += f"Total Lines: {report['total_lines']}\n"
        message += f"Total Curves: {report['total_curves']}\n\n"
        message += f"Issues Found: {report['issues_found']}\n"
        message += f"  - Isolated Points: {len(report['isolated_points'])}\n"
        message += f"  - Zero-Length Lines: {len(report['zero_length_lines'])}\n"
        message += f"  - Duplicate Lines: {len(report['duplicate_lines'])}\n"
        message += f"  - Overlapping Points: {len(report['overlapping_points'])}\n"
        
        QMessageBox.information(self, "Project Validation", message)
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About 3D Maker Digitizer",
            "3D Maker Digitizer - Qt Version\n\n"
            "A tool for digitizing 3D track layouts from PDF plans.\n\n"
            "Ported to Qt for better performance and integration."
        )
    
    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts_text = """
<h3>Keyboard Shortcuts</h3>

<h4>General</h4>
<table cellpadding="5">
<tr><td><b>Ctrl+N</b></td><td>New Project</td></tr>
<tr><td><b>Ctrl+O</b></td><td>Open Project</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save Project</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Exit Application</td></tr>
<tr><td><b>F1</b></td><td>Show Keyboard Shortcuts</td></tr>
<tr><td><b>Esc</b></td><td>Cancel line drawing / Clear highlighting</td></tr>
</table>

<h4>Tab Navigation</h4>
<table cellpadding="5">
<tr><td><b>Ctrl+1</b></td><td>Switch to PDF View</td></tr>
<tr><td><b>Ctrl+2</b></td><td>Switch to 2D Editor</td></tr>
<tr><td><b>Ctrl+3</b></td><td>Switch to 3D View</td></tr>
<tr><td><b>Tab</b></td><td>Cycle through tabs</td></tr>
</table>

<h4>PDF View Modes</h4>
<table cellpadding="5">
<tr><td><b>1</b></td><td>Point placement mode</td></tr>
<tr><td><b>2</b></td><td>Line drawing mode</td></tr>
<tr><td><b>3</b></td><td>Curve drawing mode</td></tr>
</table>

<h4>2D Editor</h4>
<table cellpadding="5">
<tr><td><b>Delete</b></td><td>Delete selected item(s) in focused table</td></tr>
<tr><td><b>Ctrl+Click</b></td><td>Multi-select items</td></tr>
<tr><td><b>Shift+Click</b></td><td>Select range</td></tr>
</table>

<h4>3D View</h4>
<table cellpadding="5">
<tr><td><b>Right-click</b></td><td>Context menu for items</td></tr>
<tr><td><b>Mouse drag</b></td><td>Rotate view</td></tr>
<tr><td><b>Scroll wheel</b></td><td>Zoom in/out</td></tr>
</table>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts_text)
        msg.exec()
    
    def show_settings(self):
        """Show settings dialog."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                                     QDialogButtonBox, QGroupBox, QLabel, QSpinBox, QPushButton,
                                     QTabWidget)
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QColorDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle("View Settings")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        tabs = QTabWidget()
        
        # ===== PDF VIEW TAB =====
        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout()
        # ===== PDF VIEW TAB =====
        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout()
        
        # PDF Rendering options group
        pdf_render_group = QGroupBox("PDF View - Rendering Options")
        pdf_render_layout = QVBoxLayout()
        
        show_points_cb = QCheckBox("Show Points")
        show_points_cb.setChecked(self.show_points)
        pdf_render_layout.addWidget(show_points_cb)
        
        show_lines_cb = QCheckBox("Show Lines")
        show_lines_cb.setChecked(self.show_lines)
        pdf_render_layout.addWidget(show_lines_cb)
        
        show_curves_cb = QCheckBox("Show Curves")
        show_curves_cb.setChecked(self.show_curves)
        pdf_render_layout.addWidget(show_curves_cb)
        
        show_hidden_cb = QCheckBox("Show Hidden Objects")
        show_hidden_cb.setChecked(self.show_hidden)
        pdf_render_layout.addWidget(show_hidden_cb)
        
        pdf_render_group.setLayout(pdf_render_layout)
        pdf_layout.addWidget(pdf_render_group)
        
        # PDF Colors and Sizes group
        pdf_style_group = QGroupBox("PDF View - Colors and Line Weights")
        pdf_style_layout = QVBoxLayout()
        # PDF Colors and Sizes group
        pdf_style_group = QGroupBox("PDF View - Colors and Line Weights")
        pdf_style_layout = QVBoxLayout()
        
        # Point settings
        point_row = QHBoxLayout()
        point_row.addWidget(QLabel("Points:"))
        point_color_btn = QPushButton()
        point_color_btn.setFixedSize(50, 25)
        point_color_btn.setStyleSheet(f"background-color: rgb{self.point_color};")
        point_color = list(self.point_color)
        def change_point_color():
            color = QColorDialog.getColor(QColor(*self.point_color), dialog, "Point Color")
            if color.isValid():
                point_color[0], point_color[1], point_color[2] = color.red(), color.green(), color.blue()
                point_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        point_color_btn.clicked.connect(change_point_color)
        point_row.addWidget(point_color_btn)
        point_row.addWidget(QLabel("Size:"))
        point_size_spin = QSpinBox()
        point_size_spin.setRange(1, 200)
        point_size_spin.setValue(self.point_size)
        point_row.addWidget(point_size_spin)
        point_row.addStretch()
        pdf_style_layout.addLayout(point_row)
        
        # Line settings
        line_row = QHBoxLayout()
        line_row.addWidget(QLabel("Lines:"))
        line_color_btn = QPushButton()
        line_color_btn.setFixedSize(50, 25)
        line_color_btn.setStyleSheet(f"background-color: rgb{self.line_color};")
        line_color = list(self.line_color)
        def change_line_color():
            color = QColorDialog.getColor(QColor(*self.line_color), dialog, "Line Color")
            if color.isValid():
                line_color[0], line_color[1], line_color[2] = color.red(), color.green(), color.blue()
                line_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        line_color_btn.clicked.connect(change_line_color)
        line_row.addWidget(line_color_btn)
        line_row.addWidget(QLabel("Width:"))
        line_width_spin = QSpinBox()
        line_width_spin.setRange(1, 100)
        line_width_spin.setValue(self.line_width)
        line_row.addWidget(line_width_spin)
        line_row.addStretch()
        pdf_style_layout.addLayout(line_row)
        
        # Curve settings
        curve_row = QHBoxLayout()
        curve_row.addWidget(QLabel("Curves:"))
        curve_color_btn = QPushButton()
        curve_color_btn.setFixedSize(50, 25)
        curve_color_btn.setStyleSheet(f"background-color: rgb{self.curve_color};")
        curve_color = list(self.curve_color)
        def change_curve_color():
            color = QColorDialog.getColor(QColor(*self.curve_color), dialog, "Curve Color")
            if color.isValid():
                curve_color[0], curve_color[1], curve_color[2] = color.red(), color.green(), color.blue()
                curve_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        curve_color_btn.clicked.connect(change_curve_color)
        curve_row.addWidget(curve_color_btn)
        curve_row.addWidget(QLabel("Width:"))
        curve_width_spin = QSpinBox()
        curve_width_spin.setRange(1, 100)
        curve_width_spin.setValue(self.curve_width)
        curve_row.addWidget(curve_width_spin)
        curve_row.addStretch()
        pdf_style_layout.addLayout(curve_row)
        
        # Calibration marker settings
        calib_row = QHBoxLayout()
        calib_row.addWidget(QLabel("Calibration:"))
        calib_color_btn = QPushButton()
        calib_color_btn.setFixedSize(50, 25)
        calib_color_btn.setStyleSheet(f"background-color: rgb{self.calibration_color};")
        calib_color = list(self.calibration_color)
        def change_calib_color():
            color = QColorDialog.getColor(QColor(*self.calibration_color), dialog, "Calibration Color")
            if color.isValid():
                calib_color[0], calib_color[1], calib_color[2] = color.red(), color.green(), color.blue()
                calib_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        calib_color_btn.clicked.connect(change_calib_color)
        calib_row.addWidget(calib_color_btn)
        calib_row.addWidget(QLabel("Size:"))
        calib_size_spin = QSpinBox()
        calib_size_spin.setRange(1, 20)
        calib_size_spin.setValue(self.calibration_size)
        calib_row.addWidget(calib_size_spin)
        calib_row.addStretch()
        pdf_style_layout.addLayout(calib_row)
        
        pdf_style_group.setLayout(pdf_style_layout)
        pdf_layout.addWidget(pdf_style_group)
        
        # PDF Interaction group
        pdf_interaction_group = QWidget()
        pdf_interaction_group.setStyleSheet("QWidget { background-color: #f0f0f0; border-radius: 5px; padding: 10px; }")
        pdf_interaction_layout = QVBoxLayout()
        pdf_interaction_layout.addWidget(QLabel("<b>PDF View - Click Tolerances (pixels)</b>"))
        # PDF Interaction group
        pdf_interaction_group = QWidget()
        pdf_interaction_group.setStyleSheet("QWidget { background-color: #f0f0f0; border-radius: 5px; padding: 10px; }")
        pdf_interaction_layout = QVBoxLayout()
        pdf_interaction_layout.addWidget(QLabel("<b>PDF View - Click Tolerances (pixels)</b>"))
        
        # Point tolerance
        point_tol_row = QHBoxLayout()
        point_tol_row.addWidget(QLabel("Point:"))
        point_tol_spin = QSpinBox()
        point_tol_spin.setRange(5, 100)
        point_tol_spin.setValue(self.point_tolerance)
        point_tol_row.addWidget(point_tol_spin)
        point_tol_row.addStretch()
        pdf_interaction_layout.addLayout(point_tol_row)
        
        # Line tolerance
        line_tol_row = QHBoxLayout()
        line_tol_row.addWidget(QLabel("Line:"))
        line_tol_spin = QSpinBox()
        line_tol_spin.setRange(5, 100)
        line_tol_spin.setValue(self.line_tolerance)
        line_tol_row.addWidget(line_tol_spin)
        line_tol_row.addStretch()
        pdf_interaction_layout.addLayout(line_tol_row)
        
        # Curve tolerance
        curve_tol_row = QHBoxLayout()
        curve_tol_row.addWidget(QLabel("Curve:"))
        curve_tol_spin = QSpinBox()
        curve_tol_spin.setRange(5, 100)
        curve_tol_spin.setValue(self.curve_tolerance)
        curve_tol_row.addWidget(curve_tol_spin)
        curve_tol_row.addStretch()
        pdf_interaction_layout.addLayout(curve_tol_row)
        
        pdf_interaction_group.setLayout(pdf_interaction_layout)
        pdf_layout.addWidget(pdf_interaction_group)
        
        pdf_tab.setLayout(pdf_layout)
        tabs.addTab(pdf_tab, "PDF View")
        
        # ===== 3D VIEW TAB =====
        view3d_tab = QWidget()
        view3d_layout = QVBoxLayout()
        
        # 3D Colors and Sizes group
        view3d_style_group = QGroupBox("3D View - Colors and Radii")
        view3d_style_layout = QVBoxLayout()
        
        # 3D Point settings
        view3d_point_row = QHBoxLayout()
        view3d_point_row.addWidget(QLabel("Points:"))
        view3d_point_color_btn = QPushButton()
        view3d_point_color_btn.setFixedSize(50, 25)
        # Use 3D viewer's point color
        view3d_point_color_rgb = self.viewer_3d.point_color
        view3d_point_color_btn.setStyleSheet(f"background-color: rgb{view3d_point_color_rgb};")
        view3d_point_color = list(view3d_point_color_rgb)
        def change_view3d_point_color():
            color = QColorDialog.getColor(QColor(*view3d_point_color_rgb), dialog, "3D Point Color")
            if color.isValid():
                view3d_point_color[0], view3d_point_color[1], view3d_point_color[2] = color.red(), color.green(), color.blue()
                view3d_point_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        view3d_point_color_btn.clicked.connect(change_view3d_point_color)
        view3d_point_row.addWidget(view3d_point_color_btn)
        view3d_point_row.addWidget(QLabel("Radius:"))
        view3d_point_radius_spin = QSpinBox()
        view3d_point_radius_spin.setRange(1, 200)
        view3d_point_radius_spin.setValue(int(self.viewer_3d.point_radius))
        view3d_point_row.addWidget(view3d_point_radius_spin)
        view3d_point_row.addStretch()
        view3d_style_layout.addLayout(view3d_point_row)
        
        # 3D Line settings
        view3d_line_row = QHBoxLayout()
        view3d_line_row.addWidget(QLabel("Lines:"))
        view3d_line_color_btn = QPushButton()
        view3d_line_color_btn.setFixedSize(50, 25)
        view3d_line_color_rgb = self.viewer_3d.line_color
        view3d_line_color_btn.setStyleSheet(f"background-color: rgb{view3d_line_color_rgb};")
        view3d_line_color = list(view3d_line_color_rgb)
        def change_view3d_line_color():
            color = QColorDialog.getColor(QColor(*view3d_line_color_rgb), dialog, "3D Line Color")
            if color.isValid():
                view3d_line_color[0], view3d_line_color[1], view3d_line_color[2] = color.red(), color.green(), color.blue()
                view3d_line_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
        view3d_line_color_btn.clicked.connect(change_view3d_line_color)
        view3d_line_row.addWidget(view3d_line_color_btn)
        view3d_line_row.addWidget(QLabel("Radius:"))
        view3d_line_radius_spin = QSpinBox()
        view3d_line_radius_spin.setRange(1, 100)
        view3d_line_radius_spin.setValue(int(self.viewer_3d.line_radius))
        view3d_line_row.addWidget(view3d_line_radius_spin)
        view3d_line_row.addStretch()
        view3d_style_layout.addLayout(view3d_line_row)
        
        view3d_style_group.setLayout(view3d_style_layout)
        view3d_layout.addWidget(view3d_style_group)
        
        view3d_tab.setLayout(view3d_layout)
        tabs.addTab(view3d_tab, "3D View")
        
        layout.addWidget(tabs)
        
        # Function to apply settings
        def apply_settings():
            # Apply PDF view settings
            self.show_points = show_points_cb.isChecked()
            self.show_lines = show_lines_cb.isChecked()
            self.show_curves = show_curves_cb.isChecked()
            self.show_hidden = show_hidden_cb.isChecked()
            
            # Apply PDF color and size settings
            self.point_color = tuple(point_color)
            self.point_size = point_size_spin.value()
            self.line_color = tuple(line_color)
            self.line_width = line_width_spin.value()
            self.curve_color = tuple(curve_color)
            self.curve_width = curve_width_spin.value()
            self.calibration_color = tuple(calib_color)
            self.calibration_size = calib_size_spin.value()
            
            # Apply tolerance settings
            self.point_tolerance = point_tol_spin.value()
            self.line_tolerance = line_tol_spin.value()
            self.curve_tolerance = curve_tol_spin.value()
            
            # Update PDF viewer settings
            self.pdf_viewer.set_render_settings(
                point_color=self.point_color,
                point_size=self.point_size,
                line_color=self.line_color,
                line_width=self.line_width,
                curve_color=self.curve_color,
                curve_width=self.curve_width,
                calibration_color=self.calibration_color,
                calibration_size=self.calibration_size,
                point_tolerance=self.point_tolerance,
                line_tolerance=self.line_tolerance,
                curve_tolerance=self.curve_tolerance
            )
            
            # Update 3D viewer settings
            self.viewer_3d.set_render_settings(
                point_color=tuple(view3d_point_color),
                point_radius=float(view3d_point_radius_spin.value()),
                line_color=tuple(view3d_line_color),
                line_radius=float(view3d_line_radius_spin.value())
            )
            
            # Refresh displays
            self._refresh_pdf_markers()
            self.viewer_3d.refresh()
            self.update_status("Settings updated")
        
        # Button box with Apply button
        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Apply)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(apply_settings)
        buttons.accepted.connect(lambda: (apply_settings(), dialog.accept()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Project has unsaved changes. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        event.accept()
    
    # ==================== INTERNAL HANDLERS ====================
    
    def _handle_pdf_click(self, canvas_x: float, canvas_y: float, pdf_x: float, pdf_y: float):
        """Handle clicks on the PDF viewer."""
        if self.current_mode == 'calibration':
            self._handle_calibration_click(pdf_x, pdf_y)
        elif self.current_mode == 'coordinates':
            self._handle_coordinate_click(pdf_x, pdf_y)
        elif self.current_mode == 'lines':
            self._handle_line_click(pdf_x, pdf_y)
        elif self.current_mode == 'curves':
            self._handle_curve_click(pdf_x, pdf_y)
    
    def _handle_calibration_click(self, pdf_x: float, pdf_y: float):
        """Handle calibration mode clicks."""
        if len(self.project.reference_points_pdf) < 2:
            self.project.reference_points_pdf.append((pdf_x, pdf_y))
            self.pdf_viewer.add_calibration_marker(pdf_x, pdf_y)
            
            if len(self.project.reference_points_pdf) == 2:
                # Prompt for real-world coordinates
                from PyQt6.QtWidgets import QInputDialog
                
                for i in range(2):
                    x, ok1 = QInputDialog.getDouble(
                        self, f"Reference Point {i+1}", 
                        f"Enter real X coordinate for point {i+1}:"
                    )
                    if not ok1:
                        self.project.reference_points_pdf.clear()
                        self.pdf_viewer.clear_calibration_markers()
                        return
                    
                    y, ok2 = QInputDialog.getDouble(
                        self, f"Reference Point {i+1}",
                        f"Enter real Y coordinate for point {i+1}:"
                    )
                    if not ok2:
                        self.project.reference_points_pdf.clear()
                        self.pdf_viewer.clear_calibration_markers()
                        return
                    
                    self.project.reference_points_real.append((x, y))
                
                # Calculate transformation
                if self.geometry.calculate_transformation(
                    self.project.reference_points_pdf,
                    self.project.reference_points_real
                ):
                    self.project.transformation_matrix = self.geometry.transformation_matrix
                    self.update_status("Calibration successful!")
                    self.set_mode('coordinates')
                else:
                    QMessageBox.warning(self, "Calibration Failed", 
                                      "Could not calculate transformation")
                    self.project.reference_points_pdf.clear()
                    self.project.reference_points_real.clear()
                    self.pdf_viewer.clear_calibration_markers()
    
    def _handle_coordinate_click(self, pdf_x: float, pdf_y: float):
        """Handle coordinate creation mode clicks."""
        try:
            z_value = float(self.z_input.text())
        except ValueError:
            z_value = 0.0
        
        point = self.operations.create_point(pdf_x, pdf_y, z_value)
        self._refresh_all_views()
        self.update_status(f"Created point {point.id}")
    
    def _handle_line_click(self, pdf_x: float, pdf_y: float):
        """Handle line creation mode clicks."""
        # Find closest point
        point = self._find_closest_point(pdf_x, pdf_y, tolerance=10.0)
        if not point:
            self.update_status("No point found at click location")
            return
        
        if not hasattr(self, '_line_start_point'):
            self._line_start_point = point.id
            self.update_status(f"Line start: point {point.id}. Click end point.")
        else:
            line = self.operations.create_line(self._line_start_point, point.id)
            if line:
                self._refresh_all_views()
                self.update_status(f"Created line {line.id}")
            else:
                self.update_status("Failed to create line (same start/end or invalid points)")
            del self._line_start_point
    
    def _handle_curve_click(self, pdf_x: float, pdf_y: float):
        """Handle curve creation mode clicks."""
        point = self._find_closest_point(pdf_x, pdf_y, tolerance=10.0)
        if not point:
            self.update_status("No point found at click location")
            return
        
        if not hasattr(self, '_curve_points'):
            self._curve_points = []
        
        self._curve_points.append(point.id)
        
        if len(self._curve_points) == 1:
            self.update_status(f"Curve start: point {point.id}. Click center point.")
        elif len(self._curve_points) == 2:
            self.update_status(f"Curve center: point {point.id}. Click end point.")
        elif len(self._curve_points) == 3:
            curve = self.operations.create_curve(
                self._curve_points[0], self._curve_points[2], self._curve_points[1]
            )
            if curve:
                self._refresh_all_views()
                self.update_status(f"Created curve {curve.id}")
            else:
                self.update_status("Failed to create curve")
            del self._curve_points
    
    def _find_closest_point(self, pdf_x: float, pdf_y: float, tolerance: float = 10.0):
        """Find the closest point to PDF coordinates within tolerance."""
        closest = None
        min_dist = tolerance
        
        for point in self.project.points:
            if point.hidden:
                continue
            dx = point.pdf_x - pdf_x
            dy = point.pdf_y - pdf_y
            dist = (dx*dx + dy*dy) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                closest = point
        
        return closest
    
    def _refresh_pdf_markers(self):
        """Refresh all markers on the PDF."""
        self.pdf_viewer.clear_point_markers()
        
        # Add points based on settings
        if self.show_points:
            for point in self.project.points:
                if self.show_hidden or not point.hidden:
                    self.pdf_viewer.add_point_marker(point.id, point.pdf_x, point.pdf_y)
        
        # Add lines with IDs based on settings
        line_segments = []
        if self.show_lines:
            for line in self.project.lines:
                if self.show_hidden or not line.hidden:
                    start = self.project.get_point(line.start_id)
                    end = self.project.get_point(line.end_id)
                    if start and end:
                        line_segments.append((line.id, start.pdf_x, start.pdf_y, end.pdf_x, end.pdf_y))
        self.pdf_viewer.set_lines(line_segments)
        
        # Add curves with IDs based on settings
        curve_polylines = []
        if self.show_curves:
            for curve in self.project.curves:
                if self.show_hidden or not curve.hidden:
                    start = self.project.get_point(curve.start_id)
                    end = self.project.get_point(curve.end_id)
                    if start and end:
                        # Use arc_points_real but need to map back to PDF coordinates
                        # For now, just draw line from start to end
                        curve_polylines.append((curve.id, [(start.pdf_x, start.pdf_y), (end.pdf_x, end.pdf_y)]))
        self.pdf_viewer.set_curves(curve_polylines)
        
        # Render once after all markers added
        self.pdf_viewer.refresh_markers()
    
    def _refresh_all_views(self):
        """Refresh all views (PDF, editor and 3D)."""
        self._refresh_pdf_markers()
        self.editor.refresh()
        self.viewer_3d.refresh()
    
    def _find_or_create_point_at_z(self, original_point_id: int, new_z: float) -> int:
        """Find existing point at same X,Y with new Z, or create new one."""
        orig_point = self.project.get_point(original_point_id)
        if not orig_point:
            return None
        
        # Search for existing point at this X,Y,Z
        for point in self.project.points:
            if (abs(point.real_x - orig_point.real_x) < 0.01 and 
                abs(point.real_y - orig_point.real_y) < 0.01 and
                abs(point.z - new_z) < 0.01):
                return point.id
        
        # No existing point, create new one
        new_point = self.operations.duplicate_point(orig_point, new_z)
        self.pdf_viewer.add_point_marker(new_point.id, new_point.pdf_x, new_point.pdf_y)
        return new_point.id
    
    def _duplicate_point(self, point_id: int):
        """Duplicate a point at one or more Z values (comma-delimited)."""
        from PyQt6.QtWidgets import QInputDialog
        
        point = self.project.get_point(point_id)
        if not point:
            return
        
        z_input, ok = QInputDialog.getText(
            self, "Duplicate Point",
            f"Enter Z value(s) for duplicated point(s) (comma-separated):",
            text=self.last_z_levels
        )
        if ok and z_input.strip():
            # Remember the input for next time
            self.last_z_levels = z_input.strip()
            
            # Parse comma-delimited values
            z_values = []
            for z_str in z_input.split(','):
                z_str = z_str.strip()
                if z_str:
                    try:
                        z_values.append(float(z_str))
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Input", 
                                          f"'{z_str}' is not a valid number. Skipping.")
            
            if not z_values:
                return
            
            # Create duplicates
            new_points = []
            for z_value in z_values:
                new_point = self.operations.duplicate_point(point, z_value)
                self.pdf_viewer.add_point_marker(new_point.id, new_point.pdf_x, new_point.pdf_y)
                new_points.append(new_point)
            
            self.pdf_viewer.refresh_markers()
            self._refresh_all_views()
            
            if len(new_points) == 1:
                self.update_status(f"Created point {new_points[0].id} (duplicate of {point_id})")
            else:
                point_ids = ", ".join([str(p.id) for p in new_points])
                self.update_status(f"Created {len(new_points)} points ({point_ids}) as duplicates of {point_id}")
    
    def _identify_point(self, point_id: int):
        """Show information about a point."""
        point = self.project.get_point(point_id)
        if not point:
            QMessageBox.warning(self, "Point Not Found", f"Point {point_id} not found.")
            return
        
        # Get references
        refs = self.audit.get_point_references(point_id)
        total_refs = (len(refs['lines_start']) + len(refs['lines_end']) + 
                     len(refs['curves_start']) + len(refs['curves_end']) + len(refs['curves_arc']))
        
        message = f"Point {point.id} Information:\n\n"
        message += f"Real Coordinates:\n"
        message += f"  X: {int(point.real_x)}\n"
        message += f"  Y: {int(point.real_y)}\n"
        message += f"  Z: {int(point.z)}\n\n"
        message += f"PDF Coordinates:\n"
        message += f"  X: {int(point.pdf_x)}\n"
        message += f"  Y: {int(point.pdf_y)}\n\n"
        message += f"Description: {point.description or '(none)'}\n"
        message += f"Hidden: {'Yes' if point.hidden else 'No'}\n\n"
        message += f"Total References: {total_refs}\n"
        
        if total_refs > 0:
            message += "\nUsed in:\n"
            if refs['lines_start']:
                message += f"  - {len(refs['lines_start'])} line(s) as start point\n"
            if refs['lines_end']:
                message += f"  - {len(refs['lines_end'])} line(s) as end point\n"
            if refs['curves_start']:
                message += f"  - {len(refs['curves_start'])} curve(s) as start point\n"
            if refs['curves_end']:
                message += f"  - {len(refs['curves_end'])} curve(s) as end point\n"
            if refs['curves_arc']:
                message += f"  - {len(refs['curves_arc'])} curve(s) as arc point\n"
        
        QMessageBox.information(self, f"Point {point_id}", message)
    
    def _identify_line(self, line_id: int):
        """Show information about a line."""
        line = self.project.get_line(line_id)
        if not line:
            QMessageBox.warning(self, "Line Not Found", f"Line {line_id} not found.")
            return
        
        start_point = self.project.get_point(line.start_id)
        end_point = self.project.get_point(line.end_id)
        
        message = f"Line {line.id} Information:\n\n"
        message += f"Start Point: {line.start_id}\n"
        if start_point:
            message += f"  Real: ({int(start_point.real_x)}, {int(start_point.real_y)}, {int(start_point.z)})\n"
        message += f"\nEnd Point: {line.end_id}\n"
        if end_point:
            message += f"  Real: ({int(end_point.real_x)}, {int(end_point.real_y)}, {int(end_point.z)})\n"
        
        message += f"\nDescription: {line.description or '(none)'}\n"
        message += f"Hidden: {'Yes' if line.hidden else 'No'}\n"
        
        # Check if used as base for any curve
        curves_using_this_line = [c for c in self.project.curves if hasattr(c, 'base_line_id') and c.base_line_id == line_id]
        if curves_using_this_line:
            message += f"\nUsed as base for {len(curves_using_this_line)} curve(s): "
            message += ", ".join([str(c.id) for c in curves_using_this_line])
        
        QMessageBox.information(self, f"Line {line_id}", message)
    
    def _identify_curve(self, curve_id: int):
        """Show information about a curve."""
        curve = self.project.get_curve(curve_id)
        if not curve:
            QMessageBox.warning(self, "Curve Not Found", f"Curve {curve_id} not found.")
            return
        
        start_point = self.project.get_point(curve.start_id)
        end_point = self.project.get_point(curve.end_id)
        
        message = f"Curve {curve.id} Information:\n\n"
        message += f"Start Point: {curve.start_id}\n"
        if start_point:
            message += f"  Real: ({int(start_point.real_x)}, {int(start_point.real_y)}, {int(start_point.z)})\n"
        message += f"\nEnd Point: {curve.end_id}\n"
        if end_point:
            message += f"  Real: ({int(end_point.real_x)}, {int(end_point.real_y)}, {int(end_point.z)})\n"
        
        message += f"\nArc Points: {len(curve.arc_point_ids)}\n"
        if curve.arc_point_ids:
            message += "  IDs: " + ", ".join([str(pid) for pid in curve.arc_point_ids]) + "\n"
        
        message += f"\nDescription: {curve.description or '(none)'}\n"
        message += f"Hidden: {'Yes' if curve.hidden else 'No'}\n"
        
        QMessageBox.information(self, f"Curve {curve_id}", message)
    
    def _delete_point(self, point_id: int):
        """Delete a point, with option to cascade delete connected lines and orphaned points."""
        # First check if this point is an arc point of any curve
        parent_curves = []
        for curve in self.project.curves:
            if curve.arc_point_ids and point_id in curve.arc_point_ids:
                parent_curves.append(curve)
        
        if parent_curves:
            # This is an arc point - delete the entire curve(s) without prompting
            for curve in parent_curves:
                self._delete_curve(curve.id)
            return
        
        # Check if point is referenced
        ref_count = self.project.count_point_references(point_id)
        
        if ref_count > 0:
            # Point is referenced - perform cascade delete without confirmation
            self._cascade_delete_point(point_id)
        else:
            # Point is not referenced - simple delete
            success, msg = self.operations.delete_point(point_id, force=False)
            if success:
                self.pdf_viewer.remove_point_marker(point_id)
                self._refresh_all_views()
            else:
                self.update_status(msg)
    
    def _cascade_delete_point(self, point_id: int):
        """Delete a point and cascade delete connected lines and orphaned endpoints."""
        # Find all lines connected to this point
        connected_lines = []
        other_endpoints = set()
        
        for line in self.project.lines:
            if line.start_id == point_id or line.end_id == point_id:
                connected_lines.append(line)
                # Track the other endpoint
                if line.start_id == point_id:
                    other_endpoints.add(line.end_id)
                else:
                    other_endpoints.add(line.start_id)
        
        # Find all curves connected to this point
        connected_curves = []
        for curve in self.project.curves:
            if curve.start_id == point_id or curve.end_id == point_id:
                connected_curves.append(curve)
                # Track the other endpoint
                if curve.start_id == point_id:
                    other_endpoints.add(curve.end_id)
                else:
                    other_endpoints.add(curve.start_id)
        
        # Delete the point (force=True to override reference check)
        success, msg = self.operations.delete_point(point_id, force=True)
        if not success:
            self.update_status(msg)
            return
        
        deleted_items = [f"Point {point_id}"]
        
        # Delete connected lines
        for line in connected_lines:
            success, _ = self.operations.delete_line(line.id)
            if success:
                deleted_items.append(f"Line {line.id}")
        
        # Delete connected curves (don't remove orphans yet - we'll do it manually)
        for curve in connected_curves:
            success, _ = self.operations.delete_curve(curve.id, remove_orphans=False)
            if success:
                deleted_items.append(f"Curve {curve.id}")
        
        # Check each other endpoint - delete if now orphaned
        for endpoint_id in other_endpoints:
            if endpoint_id == point_id:
                continue
            ref_count = self.project.count_point_references(endpoint_id)
            if ref_count == 0:
                success, _ = self.operations.delete_point(endpoint_id, force=True)
                if success:
                    deleted_items.append(f"Point {endpoint_id} (orphaned)")
        
        # Refresh views
        self.pdf_viewer.remove_point_marker(point_id)
        self._refresh_all_views()
        
        # Show summary in status bar (no modal dialogs)
        summary = "Deleted: " + ", ".join(deleted_items)
        self.update_status(summary)
    
    def _duplicate_line(self, line_id: int):
        """Duplicate a line at new Z level(s)."""
        line = self.project.get_line(line_id)
        if not line:
            QMessageBox.warning(self, "Line Not Found", f"Line {line_id} not found.")
            return
        
        # Get start and end points
        start_point = self.project.get_point(line.start_id)
        end_point = self.project.get_point(line.end_id)
        if not start_point or not end_point:
            QMessageBox.warning(self, "Invalid Line", "Line has missing endpoints.")
            return
        
        # Check if this line is a base for any curve
        curves_using_line = [c for c in self.project.curves if hasattr(c, 'base_line_id') and c.base_line_id == line_id]
        
        if curves_using_line:
            # This is a curve base line - duplicate the entire curve
            QMessageBox.information(self, "Curve Base Line", 
                f"This line is the base for curve {curves_using_line[0].id}. The entire curve will be duplicated.")
            self._duplicate_curve(curves_using_line[0].id)
            return
        
        # Ask for Z levels
        from PyQt6.QtWidgets import QInputDialog
        z_input, ok = QInputDialog.getText(
            self, "Duplicate Line",
            f"Enter Z level(s) for new line (comma-separated)\\n"
            f"Original line at Z: {start_point.z}, {end_point.z}",
            text=self.last_z_levels
        )
        
        if not ok or not z_input.strip():
            return
        
        # Remember for next time
        self.last_z_levels = z_input.strip()
        
        # Parse Z levels
        try:
            z_levels = [float(z.strip()) for z in z_input.split(',')]
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers separated by commas.")
            return
        
        # Duplicate line at each Z level
        created_lines = []
        for new_z in z_levels:
            # Find or create points at new Z level
            new_start_id = self._find_or_create_point_at_z(line.start_id, new_z)
            new_end_id = self._find_or_create_point_at_z(line.end_id, new_z)
            
            if new_start_id and new_end_id:
                new_line = self.operations.create_line(new_start_id, new_end_id)
                if new_line:
                    new_line.description = f"{line.description} (Z={new_z})" if line.description else f"Z={new_z}"
                    new_line.hidden = line.hidden
                    created_lines.append(new_line.id)
        
        if created_lines:
            self.pdf_viewer.refresh_markers()
            self._refresh_all_views()
            self.update_status(f"Created {len(created_lines)} line(s) at Z levels: {', '.join(map(str, z_levels))}")
        else:
            QMessageBox.warning(self, "Duplicate Failed", "Failed to create duplicate lines.")
    
    def _delete_line(self, line_id: int):
        """Delete a line."""
        success, msg = self.operations.delete_line(line_id)
        if success:
            self._refresh_pdf_markers()
            self._refresh_all_views()
            self.update_status(msg)
        else:
            QMessageBox.warning(self, "Cannot Delete", msg)
    
    def _delete_points(self, point_ids: list):
        """Delete multiple points (optimized bulk delete)."""
        # Perform bulk deletion via operations to avoid repeated scans
        try:
            deleted_count, deleted_items = self.operations.delete_points_bulk(point_ids)
        except Exception:
            # Fallback to previous behavior if bulk deletion fails
            deleted_count = 0
            deleted_items = []
            for point_id in point_ids:
                if self.project.get_point(point_id):
                    self._cascade_delete_point(point_id)
                    deleted_count += 1

        # Refresh UI once
        self._refresh_pdf_markers()
        self._refresh_all_views()
        if deleted_count > 0:
            self.update_status(f"Deleted {deleted_count} point(s)")
    
    def _delete_lines(self, line_ids: list):
        """Delete multiple lines."""
        # Delete multiple lines without confirmation
        
        deleted_count = 0
        for line_id in line_ids:
            success, _ = self.operations.delete_line(line_id)
            if success:
                deleted_count += 1
        
        self._refresh_pdf_markers()
        self._refresh_all_views()
        self.update_status(f"Deleted {deleted_count} line(s)")
    
    def _delete_curves(self, curve_ids: list):
        """Delete multiple curves."""
        # Delete multiple curves without confirmation
        
        deleted_count = 0
        for curve_id in curve_ids:
            # Check if curve still exists
            curve = self.project.get_curve(curve_id)
            if curve:
                # Delete via the single curve method which handles base line cleanup
                base_line_id = curve.base_line_id
                
                # Delete base line first
                if base_line_id:
                    self.operations.delete_line(base_line_id)
                
                # Delete curve
                success, _ = self.operations.delete_curve(curve_id, remove_orphans=True)
                if success:
                    deleted_count += 1
        
        self._refresh_pdf_markers()
        self._refresh_all_views()
        self.update_status(f"Deleted {deleted_count} curve(s)")
    
    def _create_line_from_3d(self, start_id: int, end_id: int):
        """Create a line between two points from 3D view."""
        # Check if either point is an arc point (intermediate point, NOT an endpoint) of any curve
        for point_id in [start_id, end_id]:
            for curve in self.project.curves:
                # Allow endpoints, block only intermediate arc points
                if point_id in curve.arc_point_ids and point_id != curve.start_id and point_id != curve.end_id:
                    QMessageBox.warning(self, "Invalid Point", 
                        f"Cannot create line to/from Point {point_id} - it is an arc point of Curve {curve.id}.")
                    return
        
        # Check if line already exists
        for line in self.project.lines:
            if (line.start_id == start_id and line.end_id == end_id) or \
               (line.start_id == end_id and line.end_id == start_id):
                QMessageBox.information(self, "Line Exists", 
                    f"A line already exists between Point {start_id} and Point {end_id}.")
                return
        
        # Get the points
        start_point = self.project.get_point(start_id)
        end_point = self.project.get_point(end_id)
        
        if not start_point or not end_point:
            QMessageBox.warning(self, "Invalid Points", "One or both points not found.")
            return
        
        # Create the line
        new_line = self.operations.create_line(start_id, end_id)
        
        # Refresh all views
        self._refresh_all_views()
        self.update_status(f"Created line {new_line.id} from Point {start_id} to Point {end_id}")
    
    def _trace_from_line(self, line_id: int):
        """Trace connectivity from a line's start point and highlight the path."""
        line = self.project.get_line(line_id)
        if not line:
            QMessageBox.warning(self, "Line Not Found", f"Line {line_id} not found.")
            return
        
        # Use the start point of the line for tracing
        start_point_id = line.start_id
        start_point = self.project.get_point(start_point_id)
        
        if not start_point:
            QMessageBox.warning(self, "Point Not Found", f"Start point {start_point_id} not found.")
            return
        
        # Perform directional trace (only follows start->end direction)
        trace_result = self.audit.trace_directional(start_point_id)
        
        # Highlight the traced path in PDF viewer
        self.pdf_viewer.set_highlighted(
            points=trace_result['points'],
            lines=trace_result['lines'],
            curves=trace_result['curves']
        )
        
        # Also highlight in 3D viewer
        self.viewer_3d.set_highlighted(
            points=trace_result['points'],
            lines=trace_result['lines'],
            curves=trace_result['curves']
        )
        
        # Update status with trace info
        msg = f"Traced from Line {line_id}: {len(trace_result['points'])} points, "
        msg += f"{len(trace_result['lines'])} lines, {len(trace_result['curves'])} curves"
        if trace_result['endpoints']:
            msg += f", {len(trace_result['endpoints'])} endpoints"
        self.update_status(msg)
    
    def _reverse_line(self, line_id: int):
        """Reverse the direction of a line by swapping start and end points."""
        line = self.project.get_line(line_id)
        if not line:
            QMessageBox.warning(self, "Line Not Found", f"Line {line_id} not found.")
            return
        
        # Swap start and end
        line.start_id, line.end_id = line.end_id, line.start_id
        self.project.modified = True
        
        # Refresh all views to show updated arrow direction
        self._refresh_all_views()
        self.update_status(f"Reversed direction of Line {line_id}")
    
    def _reverse_curve(self, curve_id: int):
        """Reverse the direction of a curve by swapping start/end and reversing arc points."""
        curve = self.project.get_curve(curve_id)
        if not curve:
            QMessageBox.warning(self, "Curve Not Found", f"Curve {curve_id} not found.")
            return
        
        # Swap start and end points
        curve.start_id, curve.end_id = curve.end_id, curve.start_id
        
        # Reverse the arc_point_ids list (intermediate points)
        curve.arc_point_ids = list(reversed(curve.arc_point_ids))
        
        # Reverse the arc_points_real list (interpolated coordinates)
        curve.arc_points_real = list(reversed(curve.arc_points_real))
        
        # If there's a base line, reverse it too
        if curve.base_line_id:
            base_line = self.project.get_line(curve.base_line_id)
            if base_line:
                base_line.start_id, base_line.end_id = base_line.end_id, base_line.start_id
        
        self.project.modified = True
        
        # Refresh all views
        self._refresh_all_views()
        self.update_status(f"Reversed direction of Curve {curve_id}")
    
    def _clear_highlighting(self):
        """Clear all highlighting from PDF and 3D viewers."""
        self.pdf_viewer.clear_highlighted()
        self.viewer_3d.clear_highlighted()
        self.update_status("Highlighting cleared")
    
    def _duplicate_curve(self, curve_id: int):
        """Duplicate a curve at new Z level(s)."""
        curve = self.project.get_curve(curve_id)
        if not curve:
            QMessageBox.warning(self, "Curve Not Found", f"Curve {curve_id} not found.")
            return
        
        # Get all points in the curve
        start_point = self.project.get_point(curve.start_id)
        end_point = self.project.get_point(curve.end_id)
        if not start_point or not end_point:
            QMessageBox.warning(self, "Invalid Curve", "Curve has missing endpoints.")
            return
        
        # Ask for Z levels
        from PyQt6.QtWidgets import QInputDialog
        z_input, ok = QInputDialog.getText(
            self, "Duplicate Curve",
            f"Enter Z level(s) for new curve (comma-separated)\\n"
            f"Original curve at Z: {start_point.z}",
            text=self.last_z_levels
        )
        
        if not ok or not z_input.strip():
            return
        
        # Remember for next time
        self.last_z_levels = z_input.strip()
        
        # Parse Z levels
        try:
            z_levels = [float(z.strip()) for z in z_input.split(',')]
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers separated by commas.")
            return
        
        # Get base line if it exists
        base_line = None
        for line in self.project.lines:
            if ((line.start_id == curve.start_id and line.end_id == curve.end_id) or
                (line.start_id == curve.end_id and line.end_id == curve.start_id)):
                base_line = line
                break
        
        # Duplicate curve at each Z level
        created_curves = []
        for new_z in z_levels:
            # Find or create all points at new Z level
            new_start_id = self._find_or_create_point_at_z(curve.start_id, new_z)
            new_end_id = self._find_or_create_point_at_z(curve.end_id, new_z)
            
            # Find or create arc points at new Z level
            new_arc_ids = []
            for arc_id in curve.arc_point_ids:
                new_arc_id = self._find_or_create_point_at_z(arc_id, new_z)
                if new_arc_id:
                    new_arc_ids.append(new_arc_id)
            
            if not new_start_id or not new_end_id or not new_arc_ids:
                continue
            
            # Create base line at new Z level if original had one
            new_base_line = None
            if base_line:
                new_base_line = self.operations.create_line(new_start_id, new_end_id)
                if new_base_line:
                    new_base_line.description = f"{base_line.description} (Z={new_z})" if base_line.description else f"Z={new_z}"
                    new_base_line.hidden = base_line.hidden
            
            # Create the curve - use first arc point as center (original center point)
            center_id = new_arc_ids[0]
            new_curve = self.operations.create_curve(new_start_id, new_end_id, center_id)
            
            if new_curve:
                # Update arc_point_ids to include all duplicated arc points
                new_curve.arc_point_ids = new_arc_ids
                
                new_curve.description = f"{curve.description} (Z={new_z})" if curve.description else f"Z={new_z}"
                new_curve.hidden = curve.hidden
                if new_base_line:
                    new_curve.base_line_id = new_base_line.id
                created_curves.append(new_curve.id)
        
        if created_curves:
            self.pdf_viewer.refresh_markers()
            self._refresh_all_views()
            self.update_status(f"Created {len(created_curves)} curve(s) at Z levels: {', '.join(map(str, z_levels))}")
        else:
            QMessageBox.warning(self, "Duplicate Failed", "Failed to create duplicate curves.")
            QMessageBox.warning(self, "Duplicate Failed", "Failed to create duplicate curve.")
    
    def _delete_curve(self, curve_id: int):
        """Delete a curve, including its base line and arc points."""
        curve = self.project.get_curve(curve_id)
        if not curve:
            QMessageBox.warning(self, "Curve Not Found", f"Curve {curve_id} not found.")
            return
        
        # Get the base line ID before deleting the curve
        base_line_id = curve.base_line_id
        
        deleted_items = [f"Curve {curve_id}"]
        
        # Delete the base line FIRST if it exists
        # This orphans the arc points so they can be cleaned up when we delete the curve
        if base_line_id:
            line_success, _ = self.operations.delete_line(base_line_id)
            if line_success:
                deleted_items.append(f"Base Line {base_line_id}")
        
        # Now delete the curve (this will delete arc points now that they're orphaned)
        success, msg = self.operations.delete_curve(curve_id, remove_orphans=True)
        if success:
            self._refresh_pdf_markers()
            self._refresh_all_views()
            
            summary = "Deleted: " + ", ".join(deleted_items)
            self.update_status(summary)
        else:
            QMessageBox.warning(self, "Cannot Delete", msg)
    
    def _show_point_references(self, point_id: int):
        """Show all references to a point."""
        refs = self.audit.get_point_references(point_id)
        
        message = f"References for Point {point_id}:\n\n"
        
        if refs['lines_start']:
            message += "Lines (as start point):\n"
            for line in refs['lines_start']:
                message += f"  Line {line.id}: {line.start_id} → {line.end_id}\n"
            message += "\n"
        
        if refs['lines_end']:
            message += "Lines (as end point):\n"
            for line in refs['lines_end']:
                message += f"  Line {line.id}: {line.start_id} → {line.end_id}\n"
            message += "\n"
        
        if refs['curves_start']:
            message += "Curves (as start point):\n"
            for curve in refs['curves_start']:
                message += f"  Curve {curve.id}: {curve.start_id} → {curve.end_id}\n"
            message += "\n"
        
        if refs['curves_end']:
            message += "Curves (as end point):\n"
            for curve in refs['curves_end']:
                message += f"  Curve {curve.id}: {curve.start_id} → {curve.end_id}\n"
            message += "\n"
        
        if refs['curves_arc']:
            message += "Curves (as arc point):\n"
            for curve in refs['curves_arc']:
                message += f"  Curve {curve.id}\n"
            message += "\n"
        
        total = (len(refs['lines_start']) + len(refs['lines_end']) + 
                len(refs['curves_start']) + len(refs['curves_end']) + len(refs['curves_arc']))
        
        if total == 0:
            message += "No references found."
        
        QMessageBox.information(self, f"Point {point_id} References", message)
    
    def _autoload_project(self):
        """Auto-load calibrated.dig if it exists."""
        autoload_path = Path("calibrated.dig")
        if autoload_path.exists():
            try:
                if self.import_export.load_project(self.project, str(autoload_path)):
                    self.geometry.transformation_matrix = self.project.transformation_matrix
                    self.operations = Operations(self.project, self.geometry)
                    self.audit = LineAudit(self.project)
                    
                    # Update UI
                    if self.project.pdf_path and Path(self.project.pdf_path).exists():
                        if self.pdf_viewer.load_pdf(self.project.pdf_path):
                            # Add calibration markers
                            if self.project.reference_points_pdf:
                                self.pdf_viewer.clear_calibration_markers()
                                for pt in self.project.reference_points_pdf:
                                    self.pdf_viewer.add_calibration_marker(pt[0], pt[1])
                    
                    self._refresh_pdf_markers()
                    self._refresh_all_views()
                    
                    # Set mode based on project state
                    if self.project.transformation_matrix is not None:
                        self.set_mode('coordinates')
                    
                    self.update_status(f"Auto-loaded: {autoload_path.name} ({len(self.project.points)} points, {len(self.project.lines)} lines, {len(self.project.curves)} curves)")
                    self.project_loaded.emit()
            except Exception as e:
                # Silently fail auto-load, user can manually open if needed
                print(f"Auto-load failed: {e}")
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()
        
        # Tab navigation (Ctrl+1/2/3)
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_1:
                self.tabs.setCurrentIndex(0)  # PDF View
                return
            elif key == Qt.Key.Key_2:
                self.tabs.setCurrentIndex(1)  # 2D Editor
                return
            elif key == Qt.Key.Key_3:
                self.tabs.setCurrentIndex(2)  # 3D View
                return
        
        # PDF Mode shortcuts (1/2/3 without modifiers, only in PDF view)
        if self.tabs.currentIndex() == 0 and modifiers == Qt.KeyboardModifier.NoModifier:
            if key == Qt.Key.Key_1:
                self.set_mode('coordinates')
                return
            elif key == Qt.Key.Key_2:
                self.set_mode('lines')
                return
            elif key == Qt.Key.Key_3:
                self.set_mode('curves')
                return
        
        # Escape - Cancel line drawing or clear selection
        if key == Qt.Key.Key_Escape:
            if hasattr(self.viewer_3d, 'line_start_point_id') and self.viewer_3d.line_start_point_id is not None:
                self.viewer_3d._cancel_line_drawing()
                self.update_status("Line drawing cancelled")
            else:
                self._clear_highlighting()
            return
        
        # Delete key - context-aware deletion
        if key == Qt.Key.Key_Delete:
            self._handle_delete_key()
            return
        
        # Tab key - cycle through tabs
        if key == Qt.Key.Key_Tab and modifiers == Qt.KeyboardModifier.NoModifier:
            current = self.tabs.currentIndex()
            next_tab = (current + 1) % self.tabs.count()
            self.tabs.setCurrentIndex(next_tab)
            return
        
        # Pass unhandled keys to parent
        super().keyPressEvent(event)
    
    def _handle_delete_key(self):
        """Handle Delete key based on current context."""
        # Check which tab is active
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 1:  # 2D Editor
            # Check which table has focus in editor
            if self.editor.points_table.hasFocus():
                selected = self.editor.points_table.selectedIndexes()
                if selected:
                    rows = sorted(set(idx.row() for idx in selected), reverse=True)
                    point_ids = [self.project.points[row].id for row in rows]
                    if len(point_ids) == 1:
                        self._delete_point(point_ids[0])
                    else:
                        self._delete_points(point_ids)
            elif self.editor.lines_table.hasFocus():
                selected = self.editor.lines_table.selectedIndexes()
                if selected:
                    rows = sorted(set(idx.row() for idx in selected), reverse=True)
                    line_ids = [self.project.lines[row].id for row in rows]
                    if len(line_ids) == 1:
                        self._delete_line(line_ids[0])
                    else:
                        self._delete_lines(line_ids)
            elif self.editor.curves_table.hasFocus():
                selected = self.editor.curves_table.selectedIndexes()
                if selected:
                    rows = sorted(set(idx.row() for idx in selected), reverse=True)
                    curve_ids = [self.project.curves[row].id for row in rows]
                    if len(curve_ids) == 1:
                        self._delete_curve(curve_ids[0])
                    else:
                        self._delete_curves(curve_ids)
        else:
            # No deletion in PDF or 3D view via keyboard (use context menus)
            self.update_status("Use context menu to delete items in this view")
