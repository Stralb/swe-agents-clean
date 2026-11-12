from pathlib import Path
import io,zipfile
r=Path.home()/"research_artifacts"
a=r/"prevention_pilot_phase2/seven_case_delivery_20261020/SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip"
d=r/"prevention_pilot_phase2/seven_case_targeted_fixes_20261020/issue_texts"
d.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a) as outer:
 for cid in ["08152","31207"]:
  packet=outer.read("CASE_INPUTS/CASE_"+cid+"_O.zip")
  with zipfile.ZipFile(io.BytesIO(packet)) as inner:
   t=inner.read("ISSUE.md")
   (d/("CASE_"+cid+"_ORIGINAL_ISSUE.md")).write_bytes(t)
   print(cid,len(t))
