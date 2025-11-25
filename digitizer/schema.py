"""
Canonical schemas and validation helpers for the digitizer app.
This module defines expected keys and lightweight validators used by the new app.
"""
from typing import Dict, List, Any

# Canonical shapes (documented)
POINT_KEYS = ('id', 'pdf_x', 'pdf_y', 'real_x', 'real_y', 'z', 'description', 'hidden')
LINE_KEYS = ('id', 'start_id', 'end_id', 'canvas_id', 'text_id', 'hidden')
CURVE_KEYS = ('id', 'start_id', 'end_id', 'base_line_id', 'arc_points_pdf', 'arc_points_real', 'arc_point_ids', 'arc_point_marker_ids', 'canvas_id', 'z_level', 'hidden')


def is_point(obj: Dict[str, Any]) -> bool:
    try:
        return isinstance(obj['id'], int) and 'pdf_x' in obj and 'pdf_y' in obj
    except Exception:
        return False


def is_line(obj: Dict[str, Any]) -> bool:
    try:
        return isinstance(obj['id'], int) and isinstance(obj['start_id'], int) and isinstance(obj['end_id'], int)
    except Exception:
        return False


def is_curve(obj: Dict[str, Any]) -> bool:
    try:
        return isinstance(obj['id'], int) and 'arc_point_ids' in obj
    except Exception:
        return False


def validate_project(project: Dict[str, Any]) -> List[str]:
    """Return a list of validation error messages; empty list means OK."""
    errs = []
    if 'points' not in project or not isinstance(project['points'], list):
        errs.append('Missing or invalid points list')
    if 'lines' not in project or not isinstance(project['lines'], list):
        errs.append('Missing or invalid lines list')
    if 'curves' not in project or not isinstance(project['curves'], list):
        errs.append('Missing or invalid curves list')
    # Basic checks for unique IDs
    try:
        pids = [p['id'] for p in project.get('points', []) if isinstance(p, dict) and 'id' in p]
        if len(pids) != len(set(pids)):
            errs.append('Duplicate point IDs')
    except Exception:
        errs.append('Error checking point IDs')
    try:
        lids = [l['id'] for l in project.get('lines', []) if isinstance(l, dict) and 'id' in l]
        if len(lids) != len(set(lids)):
            errs.append('Duplicate line IDs')
    except Exception:
        errs.append('Error checking line IDs')
    return errs
