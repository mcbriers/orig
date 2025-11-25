"""
Simple centralized ID allocator for points/lines/curves.
This keeps counters in one place and can be serialized into project files.
"""
from typing import Dict

class IDAllocator:
    def __init__(self, start_point=1, start_line=1, start_curve=1):
        self.point_counter = int(start_point)
        self.line_counter = int(start_line)
        self.curve_counter = int(start_curve)

    def next_point_id(self) -> int:
        pid = self.point_counter
        self.point_counter += 1
        return pid

    def next_line_id(self) -> int:
        lid = self.line_counter
        self.line_counter += 1
        return lid

    def next_curve_id(self) -> int:
        cid = self.curve_counter
        self.curve_counter += 1
        return cid

    def to_dict(self) -> Dict[str, int]:
        return {'point_counter': self.point_counter, 'line_counter': self.line_counter, 'curve_counter': self.curve_counter}

    @classmethod
    def from_project(cls, project: Dict):
        # Initialize counters based on existing data (max id + 1 semantics)
        pmax = max((p.get('id', 0) for p in project.get('points', [])), default=0)
        lmax = max((l.get('id', 0) for l in project.get('lines', [])), default=0)
        cmax = max((c.get('id', 0) for c in project.get('curves', [])), default=0)
        return cls(start_point=pmax+1, start_line=lmax+1, start_curve=cmax+1)
