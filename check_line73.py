import json

with open('calibrated.dig', 'r') as f:
    data = json.load(f)

line_73 = [l for l in data['lines'] if l['id'] == 73]
if line_73:
    print(f"Line 73 exists: {line_73[0]}")
else:
    print("Line 73 does not exist - may have been deleted already")
    
# Check point 146 references the new way
print("\nPoint 146 line references:")
for l in data['lines']:
    if 146 in [l.get('start_id'), l.get('end_id')]:
        print(f"  Line {l['id']}: start={l.get('start_id')}, end={l.get('end_id')}")
