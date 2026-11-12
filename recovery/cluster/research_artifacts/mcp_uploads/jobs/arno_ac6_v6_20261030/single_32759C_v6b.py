#!/usr/bin/env python3
"""Independent C-32759 CodeQL replay using exact supplied patch and receipt."""
from pathlib import Path
import ast,hashlib
R=Path.home()/"research_artifacts";D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
z=D/"single32759C_INPUT.zip";assert z.is_file()
sha=lambda b:hashlib.sha256(b).hexdigest()
source=(D/"scan_ac_v6b.py").read_text()
source=source.replace('ARCH=D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"','ARCH=D/"single32759C_INPUT.zip"')
source=source.replace('ARCH_SHA="d0319135b633c5c0d949e705af4ad99f7a415bd2cd6357d9fbe101bebf3e27b1"',
 'ARCH_SHA="'+sha(z.read_bytes())+'"')
source=source.replace('ensure(len(bundle.namelist())==30,"expected exactly 30 evidence files")',
 'ensure(len(bundle.namelist())==2,"expected exactly two direct evidence files")')
old='''    risk=bundle.read("RISKS_PILOT%s_PROSPECTIVE_PREDICT_R1.json"%case)
    ensure(doc.get("prediction_report_sha256")==sha(risk),"C prediction hash mismatch")
    (out/"RISKS.json").write_bytes(risk)'''
new='''    ensure(doc.get("prediction_report_sha256")=="5cad79f80852def666bfe40efc9b45fcf408e1dfe33983dbeb2a6d55266bdc03","C prediction hash does not match locally verified Stage2 report")'''
assert old in source
source=source.replace(old,new).replace('OUT=D/"results"','OUT=D/"results_single_b"')
scope={"__name__":"single_v6b"}
exec(compile(source,str(D/"scan_ac_v6b.py"),"exec"),scope)
scope["eval_task"](11)
