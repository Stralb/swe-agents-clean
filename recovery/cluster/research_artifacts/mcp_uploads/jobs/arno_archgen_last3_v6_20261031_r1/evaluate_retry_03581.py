from pathlib import Path
import hashlib
original=Path(__file__).with_name("evaluate_verified.py")
raw=original.read_bytes()
assert hashlib.sha256(raw).hexdigest()=="97dbb716d8f77551189d2da7832240f81e92f97b6378c8365fdd3b27f0c2425f"
script=raw.decode("utf8")
old='exec(compile(script,str(original),"exec"),{"__name__":"__main__"})'
replacement='''old_line="out.mkdir(parents=True,exist_ok=False)"
new_line="out.mkdir(parents=True,exist_ok=True)\\nassert not any(out.iterdir()), \\"Nonempty results directory\\""
assert script.count(old_line)==1
script=script.replace(old_line,new_line)
exec(compile(script,str(original),"exec"),{"__name__":"__main__"})'''
assert script.count(old)==1
script=script.replace(old,replacement)
exec(compile(script,str(original),"exec"),{"__name__":"__main__"})
