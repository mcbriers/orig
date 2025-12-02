"""
Quick test to verify the Qt application launches.
Run with: python test_qt_basic.py
"""
import sys
sys.path.insert(0, 'c:/temp/3DMaker/orig')

try:
    from PyQt6.QtWidgets import QApplication
    print("✓ PyQt6 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import PyQt6: {e}")
    print("  Install with: pip install PyQt6")
    sys.exit(1)

try:
    from qt_app.models import ProjectData, Point, Line, Curve
    print("✓ Models module imported")
    
    # Test basic model creation
    project = ProjectData()
    point = Point(id=1, real_x=100, real_y=200, z=0, pdf_x=50, pdf_y=100)
    project.points.append(point)
    print(f"✓ Created point: {point.id}")
    
    line = Line(id=1, start_id=1, end_id=2)
    project.lines.append(line)
    print(f"✓ Created line: {line.id}")
    
except Exception as e:
    print(f"✗ Models module error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from qt_app.geometry import GeometryEngine
    print("✓ Geometry module imported")
    
    geo = GeometryEngine()
    x, y = geo.transform_point(100, 200)
    print(f"✓ Transform works: ({x}, {y})")
    
except Exception as e:
    print(f"✗ Geometry module error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from qt_app.operations import Operations
    from qt_app.audit import LineAudit
    from qt_app.import_export import ImportExport
    print("✓ Operations, Audit, ImportExport modules imported")
    
except Exception as e:
    print(f"✗ Business logic modules error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from qt_app.main_window import MainWindow
    print("✓ MainWindow imported")
    
    # Test application creation (don't show window)
    app = QApplication(sys.argv)
    window = MainWindow()
    print("✓ MainWindow created successfully")
    
    # Don't exec, just verify it works
    print("\n✅ All basic tests passed!")
    print("\nTo run the full application:")
    print("  python main_qt.py")
    
except Exception as e:
    print(f"✗ MainWindow error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
