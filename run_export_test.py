from digitizer.exporter import export_project
proj = {
    'points': [{'id':1,'real_x':10,'real_y':20,'z':0,'description':'p1'},{'id':2,'real_x':30,'real_y':40,'z':0,'description':'p2'}],
    'lines': [{'id':100,'start_id':1,'end_id':2}],
    'curves':[{'id':200,'base_line_id':100,'arc_point_ids':[1,2], 'arc_points_pdf':[(0,0),(1,1)]}],
    'curve_interior_points': 0
}
res = export_project(proj, '.', 'testproj')
print('Generated:', res['sql_file'])
print('--- SQL head ---')
with open(res['sql_file'],'r',encoding='utf-8') as f:
    for i,line in enumerate(f):
        print(line.rstrip())
        if i>20:
            break
