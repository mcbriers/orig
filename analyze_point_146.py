"""
Detailed analysis of point 146 which has 5 references including line_73 where it's both start and end.
"""
import json

with open('calibrated.dig', 'r') as f:
    data = json.load(f)

# Find point 146
point_146 = next((p for p in data['points'] if p['id'] == 146), None)
print("Point 146 details:")
print(f"  Location: ({point_146['real_x']}, {point_146['real_y']}, {point_146['z']})")
print(f"  PDF: ({point_146['pdf_x']:.2f}, {point_146['pdf_y']:.2f})")
print()

# Find related lines
lines_with_146 = [l for l in data['lines'] if 146 in [l.get('start_id'), l.get('end_id')]]
print(f"Lines referencing point 146:")
for line in lines_with_146:
    print(f"  Line {line['id']}: start={line['start_id']}, end={line['end_id']}")
    if line['start_id'] == 146:
        end_pt = next((p for p in data['points'] if p['id'] == line['end_id']), None)
        if end_pt:
            print(f"    -> end point {line['end_id']} at ({end_pt['real_x']}, {end_pt['real_y']}, {end_pt['z']})")
    if line['end_id'] == 146:
        start_pt = next((p for p in data['points'] if p['id'] == line['start_id']), None)
        if start_pt:
            print(f"    <- start point {line['start_id']} at ({start_pt['real_x']}, {start_pt['real_y']}, {start_pt['z']})")

# Find curves
curves_with_146 = [c for c in data['curves'] if 146 in c.get('arc_point_ids', [])]
print(f"\nCurves referencing point 146:")
for curve in curves_with_146:
    arc_ids = curve.get('arc_point_ids', [])
    idx = arc_ids.index(146)
    print(f"  Curve {curve['id']}: point 146 is at index {idx} of {len(arc_ids)} arc points")
    print(f"    Arc point IDs: {arc_ids}")

# Check if line 73 is a zero-length line (same start and end)
line_73 = next((l for l in data['lines'] if l['id'] == 73), None)
if line_73:
    print(f"\n⚠️  ISSUE FOUND: Line 73 has start_id={line_73['start_id']} and end_id={line_73['end_id']}")
    if line_73['start_id'] == line_73['end_id']:
        print(f"   This is a ZERO-LENGTH line (point to itself)! This should not exist.")
        print(f"   This invalid line adds 2 references to point {line_73['start_id']}")
