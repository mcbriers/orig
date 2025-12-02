"""
Entry point for the Qt-based 3D Maker Digitizer application.
"""
import sys
from PyQt6.QtWidgets import QApplication
from qt_app.main_window import MainWindow


def main():
    """Initialize and run the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("3D Maker Digitizer")
    app.setOrganizationName("3D Maker")
    
    window = MainWindow()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
