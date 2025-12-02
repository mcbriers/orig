"""
Quick test to verify the changes work correctly.
"""
import json

with open('calibrated.dig', 'r') as f:
    data = json.load(f)

print("Testing refs calculation logic...")
print("=" * 60)

# Test point with multiple references
test_point_id = 146

refs = 0
# Count line references (skip hidden lines)
for l in data.get('lines', []):
    if not l.get('hidden', False):
        if l.get('start_id') == test_point_id or l.get('end_id') == test_point_id:
            refs += 1
            print(f"Line {l['id']}: start={l['start_id']}, end={l['end_id']}")

# Count curve references (skip hidden curves)
for c in data.get('curves', []):
    if not c.get('hidden', False):
        arc_ids = c.get('arc_point_ids', [])
        # Count arc point reference
        if test_point_id in arc_ids:
            refs += 1
            print(f"Curve {c['id']}: arc point (position {arc_ids.index(test_point_id) + 1} of {len(arc_ids)})")
        # Only count start/end if NOT already in arc_point_ids (avoid double-counting)
        elif c.get('start_id') == test_point_id or c.get('end_id') == test_point_id:
            refs += 1
            if c.get('start_id') == test_point_id:
                print(f"Curve {c['id']}: start point")
            if c.get('end_id') == test_point_id:
                print(f"Curve {c['id']}: end point")

print(f"\nTotal refs for point {test_point_id}: {refs}")
print("Expected: 3 (not 5, since line 73 is invalid and shouldn't count both start+end)")
