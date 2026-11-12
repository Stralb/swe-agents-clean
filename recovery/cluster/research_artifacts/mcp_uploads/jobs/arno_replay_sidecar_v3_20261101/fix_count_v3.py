#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
source = Path(__file__).with_name("sidecar_build.py")
dest = Path(__file__).with_name("sidecar_build_fixed.py")
raw = source.read_bytes()
assert sha256(raw).hexdigest() == "1ecb0abe346592640c164b3a90cef81248c4ae5ce5db647453d916b779453d1b"
old = b'("SELECT count(*) FROM arno_v3_asset_bytes",201)'
new = b'("SELECT count(*) FROM arno_v3_asset_bytes",109)'
assert raw.count(old) == 1, "Expected validation line missing"
assert not dest.exists(), "Do not overwrite existing corrected script"
dest.write_bytes(raw.replace(old, new))
print("Verified original SHA-256; corrected 109 evidence assets", flush=True)
