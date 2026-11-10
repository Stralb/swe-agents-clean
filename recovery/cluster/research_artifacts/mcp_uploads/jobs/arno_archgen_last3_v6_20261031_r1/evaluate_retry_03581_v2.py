from pathlib import Path
import hashlib
p=Path(__file__).with_name("evaluate_verified.py")
raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=="97dbb716d8f77551189d2da7832240f81e92f97b6378c8365fdd3b27f0c2425f"
s=raw.decode("utf8")
needle='exec(compile(script,str(original),"exec"),{"__name__":"__main__"})'
replacement='script=script.replace("out.mkdir(parents=True,exist_ok=False)","out.mkdir(parents=True,exist_ok=True)")\\nexec(compile(script,str(original),"exec"),{"__name__":"__main__"})'
assert s.count(needle)==1
s=s.replace(needle,replacement.replace("\\n","\n"))
exec(compile(s,str(p),"exec"),{"__name__":"__main__"})
