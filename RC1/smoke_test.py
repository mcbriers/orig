"""
Comprehensive smoke test suite for 3D Maker Digitizer
Tests all major functionality including models, operations, geometry, and I/O
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# Import Qt components
from qt_app.models import Point, Line, Curve, ProjectData
from qt_app.operations import Operations
from qt_app.geometry import GeometryEngine
from qt_app.import_export import ImportExport
from digitizer.schema import is_point, is_line, is_curve, validate_project
from digitizer.calibration import Calibration, PDFDocument

# Test counters
tests_passed = 0
tests_failed = 0
test_details = []

def test(name, condition, details=""):
    """Record test result."""
    global tests_passed, tests_failed, test_details
    if condition:
        tests_passed += 1
        print(f"✓ {name}")
    else:
        tests_failed += 1
        print(f"✗ {name}")
        if details:
            print(f"  Details: {details}")
        test_details.append(f"FAILED: {name} - {details}")

def test_exception(name, func, *args, **kwargs):
    """Test that function doesn't raise exception."""
    try:
        result = func(*args, **kwargs)
        test(name, True)
        return result
    except Exception as e:
        test(name, False, str(e))
        return None

print("=" * 70)
print("3D MAKER DIGITIZER - COMPREHENSIVE SMOKE TEST SUITE")
print("=" * 70)

# ==================== SCHEMA VALIDATION TESTS ====================
print("\n[1] Schema Validation Tests")

point_dict = {'id': 1, 'pdf_x': 10.0, 'pdf_y': 20.0, 'real_x': 100, 'real_y': 200, 'z': 0}
test("is_point validates point dict", is_point(point_dict))
test("is_point rejects invalid dict", not is_point({'id': 'abc'}))

line_dict = {'id': 1, 'start_id': 1, 'end_id': 2}
test("is_line validates line dict", is_line(line_dict))
test("is_line rejects invalid dict", not is_line({'id': 1}))

curve_dict = {'id': 1, 'arc_point_ids': [1, 2, 3]}
test("is_curve validates curve dict", is_curve(curve_dict))
test("is_curve rejects invalid dict", not is_curve({'id': 1}))

valid_project = {'points': [], 'lines': [], 'curves': []}
errors = validate_project(valid_project)
test("validate_project accepts valid structure", len(errors) == 0, f"Errors: {errors}")

invalid_project = {'points': 'not a list'}
errors = validate_project(invalid_project)
test("validate_project detects invalid structure", len(errors) > 0)

# ==================== MODEL TESTS ====================
print("\n[2] Data Model Tests")

# Test Point model
point = test_exception("Point creation", Point, 
    id=1, real_x=100, real_y=200, z=5, pdf_x=10.0, pdf_y=20.0)
if point:
    point_dict = point.to_dict()
    test("Point.to_dict() contains id", point_dict['id'] == 1)
    test("Point.to_dict() contains coordinates", 
         point_dict['real_x'] == 100 and point_dict['z'] == 5)
    
    restored = Point.from_dict(point_dict)
    test("Point.from_dict() restores data", 
         restored.id == 1 and restored.real_x == 100)

# Test Line model
line = test_exception("Line creation", Line, 
    id=10, start_id=1, end_id=2)
if line:
    line_dict = line.to_dict()
    test("Line.to_dict() contains endpoints", 
         line_dict['start_id'] == 1 and line_dict['end_id'] == 2)
    
    restored = Line.from_dict(line_dict)
    test("Line.from_dict() restores data", 
         restored.start_id == 1 and restored.end_id == 2)

# Test Curve model
curve = test_exception("Curve creation", Curve,
    id=100, start_id=1, end_id=2, arc_point_ids=[1, 3, 2],
    arc_points_real=[(0, 0, 0), (50, 50, 0), (100, 0, 0)])
if curve:
    curve_dict = curve.to_dict()
    test("Curve.to_dict() contains arc points", 
         len(curve_dict['arc_point_ids']) == 3)
    
    restored = Curve.from_dict(curve_dict)
    test("Curve.from_dict() restores data", 
         len(restored.arc_point_ids) == 3)

# Test ProjectData
print("\n[3] ProjectData Tests")
project = test_exception("ProjectData creation", ProjectData)

if project:
    # Test ID allocation
    id1 = project.allocate_point_id()
    id2 = project.allocate_point_id()
    test("allocate_point_id() returns unique IDs", id1 != id2 and id2 == id1 + 1)
    
    # Add test points
    p1 = Point(1, 0, 0, 0, 0, 0)
    p2 = Point(2, 100, 0, 0, 10, 0)
    p3 = Point(3, 50, 50, 0, 5, 5)
    project.points = [p1, p2, p3]
    
    # Test point retrieval
    found = project.get_point(2)
    test("get_point() finds existing point", found is not None and found.id == 2)
    test("get_point() returns None for missing point", project.get_point(999) is None)
    
    # Add test line
    line1 = Line(10, 1, 2)
    project.lines = [line1]
    
    # Test reference counting
    refs = project.count_point_references(1)
    test("count_point_references() counts line endpoints", refs == 1)
    
    # Add test curve
    curve1 = Curve(100, 1, 2, arc_point_ids=[1, 3, 2])
    project.curves = [curve1]
    
    refs_with_curve = project.count_point_references(3)
    test("count_point_references() counts curve points", refs_with_curve == 1)
    
    # Test serialization
    project_dict = project.to_dict()
    test("to_dict() creates valid structure", 
         'user_points' in project_dict and 'lines' in project_dict)
    test("to_dict() includes all points", 
         len(project_dict['user_points']) == 3)
    
    # Test deserialization
    new_project = ProjectData()
    new_project.from_dict(project_dict)
    test("from_dict() restores points", len(new_project.points) == 3)
    test("from_dict() restores lines", len(new_project.lines) == 1)
    test("from_dict() restores curves", len(new_project.curves) == 1)

# ==================== GEOMETRY TESTS ====================
print("\n[4] Geometry Engine Tests")

geometry = test_exception("GeometryEngine creation", GeometryEngine)

if geometry:
    # Test transformation calculation
    pdf_points = [(0, 0), (100, 0)]
    real_points = [(0, 0), (200, 0)]  # 2x scale
    
    success = geometry.calculate_transformation(pdf_points, real_points)
    test("calculate_transformation() succeeds with valid points", success)
    
    if success:
        # Test point transformation
        real_x, real_y = geometry.transform_point(50, 0)
        test("transform_point() applies scaling correctly", 
             abs(real_x - 100) < 0.1, f"Expected ~100, got {real_x}")
        
        # Test inverse transformation
        pdf_coords = geometry.real_to_pdf(200, 0)
        test("real_to_pdf() inverts transformation", 
             pdf_coords is not None and abs(pdf_coords[0] - 100) < 0.1)
    
    # Test distance calculations
    dist_2d = geometry.distance_2d((0, 0), (3, 4))
    test("distance_2d() calculates correctly", abs(dist_2d - 5.0) < 0.01)
    
    dist_3d = geometry.distance_3d((0, 0, 0), (3, 4, 0))
    test("distance_3d() calculates correctly", abs(dist_3d - 5.0) < 0.01)
    
    # Test angle calculations
    angle = geometry.angle_from_center((0, 0), (1, 0))
    test("angle_from_center() returns 0 for east", abs(angle) < 0.01)
    
    angle_90 = geometry.angle_from_center((0, 0), (0, 1))
    test("angle_from_center() returns 90 for north", abs(angle_90 - 90) < 0.01)
    
    # Test angle between
    is_between = geometry.is_angle_between(45, 0, 90)
    test("is_angle_between() detects angle in range", is_between)
    
    not_between = geometry.is_angle_between(120, 0, 90)
    test("is_angle_between() rejects angle outside range", not not_between)

# ==================== OPERATIONS TESTS ====================
print("\n[5] Operations Tests")

project = ProjectData()
geometry = GeometryEngine()
geometry.transformation_matrix = None  # Identity (no transformation)

ops = test_exception("Operations creation", Operations, project, geometry)

if ops:
    # Test point creation
    p1 = ops.create_point(10.0, 20.0, 5.0)
    test("create_point() creates point", p1 is not None and p1.id > 0)
    test("create_point() adds to project", len(project.points) == 1)
    test("create_point() sets modified flag", project.modified)
    
    # Test point duplication
    project.modified = False
    p2 = ops.duplicate_point(p1, 10.0)
    test("duplicate_point() creates new point", p2 is not None and p2.id != p1.id)
    test("duplicate_point() preserves coordinates", 
         p2.pdf_x == p1.pdf_x and p2.pdf_y == p1.pdf_y)
    test("duplicate_point() updates Z", p2.z == 10.0)
    
    # Test line creation
    p3 = ops.create_point(30.0, 40.0, 5.0)
    line = ops.create_line(p1.id, p3.id)
    test("create_line() creates line", line is not None and line.id > 0)
    test("create_line() links points correctly", 
         line.start_id == p1.id and line.end_id == p3.id)
    test("create_line() prevents zero-length lines", 
         ops.create_line(p1.id, p1.id) is None)
    
    # Test line duplication (create valid destination points)
    p4 = ops.create_point(40.0, 50.0, 5.0)
    point_map = {p1.id: p2.id, p3.id: p4.id}
    dup_line = ops.duplicate_line(line, point_map)
    test("duplicate_line() creates new line", dup_line is not None)
    
    # Test point deletion
    p_temp = ops.create_point(100.0, 100.0, 0.0)
    success, msg = ops.delete_point(p_temp.id)
    test("delete_point() deletes unreferenced point", success)
    test("delete_point() with cascade=False prevents deletion of referenced point", 
         not ops.delete_point(p1.id, cascade=False)[0])
    test("delete_point() with cascade=True deletes referenced point and dependents", 
         ops.delete_point(p1.id, cascade=True)[0])
    
    # Test line deletion (create a new line first since previous one was cascaded)
    p5 = ops.create_point(50.0, 60.0, 0.0)
    p6 = ops.create_point(70.0, 80.0, 0.0)
    test_line = ops.create_line(p5.id, p6.id)
    line_count = len(project.lines)
    success, msg = ops.delete_line(test_line.id)
    test("delete_line() removes line", success and len(project.lines) == line_count - 1)
    
    # Test curve creation (requires setup with proper transformation)
    project = ProjectData()
    geometry_for_curve = GeometryEngine()
    # Set up a simple identity transformation that won't reject points
    pdf_pts = [(0.0, 0.0), (1000.0, 0.0)]
    real_pts = [(0.0, 0.0), (1000.0, 0.0)]
    geometry_for_curve.calculate_transformation(pdf_pts, real_pts)
    ops = Operations(project, geometry_for_curve)
    
    start = ops.create_point(0.0, 0.0, 0.0)
    via = ops.create_point(500.0, 500.0, 0.0)
    end = ops.create_point(1000.0, 0.0, 0.0)
    
    curve = ops.create_curve(start.id, end.id, via.id, num_interior_points=2)
    test("create_curve() creates curve", curve is not None)
    if curve:
        test("create_curve() generates arc points", len(curve.arc_point_ids) >= 2)
        test("create_curve() creates base line", curve.base_line_id is not None)
        test("create_curve() generates arc points data", len(curve.arc_points_real) >= 3)
        
        # Test curve deletion
        curve_count = len(project.curves)
        success, msg = ops.delete_curve(curve.id)
        test("delete_curve() removes curve", 
             success and len(project.curves) == curve_count - 1)

# ==================== BULK OPERATIONS TESTS ====================
print("\n[6] Bulk Operations Tests")

project = ProjectData()
ops = Operations(project, geometry)

# Create test structure
p1 = ops.create_point(0, 0, 0)
p2 = ops.create_point(10, 0, 0)
p3 = ops.create_point(20, 0, 0)
p4 = ops.create_point(30, 0, 0)
line1 = ops.create_line(p1.id, p2.id)
line2 = ops.create_line(p2.id, p3.id)
curve = ops.create_curve(p1.id, p3.id, p2.id)

initial_points = len(project.points)
deleted_count, deleted_items = ops.delete_points_bulk([p2.id])
test("delete_points_bulk() cascades deletions", deleted_count > 1)
test("delete_points_bulk() removes referenced entities", 
     'Curve' in str(deleted_items) or 'Line' in str(deleted_items))
test("delete_points_bulk() updates project", len(project.points) < initial_points)

# ==================== IMPORT/EXPORT TESTS ====================
print("\n[7] Import/Export Tests")

project = ProjectData()
ops = Operations(project, geometry)

# Create test data
p1 = ops.create_point(0, 0, 5)
p2 = ops.create_point(100, 100, 10)
line = ops.create_line(p1.id, p2.id)

# Test save/load
with tempfile.TemporaryDirectory() as tmpdir:
    test_file = Path(tmpdir) / "test_project.json"
    
    success = ImportExport.save_project(project, str(test_file))
    test("save_project() creates file", success and test_file.exists())
    
    # Load into new project
    new_project = ProjectData()
    success = ImportExport.load_project(new_project, str(test_file))
    test("load_project() reads file", success)
    test("load_project() restores points", len(new_project.points) == 2)
    test("load_project() restores lines", len(new_project.lines) == 1)
    
    # Test backup creation
    backup_path = ImportExport.create_backup(str(test_file))
    test("create_backup() creates backup file", 
         backup_path is not None and Path(backup_path).exists())
    
    # Test CSV exports
    points_csv = Path(tmpdir) / "points.csv"
    success = ImportExport.export_points_csv(project, str(points_csv))
    test("export_points_csv() creates file", success and points_csv.exists())
    
    lines_csv = Path(tmpdir) / "lines.csv"
    success = ImportExport.export_lines_csv(project, str(lines_csv))
    test("export_lines_csv() creates file", success and lines_csv.exists())
    
    # Test SQL export
    sql_file = Path(tmpdir) / "export.sql"
    success = ImportExport.export_sql(project, str(sql_file))
    test("export_sql() creates file", success and sql_file.exists())
    
    if sql_file.exists():
        content = sql_file.read_text()
        test("export_sql() includes point inserts", 
             'Visualization_Coordinate' in content)
        test("export_sql() includes line inserts", 
             'Visualization_Edge' in content)
    
    # Test GRASS export
    grass_file = Path(tmpdir) / "export.dig"
    success = ImportExport.export_grass_ascii(project, str(grass_file))
    test("export_grass_ascii() creates file", success and grass_file.exists())
    
    # Test RFID CSV import
    rfid_csv = Path(tmpdir) / "rfid.csv"
    rfid_csv.write_text("Id,Description,MagnetOnly,TransponderId\n1,Test Tag,0,RFID001\n2,Magnet,1,\n")
    rfid_data = ImportExport.import_rfid_csv(str(rfid_csv))
    test("import_rfid_csv() reads file", len(rfid_data) == 2)
    test("import_rfid_csv() parses fields correctly", 
         rfid_data[0]['description'] == 'Test Tag')
    test("import_rfid_csv() handles boolean fields", 
         rfid_data[1]['magnet_only'] == True)

# ==================== INTEGRATION TESTS ====================
print("\n[8] Integration Tests")

# Full workflow test
project = ProjectData()
geometry = GeometryEngine()
ops = Operations(project, geometry)

# Setup calibration
pdf_refs = [(0, 0), (100, 0)]
real_refs = [(0, 0), (1000, 0)]
geometry.calculate_transformation(pdf_refs, real_refs)
project.reference_points_pdf = pdf_refs
project.reference_points_real = real_refs

# Create points with transformation
p1 = ops.create_point(10, 10, 0, "Start Point")
p2 = ops.create_point(90, 10, 0, "End Point")
p3 = ops.create_point(50, 30, 0, "Arc Point")

test("Integration: points created with calibration", len(project.points) == 3)
test("Integration: transformation applied", p1.real_x != p1.pdf_x)

# Create line
line = ops.create_line(p1.id, p2.id, "Test Line")
test("Integration: line created", line is not None)

# Create curve
curve = ops.create_curve(p1.id, p2.id, p3.id, num_interior_points=3)
test("Integration: curve created", curve is not None)

# Test serialization roundtrip
with tempfile.TemporaryDirectory() as tmpdir:
    save_path = Path(tmpdir) / "integration_test.json"
    
    # Test modification tracking before save
    test("Integration: modification flag set", project.modified)
    
    ImportExport.save_project(project, str(save_path))
    test("Integration: save clears modified flag", not project.modified)
    
    restored_project = ProjectData()
    ImportExport.load_project(restored_project, str(save_path))
    
    test("Integration: roundtrip preserves point count", 
         len(restored_project.points) >= 3)
    test("Integration: roundtrip preserves calibration", 
         len(restored_project.reference_points_pdf) == 2)
    test("Integration: roundtrip preserves curves", 
         len(restored_project.curves) >= 1)

# ==================== MULTI-PDF TESTS ====================
print("\n[9] Multi-PDF Tests")

# Test PDFDocument creation
pdf1 = test_exception("PDFDocument creation", 
                      PDFDocument, "track1.pdf", None, "Track 1", 0)

# Test Calibration creation
cal1 = test_exception("Calibration creation", 
                      Calibration, "track1.pdf")

# Test calibration setup
if cal1:
    cal1.reference_points_pdf = [(0, 0), (100, 100)]
    cal1.reference_points_real = [(0, 0), (100, 100)]
    cal1._calculate_transformation()
    test("Calibration has transformation", cal1.is_valid())

# Test coordinate transformation
if cal1 and cal1.is_valid():
    x_real, y_real = cal1.pdf_to_real(50, 50)
    test("pdf_to_real() transforms correctly", abs(x_real - 50) < 0.1 and abs(y_real - 50) < 0.1)
    
    x_pdf, y_pdf = cal1.real_to_pdf(50, 50)
    test("real_to_pdf() transforms correctly", abs(x_pdf - 50) < 0.1 and abs(y_pdf - 50) < 0.1)

# Test calibration serialization
if cal1:
    with tempfile.TemporaryDirectory() as tmpdir:
        cal_path = Path(tmpdir) / "test.cal"
        cal1.save(str(cal_path))
        test("Calibration save creates file", cal_path.exists())
        
        cal2 = Calibration.load(str(cal_path))
        test("Calibration load restores data", 
             len(cal2.reference_points_pdf) == 2 and cal2.is_valid())

# Test ProjectData multi-PDF operations
mp_project = ProjectData()

# Create test PDFs
cal_a = Calibration("drawing_a.pdf")
cal_a.reference_points_pdf = [(0, 0), (100, 100)]
cal_a.reference_points_real = [(0, 0), (50, 50)]
cal_a._calculate_transformation()

cal_b = Calibration("drawing_b.pdf")
cal_b.reference_points_pdf = [(0, 0), (200, 200)]
cal_b.reference_points_real = [(0, 0), (100, 100)]
cal_b._calculate_transformation()

pdf_a = PDFDocument("drawing_a.pdf", cal_a, "Drawing A", 0)
pdf_b = PDFDocument("drawing_b.pdf", cal_b, "Drawing B", 1)

# Test add_pdf
mp_project.add_pdf(pdf_a)
test("add_pdf() adds to list", len(mp_project.pdfs) == 1)
test("add_pdf() sets modified flag", mp_project.modified)

mp_project.add_pdf(pdf_b)
test("add_pdf() handles multiple PDFs", len(mp_project.pdfs) == 2)

# Test get_active_pdf
active = mp_project.get_active_pdf()
test("get_active_pdf() returns PDF", active is not None)
test("get_active_pdf() returns first by default", 
     active.filename == "drawing_a.pdf" if active else False)

# Test set_active_pdf
mp_project.set_active_pdf(1)
test("set_active_pdf() changes active index", mp_project.active_pdf_index == 1)
active = mp_project.get_active_pdf()
test("set_active_pdf() changes active PDF", 
     active.filename == "drawing_b.pdf" if active else False)

# Test reorder_pdf
mp_project.reorder_pdf(0, 1)
test("reorder_pdf() changes order", mp_project.pdfs[0].filename == "drawing_b.pdf")
test("reorder_pdf() updates active index", mp_project.active_pdf_index == 0)

# Test remove_pdf
mp_project.remove_pdf(1)
test("remove_pdf() removes from list", len(mp_project.pdfs) == 1)
test("remove_pdf() adjusts active index", mp_project.active_pdf_index == 0)

# Test multi-PDF serialization
mp_project2 = ProjectData()
mp_project2.add_pdf(pdf_a)
mp_project2.add_pdf(pdf_b)

data = mp_project2.to_dict()
test("to_dict() includes pdfs field", 'pdfs' in data)
test("to_dict() includes active_pdf_index", 'active_pdf_index' in data)
test("to_dict() serializes PDFs", len(data['pdfs']) == 2)

# Test multi-PDF deserialization
mp_project3 = ProjectData()
mp_project3.project_path = "c:\\temp\\test.dig"
mp_project3.from_dict(data)
test("from_dict() restores PDFs", len(mp_project3.pdfs) == 2)
test("from_dict() restores active index", mp_project3.active_pdf_index == 0)
test("from_dict() restores PDF filenames", 
     mp_project3.pdfs[0].filename == "drawing_a.pdf")

# Test backward compatibility with old projects
old_data = {
    'user_points': [],
    'lines': [],
    'curves': [],
    'transponders': [],
    'reference_points_pdf': [(0, 0), (100, 100)],
    'reference_points_real': [(0, 0), (50, 50)],
    'deletion_log': []
}

compat_project = ProjectData()
compat_project.from_dict(old_data)
test("Backward compatibility: old projects load", len(compat_project.pdfs) == 0)
test("Backward compatibility: legacy calibration preserved", 
     len(compat_project.reference_points_pdf) == 2)

# ==================== FINAL SUMMARY ====================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Tests Passed: {tests_passed}")
print(f"Tests Failed: {tests_failed}")
print(f"Total Tests:  {tests_passed + tests_failed}")

if tests_failed > 0:
    print("\nFailed Tests:")
    for detail in test_details:
        print(f"  - {detail}")

print("=" * 70)

# Exit with appropriate code
if tests_failed == 0:
    print("✓ ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"✗ {tests_failed} TEST(S) FAILED")
    sys.exit(1)
