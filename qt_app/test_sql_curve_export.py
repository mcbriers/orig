from qt_app.models import ProjectData, Point, Line, Curve
from qt_app.import_export import ImportExport

p = ProjectData()
# existing points
p.points.append(Point(id=1, real_x=100, real_y=200, z=0, pdf_x=0, pdf_y=0, description='p1'))
p.points.append(Point(id=2, real_x=300, real_y=400, z=50, pdf_x=0, pdf_y=0, description='p2'))
# base line
p.lines.append(Line(id=10, start_id=1, end_id=2))
# curve: start and end correspond to points above; arc_points_real include intermediate coords with z varying
curve = Curve(id=20, start_id=1, end_id=2, arc_point_ids=[1], arc_points_real=[(100,200,0),(150,250,25),(300,400,50)], base_line_id=10)
p.curves.append(curve)

ok = ImportExport.export_sql(p, 'test_curve_export.sql')
print('Exported:', ok)
with open('test_curve_export.sql','r',encoding='utf-8') as f:
    print(f.read())