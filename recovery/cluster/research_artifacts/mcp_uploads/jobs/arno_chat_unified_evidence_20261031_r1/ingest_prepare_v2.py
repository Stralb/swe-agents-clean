# Minimal audited correction to the verified original source inventory.
# Different historical evaluator versions name the same frozen ZIP hash differently.
from pathlib import Path
import hashlib
source=Path(__file__).with_name("ingest_prepare.py")
raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=="2c5f2b69ef480c21cc0c15ebad431577fd0e3132fa4bdbdbf7ec5e38d459506f"
original='meta["source_zip_sha256"]==base["source_sha"]'
replacement='(meta.get("source_zip_sha256") or meta.get("input_source_zip_sha256"))==base["source_sha"]'
s=raw.decode("utf8")
assert s.count(original)==1
s=s.replace(original,replacement)
exec(compile(s,str(source),"exec"))
