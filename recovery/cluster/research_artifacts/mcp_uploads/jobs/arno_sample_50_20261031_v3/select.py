#!/usr/bin/env python3
import sqlite3,random,csv
from pathlib import Path
root=Path.home()/'research_artifacts'
db=sqlite3.connect('file:'+str(root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite')+'?mode=ro',uri=True)
rng=random.Random(20261031)
picks=[]
used=set()
for cls,n in [('H',6),('T',19),('M',25)]:
    rows=db.execute('select root_id,case_id from arno_d7_final_roots_342 where final_route=?',(cls,)).fetchall()
    rng.shuffle(rows)
    for root_id,case_id in rows:
        if case_id not in used:
            picks.append((root_id,case_id))
            used.add(case_id)
        if len([x for x in picks if x in rows])>=n:
            break
rng.shuffle(picks)
print(len(picks),len(used))
