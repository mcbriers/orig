"""
Find all zero-length lines (where start_id == end_id)
"""
import json

with open('calibrated.dig', 'r') as f:
    data = json.load(f)

zero_length_lines = []
for line in data.get('lines', []):
    if line.get('start_id') == line.get('end_id'):
        zero_length_lines.append(line)

print(f"Found {len(zero_length_lines)} zero-length lines:")
print("=" * 80)

for line in zero_length_lines:
    point_id = line['start_id']
    point = next((p for p in data['points'] if p['id'] == point_id), None)
    print(f"\nLine {line['id']}: start={line['start_id']}, end={line['end_id']}")
    print(f"  Hidden: {line.get('hidden', False)}")
    if point:
        print(f"  Point location: ({point['real_x']}, {point['real_y']}, {point['z']})")
