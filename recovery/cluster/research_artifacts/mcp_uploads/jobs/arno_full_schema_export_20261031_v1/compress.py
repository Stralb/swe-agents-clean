#!/usr/bin/env python3
from pathlib import Path
import lzma,base64,hashlib
root=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_full_schema_export_20261031_v1/output"
p=root/"ARNO_MASTER_FULL_SCHEMA.sql"
data=p.read_bytes()
compressed=lzma.compress(data,preset=9)
encoded=base64.b64encode(compressed).decode("ascii")
target=root/"SCHEMA_SQL_LZMA_BASE64.txt"
target.write_text(encoded)
print("sql_bytes",len(data),"lzma_bytes",len(compressed),"base64_chars",len(encoded),"sql_sha256",hashlib.sha256(data).hexdigest())
