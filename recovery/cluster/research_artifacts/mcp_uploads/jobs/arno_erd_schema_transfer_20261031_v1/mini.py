#!/usr/bin/env python3
import json,sqlite3,lzma,base64
from pathlib import Path
from urllib.parse import quote
r=Path.home()/'research_artifacts'
db=r/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=r/'mcp_uploads/jobs/arno_erd_schema_transfer_20261031_v1'
out.mkdir(parents=True,exist_ok=True)
con=sqlite3.connect('file:'+quote(str(db))+'?mode=ro',uri=True)
con.execute('PRAGMA query_only=ON')
T={}
for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
 safe=name.replace('"','""')
 cols=[list(x) for x in con.execute('PRAGMA table_xinfo("'+safe+'")')]
 fks=[list(x) for x in con.execute('PRAGMA foreign_key_list("'+safe+'")')]
 T[name]={'c':[[x[1],x[2],x[3],x[5]] for x in cols],'f':[[x[0],x[1],x[2],x[3],x[4],x[5],x[6]] for x in fks]}
V=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]
obj={'tables':T,'views':V,'version':'LIVE_WITS_20261031'}
raw=json.dumps(obj,separators=(',',':')).encode()
b64=base64.b64encode(lzma.compress(raw,preset=9)).decode()
(out/'SCHEMA_MINI_BASE64.txt').write_text(b64)
print('tables',len(T),'views',len(V),'columns',sum(len(v['c']) for v in T.values()),'fk_columns',sum(len(v['f']) for v in T.values()),'raw',len(raw),'encoded',len(b64))
