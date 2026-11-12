#!/bin/bash
#SBATCH --job-name=e127-archive-index
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
root=Path('/home-mscluster/astrauss/research_artifacts')
path=root/'mcp_uploads/jobs/click_integrated_audit_e127_20261026/analysis/E124_E125_E126_FULL_NATIVE_EVIDENCE.zip'
assert path.is_file()
with ZipFile(path) as z:
    files=[x for x in z.infolist() if not x.is_dir()]
    print('ZIP_FILES',len(files),'UNCOMPRESSED',sum(x.file_size for x in files),flush=True)
    print('EXTENSIONS',Counter(Path(x.filename).suffix for x in files),flush=True)
    for x in files[:95]:
        print('ENTRY',x.filename,x.file_size,flush=True)
    print('POTENTIAL_TRACE_EXCERPTS',flush=True)
    c=0
    for x in files:
        if x.file_size>200000 or not x.filename.lower().endswith(('.csv','.json','.jsonl','.txt')):
            continue
        if any(k in x.filename.lower() for k in ('trace','event','frame','transition','actions')):
            b=z.open(x).read(600).decode('utf-8','replace').replace(chr(10),' | ')
            print('EXCERPT',x.filename,repr(b[:550]),flush=True);c+=1
            if c>=8: break
print('READONLY_ARCHIVE_INSPECTION_DONE')
PY