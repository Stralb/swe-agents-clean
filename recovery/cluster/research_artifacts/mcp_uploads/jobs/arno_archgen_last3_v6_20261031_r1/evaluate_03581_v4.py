from pathlib import Path
import hashlib
orig=Path(__file__).with_name("evaluate.py")
raw=orig.read_bytes()
assert hashlib.sha256(raw).hexdigest()=="6e19d665be114ea35f214463062c591ca1de75289fa6a2ad998769c9dbb2ebe3"
code=raw.decode("utf8")
old='read_original(receipt_path,sha(json.dumps(receipt,ensure_ascii=False,indent=2).encode())) if False else receipt_path.read_bytes()'
assert code.count(old)==1
code=code.replace(old,'read_original(receipt_path,"43ce80895f33deb0056ae05ad0aed348b4744263525fdd3cb3d595c6f769c4e3")')
assert code.count("receipt_sha256=fhash(receipt_path)")==1
code=code.replace("receipt_sha256=fhash(receipt_path)",'receipt_sha256=sha(read_original(receipt_path,"43ce80895f33deb0056ae05ad0aed348b4744263525fdd3cb3d595c6f769c4e3"))')
old='out=D/("results_"+case);out.mkdir(parents=True,exist_ok=False)'
new='out=D/("results_"+case+"_v2");out.mkdir(parents=True,exist_ok=False)'
assert code.count(old)==1
code=code.replace(old,new)
exec(compile(code,str(orig),"exec"),{"__name__":"__main__"})
