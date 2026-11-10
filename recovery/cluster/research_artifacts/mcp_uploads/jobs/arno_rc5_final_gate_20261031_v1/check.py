#!/usr/bin/env python3
import zipfile,sqlite3,hashlib,json
from pathlib import Path
r=Path.home()/'research_artifacts/mcp_uploads/jobs/arno_release_rc5_oct31/release'
f=r/'ARNO_REVIEWER_RC5_RESTRICTED.zip'
p=r/'ARNO_REVIEWER_RC5_MINIMIZED.sqlite'
with zipfile.ZipFile(f) as z:
 assert z.testzip() is None
 names=z.namelist()
 assert 'ARNO_REVIEWER_RC5_MINIMIZED.sqlite' in names
 info=z.getinfo('ARNO_REVIEWER_RC5_MINIMIZED.sqlite')
 assert info.file_size==p.stat().st_size
 assert hashlib.sha256(z.read('ARNO_REVIEWER_RC5_MINIMIZED.sqlite')).hexdigest()==hashlib.sha256(p.read_bytes()).hexdigest()
c=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert c.execute('SELECT COUNT(*) FROM scientific_limitations').fetchone()[0]==12
assert c.execute('SELECT COUNT(*) FROM new_rerun_provenance').fetchone()[0]==2
assert c.execute('SELECT COUNT(*) FROM human_review_labels').fetchone()[0]==50
c.close()
print(json.dumps({'ZIP_CRC':'PASS','EXTRACTED_SQLITE_SHA_MATCHES':'PASS','INTEGRITY_CHECK':'PASS','ZIP_NAMES':names,'FILE_BYTES':p.stat().st_size},indent=2))
