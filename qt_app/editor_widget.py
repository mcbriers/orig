"""
Table editor widgets for points, lines, and curves.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
                             QTabWidget, QPushButton, QHeaderView, QMenu)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QVariant
from PyQt6.QtGui import QAction
from typing import List, Any


class PointsTableModel(QAbstractTableModel):
    """Table model for points."""
    
    def __init__(self, points: List = None, project = None):
        super().__init__()
        self.points = points or []
        self.project = project
        self.headers = ['ID', 'Real X', 'Real Y', 'Z', 'Hidden', 'Refs', 'Description']
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._sorted_cache = None  # Cache sorted list
    
    def rowCount(self, parent=QModelIndex()):
        if self.project:
            return len(self.project.points)
        return len(self.points)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        points_list = self._get_sorted_points()
        if not (0 <= index.row() < len(points_list)):
            return QVariant()
        
        point = points_list[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # ID
                return str(point.id)
            elif col == 1:  # Real X
                return str(int(point.real_x))
            elif col == 2:  # Real Y
                return str(int(point.real_y))
            elif col == 3:  # Z
                return str(int(point.z))
            elif col == 4:  # Hidden
                return "Yes" if point.hidden else "No"
            elif col == 5:  # Refs
                if self.project:
                    return str(self.project.count_point_references(point.id))
                return "0"
            elif col == 6:  # Description
                return point.description
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return QVariant()
    
    def sort(self, column, order):
        """Sort table by given column."""
        self.layoutAboutToBeChanged.emit()
        self._sort_column = column
        self._sort_order = order
        self._sorted_cache = None  # Invalidate cache
        self.layoutChanged.emit()
        # Force correct sort indicator
        if hasattr(self, '_table_view'):
            self._table_view.horizontalHeader().setSortIndicator(column, order)
    
    def beginResetModel(self):
        """Invalidate cache when model is reset."""
        self._sorted_cache = None
        super().beginResetModel()
    
    def _get_sorted_points(self):
        """Get points list sorted by current sort settings (cached)."""
        if self._sorted_cache is not None:
            return self._sorted_cache
        
        points_list = self.project.points if self.project else self.points
        
        # Define sort key function
        def sort_key(point):
            if self._sort_column == 0:  # ID
                return point.id
            elif self._sort_column == 1:  # Real X
                return point.real_x
            elif self._sort_column == 2:  # Real Y
                return point.real_y
            elif self._sort_column == 3:  # Z
                return point.z
            elif self._sort_column == 4:  # Hidden
                return point.hidden
            elif self._sort_column == 5:  # Refs
                return self.project.count_point_references(point.id) if self.project else 0
            elif self._sort_column == 6:  # Description
                return point.description.lower()
            return 0
        
        reverse = (self._sort_order == Qt.SortOrder.DescendingOrder)
        self._sorted_cache = sorted(points_list, key=sort_key, reverse=reverse)
        return self._sorted_cache


class LinesTableModel(QAbstractTableModel):
    """Table model for lines."""
    
    def __init__(self, lines: List = None, project = None):
        super().__init__()
        self.lines = lines or []
        self.project = project
        # Add 'Z' column (average of start/end point Z)
        self.headers = ['ID', 'Start ID', 'End ID', 'Z', 'Hidden', 'Base for Curve', 'Description']
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._sorted_cache = None  # Cache sorted list
    
    def rowCount(self, parent=QModelIndex()):
        if self.project:
            return len(self.project.lines)
        return len(self.lines)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        lines_list = self._get_sorted_lines()
        if not (0 <= index.row() < len(lines_list)):
            return QVariant()
        
        line = lines_list[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # ID
                return str(line.id)
            elif col == 1:  # Start ID
                return str(line.start_id)
            elif col == 2:  # End ID
                return str(line.end_id)
            elif col == 3:  # Z (average of start/end z)
                if self.project:
                    start_pt = self.project.get_point(line.start_id)
                    end_pt = self.project.get_point(line.end_id)
                    if start_pt and end_pt:
                        return str(int(round((start_pt.z + end_pt.z) / 2)))
                    elif start_pt:
                        return str(int(round(start_pt.z)))
                    elif end_pt:
                        return str(int(round(end_pt.z)))
                return "0"
            elif col == 4:  # Hidden
                return "Yes" if line.hidden else "No"
            elif col == 5:  # Base for Curve
                if self.project:
                    # Find curves that use this line as base
                    curve_ids = []
                    for curve in self.project.curves:
                        if hasattr(curve, 'base_line_id') and curve.base_line_id == line.id:
                            curve_ids.append(str(curve.id))
                    return ", ".join(curve_ids) if curve_ids else ""
                return ""
            elif col == 6:  # Description
                return line.description
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return QVariant()
    
    def sort(self, column, order):
        """Sort table by given column."""
        self.layoutAboutToBeChanged.emit()
        self._sort_column = column
        self._sort_order = order
        self._sorted_cache = None  # Invalidate cache
        self.layoutChanged.emit()
        # Force correct sort indicator
        if hasattr(self, '_table_view'):
            self._table_view.horizontalHeader().setSortIndicator(column, order)
    
    def beginResetModel(self):
        """Invalidate cache when model is reset."""
        self._sorted_cache = None
        super().beginResetModel()
    
    def _get_sorted_lines(self):
        """Get lines list sorted by current sort settings (cached)."""
        if self._sorted_cache is not None:
            return self._sorted_cache
        
        lines_list = self.project.lines if self.project else self.lines
        
        # Define sort key function
        def sort_key(line):
            if self._sort_column == 0:  # ID
                return line.id
            elif self._sort_column == 1:  # Start ID
                return line.start_id
            elif self._sort_column == 2:  # End ID
                return line.end_id
            elif self._sort_column == 3:  # Z (average)
                if self.project:
                    s = self.project.get_point(line.start_id)
                    e = self.project.get_point(line.end_id)
                    if s and e:
                        return int(round((s.z + e.z) / 2))
                    if s:
                        return int(round(s.z))
                    if e:
                        return int(round(e.z))
                return 0
            elif self._sort_column == 4:  # Hidden
                return line.hidden
            elif self._sort_column == 5:  # Base for Curve
                if self.project:
                    curve_ids = [c.id for c in self.project.curves 
                                if hasattr(c, 'base_line_id') and c.base_line_id == line.id]
                    return curve_ids[0] if curve_ids else 999999
                return 999999
            elif self._sort_column == 6:  # Description
                return line.description.lower()
            return 0
        
        reverse = (self._sort_order == Qt.SortOrder.DescendingOrder)
        self._sorted_cache = sorted(lines_list, key=sort_key, reverse=reverse)
        return self._sorted_cache


class CurvesTableModel(QAbstractTableModel):
    """Table model for curves."""
    
    def __init__(self, curves: List = None, project = None):
        super().__init__()
        self.curves = curves or []
        self.project = project
        # Dynamic headers - will show Pos 0-5 columns based on max arc points
        self.base_headers = ['ID', 'Start ID', 'End ID', 'Hidden', 'Description']
        self.max_positions = 6  # Default to show positions 0-5
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
    
    def rowCount(self, parent=QModelIndex()):
        if self.project:
            return len(self.project.curves)
        return len(self.curves)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.base_headers) + self.max_positions
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        curves_list = self._get_sorted_curves()
        if not (0 <= index.row() < len(curves_list)):
            return QVariant()
        
        curve = curves_list[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # ID
                return str(curve.id)
            elif col == 1:  # Start ID
                return str(curve.start_id)
            elif col == 2:  # End ID
                return str(curve.end_id)
            elif col == 3:  # Hidden
                return "Yes" if curve.hidden else "No"
            elif col == 4:  # Description
                return curve.description
            elif col >= 5:  # Arc point positions (Pos 0-5)
                pos = col - 5
                if self.project and curve.arc_point_ids and pos < len(curve.arc_point_ids):
                    point_id = curve.arc_point_ids[pos]
                    point = self.project.get_point(point_id)
                    if point:
                        return f"{point_id} (Z:{int(point.z)})"
                return ""
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section < len(self.base_headers):
                return self.base_headers[section]
            else:
                pos = section - len(self.base_headers)
                return f"Pos {pos}"
        return QVariant()
    
    def sort(self, column, order):
        """Sort table by given column."""
        self.layoutAboutToBeChanged.emit()
        self._sort_column = column
        self._sort_order = order
        self._sorted_cache = None  # Invalidate cache
        self.layoutChanged.emit()
        # Force correct sort indicator
        if hasattr(self, '_table_view'):
            self._table_view.horizontalHeader().setSortIndicator(column, order)
    
    def beginResetModel(self):
        """Invalidate cache when model is reset."""
        self._sorted_cache = None
        super().beginResetModel()
    
    def _get_sorted_curves(self):
        """Get curves list sorted by current sort settings (cached)."""
        if self._sorted_cache is not None:
            return self._sorted_cache
        
        curves_list = self.project.curves if self.project else self.curves
        
        # Define sort key function
        def sort_key(curve):
            if self._sort_column == 0:  # ID
                return curve.id
            elif self._sort_column == 1:  # Start ID
                return curve.start_id
            elif self._sort_column == 2:  # End ID
                return curve.end_id
            elif self._sort_column == 3:  # Hidden
                return curve.hidden
            elif self._sort_column == 4:  # Description
                return curve.description.lower()
            elif self._sort_column >= 5:  # Arc point positions
                pos = self._sort_column - 5
                if curve.arc_point_ids and pos < len(curve.arc_point_ids):
                    return curve.arc_point_ids[pos]
                return 999999
            return 0
        
        reverse = (self._sort_order == Qt.SortOrder.DescendingOrder)
        self._sorted_cache = sorted(curves_list, key=sort_key, reverse=reverse)
        return self._sorted_cache


class EditorWidget(QWidget):
    """Combined editor widget with tabs for points, lines, and curves."""
    
    # Signals
    point_selected = pyqtSignal(int)  # point_id
    line_selected = pyqtSignal(int)  # line_id
    curve_selected = pyqtSignal(int)  # curve_id
    
    duplicate_point_requested = pyqtSignal(int)  # point_id
    duplicate_line_requested = pyqtSignal(int)  # line_id
    duplicate_curve_requested = pyqtSignal(int)  # curve_id
    
    delete_point_requested = pyqtSignal(int)  # point_id
    delete_line_requested = pyqtSignal(int)  # line_id
    delete_curve_requested = pyqtSignal(int)  # curve_id
    
    delete_points_requested = pyqtSignal(list)  # [point_ids]
    delete_lines_requested = pyqtSignal(list)  # [line_ids]
    delete_curves_requested = pyqtSignal(list)  # [curve_ids]
    
    show_references_requested = pyqtSignal(int)  # point_id
    
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Points tab
        points_widget = QWidget()
        points_layout = QVBoxLayout()
        points_widget.setLayout(points_layout)
        
        self.points_table = QTableView()
        self.points_model = PointsTableModel(project=self.project)
        self.points_model._table_view = self.points_table  # Store reference for sort indicators
        self.points_table.setModel(self.points_model)
        self.points_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.points_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.points_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.points_table.customContextMenuRequested.connect(self._show_point_context_menu)
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.points_table.setSortingEnabled(True)
        points_layout.addWidget(self.points_table)
        
        self.tabs.addTab(points_widget, "Points")
        
        # Lines tab
        lines_widget = QWidget()
        lines_layout = QVBoxLayout()
        lines_widget.setLayout(lines_layout)
        
        self.lines_table = QTableView()
        self.lines_model = LinesTableModel(project=self.project)
        self.lines_model._table_view = self.lines_table  # Store reference for sort indicators
        self.lines_table.setModel(self.lines_model)
        self.lines_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.lines_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.lines_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lines_table.customContextMenuRequested.connect(self._show_line_context_menu)
        self.lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.setSortingEnabled(True)
        lines_layout.addWidget(self.lines_table)
        
        self.tabs.addTab(lines_widget, "Lines")
        
        # Curves tab
        curves_widget = QWidget()
        curves_layout = QVBoxLayout()
        curves_widget.setLayout(curves_layout)
        
        self.curves_table = QTableView()
        self.curves_model = CurvesTableModel(project=self.project)
        self.curves_model._table_view = self.curves_table  # Store reference for sort indicators
        self.curves_table.setModel(self.curves_model)
        self.curves_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.curves_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.curves_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.curves_table.customContextMenuRequested.connect(self._show_curve_context_menu)
        self.curves_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.curves_table.setSortingEnabled(True)
        curves_layout.addWidget(self.curves_table)
        
        self.tabs.addTab(curves_widget, "Curves")
        
        layout.addWidget(self.tabs)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Tables")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)
    
    def refresh(self):
        """Refresh all tables."""
        self.points_model.beginResetModel()
        self.points_model.endResetModel()
        self.lines_model.beginResetModel()
        self.lines_model.endResetModel()
        self.curves_model.beginResetModel()
        self.curves_model.endResetModel()
    
    def _show_point_context_menu(self, position):
        """Show context menu for points table."""
        # Get all selected rows
        selected_indexes = self.points_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_points = [self.project.points[index.row()] for index in selected_indexes]
        point_ids = [p.id for p in selected_points]
        
        menu = QMenu()
        
        if len(selected_points) == 1:
            # Single selection - show all options
            point = selected_points[0]
            
            duplicate_action = QAction("Duplicate Point", self)
            duplicate_action.triggered.connect(lambda: self.duplicate_point_requested.emit(point.id))
            menu.addAction(duplicate_action)
            
            delete_action = QAction("Delete Point", self)
            delete_action.triggered.connect(lambda: self.delete_point_requested.emit(point.id))
            menu.addAction(delete_action)
            
            menu.addSeparator()
            
            refs_action = QAction("Show References", self)
            refs_action.triggered.connect(lambda: self.show_references_requested.emit(point.id))
            menu.addAction(refs_action)
        else:
            # Multiple selection - only show delete option
            delete_action = QAction(f"Delete {len(selected_points)} Points", self)
            delete_action.triggered.connect(lambda: self.delete_points_requested.emit(point_ids))
            menu.addAction(delete_action)
        
        menu.exec(self.points_table.viewport().mapToGlobal(position))
    
    def _show_line_context_menu(self, position):
        """Show context menu for lines table."""
        # Get all selected rows
        selected_indexes = self.lines_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_lines = [self.project.lines[index.row()] for index in selected_indexes]
        line_ids = [l.id for l in selected_lines]
        
        menu = QMenu()
        
        if len(selected_lines) == 1:
            # Single selection - show all options
            line = selected_lines[0]
            
            duplicate_action = QAction("Duplicate Line", self)
            duplicate_action.triggered.connect(lambda: self.duplicate_line_requested.emit(line.id))
            menu.addAction(duplicate_action)
            
            delete_action = QAction("Delete Line", self)
            delete_action.triggered.connect(lambda: self.delete_line_requested.emit(line.id))
            menu.addAction(delete_action)
        else:
            # Multiple selection - only show delete option
            delete_action = QAction(f"Delete {len(selected_lines)} Lines", self)
            delete_action.triggered.connect(lambda: self.delete_lines_requested.emit(line_ids))
            menu.addAction(delete_action)
        
        menu.exec(self.lines_table.viewport().mapToGlobal(position))
    
    def _show_curve_context_menu(self, position):
        """Show context menu for curves table."""
        # Get all selected rows
        selected_indexes = self.curves_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_curves = [self.project.curves[index.row()] for index in selected_indexes]
        curve_ids = [c.id for c in selected_curves]
        
        menu = QMenu()
        
        if len(selected_curves) == 1:
            # Single selection - show all options
            curve = selected_curves[0]
            
            duplicate_action = QAction("Duplicate Curve", self)
            duplicate_action.triggered.connect(lambda: self.duplicate_curve_requested.emit(curve.id))
            menu.addAction(duplicate_action)
            
            delete_action = QAction("Delete Curve", self)
            delete_action.triggered.connect(lambda: self.delete_curve_requested.emit(curve.id))
            menu.addAction(delete_action)
        else:
            # Multiple selection - only show delete option
            delete_action = QAction(f"Delete {len(selected_curves)} Curves", self)
            delete_action.triggered.connect(lambda: self.delete_curves_requested.emit(curve_ids))
            menu.addAction(delete_action)
        
        menu.exec(self.curves_table.viewport().mapToGlobal(position))
