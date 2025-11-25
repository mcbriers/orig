import sys
import tkinter.messagebox as messagebox
from curves import CurvesMixin
from deletion import DeletionMixin

class CanvasStub:
    def delete(self, _):
        pass

class TestApp(CurvesMixin, DeletionMixin):
    def __init__(self):
        self.A, self.B = 0, 1
        self.user_points = []
        self.lines = []
        self.curves = []
        self.point_markers = {}
        self.canvas = CanvasStub()
        self.deletion_log = []
        self.point_id_counter = 4

    def update_3d_plot(self):
        # noop for smoke test
        pass

# Auto-confirm deletion dialogs
_orig_ask = messagebox.askyesno
messagebox.askyesno = lambda title, msg: True

app = TestApp()

# Test circle math
try:
    center, radius = app.circle_from_three_points((0,0), (1,0), (0,1))
    if center is None or radius is None:
        print('Circle math failed: center/radius None')
        sys.exit(2)
    print('Circle center, radius:', center, radius)
except Exception as e:
    print('Circle math raised exception:', e)
    sys.exit(2)

# Setup points/line/curve
p1 = {'id':1,'pdf_x':0,'pdf_y':0,'real_x':0,'real_y':0,'z':0}
p2 = {'id':2,'pdf_x':1,'pdf_y':0,'real_x':1,'real_y':0,'z':0}
p3 = {'id':3,'pdf_x':0.5,'pdf_y':0.5,'real_x':0.5,'real_y':0.5,'z':0}
app.user_points = [p1, p2, p3]
app.lines = [{'id':10,'start_id':1,'end_id':2,'canvas_id':None,'text_id':None}]
app.curves = [{
    'id':100,
    'start_id':1,
    'end_id':2,
    'base_line_id':10,
    'arc_point_ids':[1,3,2],
    'arc_points_pdf':[(0,0),(0.5,0.5),(1,0)],
    'arc_points_real':[(0,0,0),(0.5,0.5,0),(1,0,0)],
    'arc_point_marker_ids':[],
    'canvas_id':None,
    'z_level':0,
    'hidden':False
}]

# Run deletion of the middle arc point (id 3) which should cascade-delete the curve and base line
try:
    app.delete_point(p3)
except Exception as e:
    print('delete_point raised:', e)
    sys.exit(2)

# verify
ok = True
if any(c.get('id') == 100 for c in app.curves):
    print('Curve 100 still present (should be deleted)')
    ok = False
if any(l.get('id') == 10 for l in app.lines):
    print('Line 10 still present (should be deleted)')
    ok = False
if any(p.get('id') == 3 for p in app.user_points):
    print('Point 3 still present (should be deleted)')
    ok = False
if not any(entry.get('action','') == 'delete_curve_due_to_point' for entry in app.deletion_log):
    print('Deletion log missing delete_curve_due_to_point entry')
    ok = False

messagebox.askyesno = _orig_ask

if ok:
    print('SMOKE TEST PASSED')
    sys.exit(0)
else:
    print('SMOKE TEST FAILED')
    sys.exit(3)
