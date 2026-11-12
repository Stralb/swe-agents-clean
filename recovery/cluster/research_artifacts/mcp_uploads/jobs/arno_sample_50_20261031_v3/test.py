#!/usr/bin/env python3
import sqlite3
from pathlib import Path
f=Path.home()/'research_artifacts/ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
db=sqlite3.connect('file:'+str(f)+'?mode=ro',uri=True)
print(db.execute('select count(*) from arno_d7_final_roots_342').fetchone())
