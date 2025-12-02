"""
Analyze point references in calibrated.dig to find points with more than 3 references.
A point can be referenced by:
1. Lines (start_id or end_id)
2. Curves (arc_point_ids)
"""
import json
from collections import defaultdict

# Load the file
with open('calibrated.dig', 'r') as f:
    data = json.load(f)

# Count references for each point
point_refs = defaultdict(lambda: {'lines': [], 'curves': [], 'count': 0})

# Count line references
for line in data.get('lines', []):
    if not line.get('hidden', False):
        start_id = line.get('start_id')
        end_id = line.get('end_id')
        line_id = line.get('id')
        
        if start_id:
            point_refs[start_id]['lines'].append(f"line_{line_id}_start")
            point_refs[start_id]['count'] += 1
        if end_id:
            point_refs[end_id]['lines'].append(f"line_{line_id}_end")
            point_refs[end_id]['count'] += 1

# Count curve references
for curve in data.get('curves', []):
    if not curve.get('hidden', False):
        curve_id = curve.get('id')
        for point_id in curve.get('arc_point_ids', []):
            point_refs[point_id]['curves'].append(f"curve_{curve_id}")
            point_refs[point_id]['count'] += 1

# Find points with more than 3 references
print("Points with more than 3 references:")
print("=" * 80)

over_limit = []
for point_id in sorted(point_refs.keys()):
    refs = point_refs[point_id]
    if refs['count'] > 3:
        over_limit.append((point_id, refs))
        print(f"\nPoint ID: {point_id}")
        print(f"  Total references: {refs['count']}")
        print(f"  Line refs ({len(refs['lines'])}): {refs['lines']}")
        print(f"  Curve refs ({len(refs['curves'])}): {refs['curves']}")

print("\n" + "=" * 80)
print(f"Total points with >3 refs: {len(over_limit)}")
print(f"Maximum references: {max((r['count'] for _, r in over_limit), default=0)}")

# Show distribution
ref_counts = defaultdict(int)
for refs in point_refs.values():
    ref_counts[refs['count']] += 1

print("\nReference count distribution:")
for count in sorted(ref_counts.keys()):
    print(f"  {count} refs: {ref_counts[count]} points")
