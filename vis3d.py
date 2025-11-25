import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import csv

class ThreeDVisualizer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('3D Visualization')
        self.resize(900, 700)

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # OpenGL 3D View widget
        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.opts['distance'] = 20000  # Adjust zoom start distance based on your data scale
        self.layout.addWidget(self.gl_widget)

        # Add grid for reference
        grid = gl.GLGridItem()
        grid.scale(2000, 2000, 1)
        self.gl_widget.addItem(grid)

        # Add axis indicator
        axes = gl.GLAxisItem()
        axes.setSize(10000, 10000, 10000)
        self.gl_widget.addItem(axes)

        # Containers for plots
        self.point_plot = None
        self.line_plots = []
        self.curve_plots = []

        # Data holders
        self.points = None        # Nx3 np.array
        self.lines = []           # list of tuple (start_xyz, end_xyz)
        self.curves = {}          # dict line_id -> Nx3 np.array
        self.point_ids = []       # list of point IDs

    def load_points(self, filename):
        points = []
        point_ids = []
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)  # skip header line
            for row in reader:
                if len(row) < 4:
                    continue
                # Format expected: ID,X,Y,Z
                try:
                    point_id, x, y, z = row
                    points.append([float(x), float(y), float(z)])
                    point_ids.append(int(point_id))
                except ValueError:
                    continue
        self.points = np.array(points)
        self.point_ids = point_ids

    def calculate_center_and_shift(self):
        # Calculate centroid of all points
        centroid = np.mean(self.points, axis=0)  # shape (3,)
        # Shift points
        self.points = self.points - centroid
        # Mirror along Y axis by negating y values
        self.points[:, 1] = -self.points[:, 1]

    def load_lines(self, filename):
        lines = []
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) < 5:
                    continue
                try:
                    _, start_id, end_id, _, _ = row
                    start_idx = int(start_id) - 1   # assuming 1-based IDs
                    end_idx = int(end_id) - 1
                    start_pt = self.points[start_idx]
                    end_pt = self.points[end_idx]
                    lines.append((start_pt, end_pt))
                except (ValueError, IndexError):
                    continue
        self.lines = lines

    def load_curves(self, filename):
        curve_points = {}
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) < 3:
                    continue
                try:
                    _, point_id, line_id = row
                    line_id = int(line_id)
                    point_idx = int(point_id) - 1
                    pt = self.points[point_idx]
                    if line_id not in curve_points:
                        curve_points[line_id] = []
                    curve_points[line_id].append(pt)
                except (ValueError, IndexError):
                    continue
        for lid, pts in curve_points.items():
            self.curves[lid] = np.array(pts)

    def display_points(self):
        if self.point_plot is not None:
            self.gl_widget.removeItem(self.point_plot)
        self.point_plot = gl.GLScatterPlotItem(pos=self.points, size=10, color=(0, 0, 1, 1), pxMode=True)
        self.gl_widget.addItem(self.point_plot)

        # Add labels for each point
        for i, point in enumerate(self.points):
            text = str(self.point_ids[i])  # Use actual point IDs
            label = gl.GLTextItem(pos=point, text=text, color=(1, 1, 1, 1))
            self.gl_widget.addItem(label)

    def display_lines(self):
        for lineplot in self.line_plots:
            self.gl_widget.removeItem(lineplot)
        self.line_plots = []
        for start, end in self.lines:
            pts = np.array([start, end])
            plot = gl.GLLinePlotItem(pos=pts, color=(1, 0.5, 0, 1), width=3, antialias=True)
            self.gl_widget.addItem(plot)
            self.line_plots.append(plot)

    def display_curves(self):
        for curveplot in self.curve_plots:
            self.gl_widget.removeItem(curveplot)
        self.curve_plots = []
        for pts in self.curves.values():
            if pts.shape[0] > 1:
                plot = gl.GLLinePlotItem(pos=pts, color=(0, 1, 0, 1), width=4, antialias=True)
                self.gl_widget.addItem(plot)
                self.curve_plots.append(plot)

    def load_and_display(self, points_file, lines_file, curves_file):
        self.load_points(points_file)
        self.calculate_center_and_shift()  # shift points to center around zero and mirror along Y
        self.load_lines(lines_file)         # these use shifted points now
        self.load_curves(curves_file)       # these use shifted points now
        self.display_points()
        self.display_lines()
        self.display_curves()

def launch_3d_app(points_file, lines_file, curves_file):
    app = QtWidgets.QApplication([])
    win = ThreeDVisualizer()
    win.load_and_display(points_file, lines_file, curves_file)
    win.show()
    app.exec_()

if __name__ == "__main__":
    launch_3d_app("zf_points.txt", "zf_lines.txt", "zf_curves.txt")
