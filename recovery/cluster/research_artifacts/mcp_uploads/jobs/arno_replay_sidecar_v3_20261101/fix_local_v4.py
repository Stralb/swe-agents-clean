#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
source=Path(__file__).with_name("sidecar_build.py")
dest=Path(__file__).with_name("sidecar_build_local_v4.py")
raw=source.read_bytes()
assert sha256(raw).hexdigest()=="1ecb0abe346592640c164b3a90cef81248c4ae5ce5db647453d916b779453d1b"
old1=b'("SELECT count(*) FROM arno_v3_asset_bytes",201)'
new1=b'("SELECT count(*) FROM arno_v3_asset_bytes",207)'
old2=b'OUTPUT=J/"arno_replay_sidecar_v3_20261101/output"'
new2=b'OUTPUT=Path(os.environ["ARNO_SIDECAR_LOCAL_OUTPUT"])'
assert raw.count(old1)==1 and raw.count(old2)==1 and not dest.exists()
dest.write_bytes(raw.replace(old1,new1).replace(old2,new2))
print("Local-scratch SQLite build staged, 207 evidence assets expected",flush=True)
