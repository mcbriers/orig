"""
Minimal entrypoint demonstrating the new modular digitizer utilities.
This is intentionally lightweight: it shows how to use the allocator, migration and exporter.
Run: python new_main.py
"""
import os
from digitizer.id_alloc import IDAllocator
from digitizer import migrate, exporter, schema

# Simple transform function placeholder: identity transform
def transform_point(pdf_x, pdf_y):
    # In the real app you'd use calibration matrix to transform pdf coords to real coords
    return float(pdf_x), float(pdf_y)


def demo_export():
    # Minimal synthetic project demonstrating canonical structure
    project = {
        'pdf_path': 'map.pdf',
        'points': [
            {'id': 1, 'pdf_x': 10.0, 'pdf_y': 20.0, 'real_x': 10.0, 'real_y': 20.0, 'z': '0', 'description': 'A', 'hidden': False},
            {'id': 2, 'pdf_x': 100.0, 'pdf_y': 200.0, 'real_x': 100.0, 'real_y': 200.0, 'z': '0', 'description': 'B', 'hidden': False}
        ],
        'lines': [
            {'id': 1, 'start_id': 1, 'end_id': 2, 'hidden': False}
        ],
        'curves': [
            {
                'id': 1,
                'start_id': 1,
                'end_id': 2,
                'arc_points_pdf': [(10.0,20.0),(30.0,50.0),(60.0,80.0),(90.0,120.0),(100.0,200.0)],
                # arc_point_ids intentionally missing to demonstrate migration
                'z_level': '0',
                'hidden': False
            }
        ],
        'curve_interior_points': 4
    }

    # create allocator from project
    alloc = IDAllocator.from_project(project)

    # migrate project (create missing points, lines and arc_point_ids)
    project = migrate.migrate_project(project, alloc, transform_point, tol_pixels=3.0)

    # validate
    errs = schema.validate_project(project)
    if errs:
        print('Validation errors:', errs)
    # export to ./exports
    out = exporter.export_project(project, os.path.join(os.getcwd(),'exports'), 'demo_project')
    print('Exported files:', out)

if __name__ == '__main__':
    demo_export()
