#!/usr/bin/env python3
"""Run identical scanner on independently uploaded C-32759 artifact before full cohort transfer."""
from pathlib import Path
from zipfile import ZipFile
import ast,hashlib,json,sys
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
F=D/"new_32759_C_input_fix.py"
def sha(x):return hashlib.sha256(x).hexdigest()
p=ast.parse(F.read_text())
parts={}
for statement in p.body:
 assert isinstance(statement,ast.Assign) and len(statement.targets)==1
 name=statement.targets[0].id
 parts[name]=ast.literal_eval(statement.value).encode("utf-8")
assert sha(parts["PATCH"])=="33ae35948aa0f2f7c69368bcc243166f2dbea089247b95020c1dbabb8877bdd0"
assert sha(parts["RECEIPT"])=="00501d04af292eb692e76afe9774b5d6326e7c15fa6fd21219a66c5c5a7e8df2"
receipt=json.loads(parts["RECEIPT"])
assert receipt["run_id"]=="PILOT32759_PROSPECTIVE_BUILD_R1"
z=D/"single32759C_INPUT.zip"
assert not z.exists()
with ZipFile(z,"x") as out:
 out.writestr("PATCH_PILOT32759_PROSPECTIVE_BUILD_R1.patch",parts["PATCH"])
 out.writestr("RECEIPT_PILOT32759_PROSPECTIVE_BUILD_R1.json",parts["RECEIPT"])
source=(D/"scan_ac_v6b.py").read_text()
old='ARCH=D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"'
assert old in source
source=source.replace(old,'ARCH=D/"single32759C_INPUT.zip"')
source=source.replace('ARCH_SHA="d0319135b633c5c0d949e705af4ad99f7a415bd2cd6357d9fbe101bebf3e27b1"',
  'ARCH_SHA="'+sha(z.read_bytes())+'"')
source=source.replace('ensure(len(bundle.namelist())==30,"expected exactly 30 evidence files")',
  'ensure(len(bundle.namelist())==2,"expected exactly two direct evidence files")')
source=source.replace('OUT=D/"results"','OUT=D/"results_single"')
ns={"__name__":"arno_single_test"}
exec(compile(source,str(D/"scan_ac_v6b.py"),"exec"),ns)
ns["eval_task"](11)
