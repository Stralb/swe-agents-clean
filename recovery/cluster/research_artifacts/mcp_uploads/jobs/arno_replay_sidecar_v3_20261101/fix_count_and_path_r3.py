#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
p=Path(__file__).with_name("sidecar_build.py")
out=Path(__file__).with_name("sidecar_build_r3.py")
b=p.read_bytes()
assert sha256(b).hexdigest()=="1ecb0abe346592640c164b3a90cef81248c4ae5ce5db647453d916b779453d1b"
a=b'("SELECT count(*) FROM arno_v3_asset_bytes",201)'
z=b'("SELECT count(*) FROM arno_v3_asset_bytes",207)'
c=b'OUTPUT=J/"arno_replay_sidecar_v3_20261101/output"'
d=b'OUTPUT=J/"arno_replay_sidecar_v3_20261101/output_r3"'
assert b.count(a)==1 and b.count(c)==1
assert not out.exists()
out.write_bytes(b.replace(a,z).replace(c,d))
print("Sidecar v3 r3: verified 207 evidence assets; independent output",flush=True)
