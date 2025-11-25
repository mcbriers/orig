"""
Migration helpers to normalize older project formats into canonical schema.
This module provides `migrate_project(project, allocator, transform_point_func, tol_pixels)`
which will ensure `arc_point_ids`, `arc_points_real`, and `base_line_id` exist.
"""
from typing import Dict, Any, Callable, Tuple


def _point_distance_sq(a: Tuple[float,float], b: Tuple[float,float]) -> float:
    dx = a[0]-b[0]
    dy = a[1]-b[1]
    return dx*dx + dy*dy


def migrate_project(project: Dict[str, Any], allocator, transform_point: Callable[[float,float], Tuple[float,float]], tol_pixels: float = 3.0) -> Dict[str, Any]:
    """Normalize project in-place and return it. tol_pixels is used to match arc pdf coords to existing points.
    `transform_point(pdf_x,pdf_y)` should return (real_x, real_y).
    allocator is an IDAllocator instance used to create new points when needed.
    """
    # Build quick lookup of points by pdf coords
    pts = project.get('points', [])
    pdf_lookup = {}
    for p in pts:
        key = (round(p.get('pdf_x',0),3), round(p.get('pdf_y',0),3))
        pdf_lookup.setdefault(key, []).append(p)

    lines = project.get('lines', [])
    curves = project.get('curves', [])

    # Simple pixel tolerance in PDF coordinate units: assume 1 unit ~= 1 pixel at baseline zoom
    tol_sq = float(tol_pixels*tol_pixels)

    for c in curves:
        arc_pdf = c.get('arc_points_pdf', [])
        ids = c.get('arc_point_ids', []) if c.get('arc_point_ids') else []
        # Try to map arc_pdf to existing points if ids missing
        if not ids and arc_pdf:
            for (px, py) in arc_pdf:
                # search by rounded key first
                key = (round(px,3), round(py,3))
                matched = None
                if key in pdf_lookup:
                    matched = pdf_lookup[key][0]
                else:
                    # brute force search by distance
                    best = None
                    bestd = None
                    for p in pts:
                        d = _point_distance_sq((px,py), (p.get('pdf_x',0), p.get('pdf_y',0)))
                        if best is None or d < bestd:
                            best = p
                            bestd = d
                    if best is not None and bestd <= tol_sq:
                        matched = best
                if matched:
                    ids.append(matched['id'])
                else:
                    # create a new point
                    rx, ry = transform_point(px, py)
                    new_id = allocator.next_point_id()
                    new_point = {
                        'id': new_id,
                        'pdf_x': px,
                        'pdf_y': py,
                        'real_x': round(rx, 2),
                        'real_y': round(ry, 2),
                        'z': c.get('z_level', c.get('z', 0)),
                        'description': 'auto-created arc point',
                        'hidden': False
                    }
                    pts.append(new_point)
                    # maintain lookup
                    pdf_lookup.setdefault((round(px,3),round(py,3)), []).append(new_point)
                    ids.append(new_id)
            c['arc_point_ids'] = ids

        # Ensure arc_points_real exist
        if not c.get('arc_points_real') and c.get('arc_points_pdf'):
            real_list = []
            zipped = c.get('arc_points_pdf', [])
            for i, (px,py) in enumerate(zipped):
                # prefer z from mapped point
                z = None
                if i < len(c.get('arc_point_ids', [])):
                    pid = c['arc_point_ids'][i]
                    p = next((pp for pp in pts if pp['id']==pid), None)
                    if p:
                        z = p.get('z', c.get('z_level', c.get('z', 0)))
                if z is None:
                    z = c.get('z_level', c.get('z', 0))
                rx, ry = transform_point(px, py)
                real_list.append((round(rx,2), round(ry,2), z))
            c['arc_points_real'] = real_list

        # Ensure base_line_id exists: find a matching line between start and end
        if 'base_line_id' not in c:
            s = c.get('start_id')
            e = c.get('end_id')
            bl = next((l['id'] for l in lines if l.get('start_id')==s and l.get('end_id')==e), None)
            if bl is None:
                # create a new line automatically
                new_lid = allocator.next_line_id()
                new_line = {'id': new_lid, 'start_id': s, 'end_id': e, 'hidden': False}
                lines.append(new_line)
                bl = new_lid
            c['base_line_id'] = bl

    project['points'] = pts
    project['lines'] = lines
    project['curves'] = curves
    return project
