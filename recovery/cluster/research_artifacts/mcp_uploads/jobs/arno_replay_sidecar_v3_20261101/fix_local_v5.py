#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
source=Path(__file__).with_name("sidecar_build.py")
dest=Path(__file__).with_name("sidecar_build_local_v5.py")
raw=source.read_bytes()
assert sha256(raw).hexdigest()=="1ecb0abe346592640c164b3a90cef81248c4ae5ce5db647453d916b779453d1b"
changes=[
 (b'("SELECT count(*) FROM arno_v3_asset_bytes",201)',b'("SELECT count(*) FROM arno_v3_asset_bytes",207)'),
 (b'OUTPUT=J/"arno_replay_sidecar_v3_20261101/output"',b'OUTPUT=Path(os.environ["ARNO_SIDECAR_LOCAL_OUTPUT"])'),
 (b'PRAGMA quick_check',b'PRAGMA main.quick_check')
]
assert not dest.exists()
for old,new in changes:
 assert raw.count(old)==1,(old,raw.count(old))
 raw=raw.replace(old,new)
dest.write_bytes(raw)
print("Corrected three verified edits: assets=207, local scratch, main-only quick_check",flush=True)
