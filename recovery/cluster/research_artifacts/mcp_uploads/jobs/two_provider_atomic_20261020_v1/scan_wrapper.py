import sys,importlib.util,hashlib
from pathlib import Path
cid=sys.argv[1]
root=Path.home()/'research_artifacts'
base=root/'prevention_pilot_phase2/provider_variants_20261020'
case=base/cid
src=root/'mcp_uploads/jobs/seven_case_new_scans_20261020_v1/scan.py'
spec=importlib.util.spec_from_file_location('scanner',src)
obj=importlib.util.module_from_spec(spec)
spec.loader.exec_module(obj)
obj.RUN=base/'scans'
obj.UPLOAD=case/'upload'
obj.SHAS[cid]=hashlib.sha256((case/('CASE_'+cid+'_PROVIDER_V1.patch')).read_bytes()).hexdigest()
obj.main(cid)
