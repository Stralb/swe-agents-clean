#!/usr/bin/env python3
"""Read-only audit of original packet ZIP member names, never reads secrets into output."""
from pathlib import Path
import zipfile,re,json
R=Path.home()/"research_artifacts"
D=R/"prevention_pilot_phase2"/"owp14_allcases_packets_job71014"
bad=re.compile(r"(^|/)(?:\.env(?:\..*)?|\.ssh|id_(?:rsa|ed25519)|[^/]+\.(?:pem|p12|pfx|key)|credentials\.json|secrets?\.json)$",re.I)
template=re.compile(r"(^|/)(?:\.env(?:\..*)?\.(?:example|sample|template|dist)|\.env\.(?:example|sample|template|dist))$",re.I)
rows=[]
for p in sorted(D.glob("CASE_*.zip")):
 with zipfile.ZipFile(p) as z:
  names=[x.filename for x in z.infolist() if bad.search(x.filename)]
  templates=[x for x in names if template.search(x)]
  real=[x for x in names if not template.search(x)]
 rows.append({"file":p.name,"archive_bytes":p.stat().st_size,
 "suspicious_names":len(names),"templates":len(templates),
 "non_templates":len(real),"non_template_suffixes":sorted({Path(x).suffix.lower() for x in real}),
 "non_template_basename_samples":[Path(x).name for x in real[:5]]})
O=R/"mcp_uploads"/"jobs"/"arno_handoff_privacy_20261019_v1"/"INPUT_PRIVACY_FILENAME_AUDIT.json"
O.write_text(json.dumps({"packet_count":len(rows),"blocked":sum(bool(x["suspicious_names"]) for x in rows),"non_template_blocked":sum(bool(x["non_templates"]) for x in rows),"rows":rows},indent=2)+"\n")
print("AUDIT_COMPLETE",len(rows),"with_some_filename_flag",sum(bool(x["suspicious_names"]) for x in rows),"with_non_template",sum(bool(x["non_templates"]) for x in rows),flush=True)
