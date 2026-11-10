"""Index blinded run-manifest and scanner-summary rows as historical observations.

No run/arm/case mapping or patch bytes are inferred. This merely lets reviewers
query exact source-recorded checks and patch digests while bytes are being
recovered. All source CSV bytes are independently retained in the vault.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from .research import ResearchIndex
from .store import EvidenceStore, EvidenceError, _hash_file

STUDY_ID="S5PAIR001_STEP4_BLINDED"


def rows(raw: bytes, *, label: str) -> list[dict[str,str]]:
    text=raw.decode("utf-8-sig")
    c=csv.DictReader(io.StringIO(text,newline=""))
    if not c.fieldnames or any(not x for x in c.fieldnames) or len(set(c.fieldnames))!=len(c.fieldnames):
        raise EvidenceError(f"Invalid headers: {label}")
    values=list(c)
    if any(None in r for r in values):
        raise EvidenceError(f"Misaligned source row: {label}")
    return values


def index_blinded_run_metadata(store: EvidenceStore, manifest_file: str | Path,
                              summary_file: str | Path, qc_file: str | Path, *,
                              source_prefix: str = "wits://research_artifacts/counterfactual_replay_r1/step4_blinded") -> dict[str,Any]:
    index=ResearchIndex(store)
    files={"original_blinded_manifest":Path(manifest_file),
           "scanner_summary":Path(summary_file),"blinded_step4_qc":Path(qc_file)}
    hashes={kind:_hash_file(path)[0] for kind,path in files.items()}
    raw={kind:path.read_bytes() for kind,path in files.items()}
    if any(hashlib.sha256(raw[kind]).hexdigest()!=hashes[kind] for kind in files):
        raise EvidenceError("Source metadata changed between hashing and reading")
    manifest=rows(raw["original_blinded_manifest"],label="BLINDED_MANIFEST")
    scans=rows(raw["scanner_summary"],label="BLINDED_CODEQL_SUMMARY")
    qc=json.loads(raw["blinded_step4_qc"])
    runs={r.get("run_id") for r in manifest}
    scanruns={r.get("run_id") for r in scans}
    if (not manifest or len(runs)!=len(manifest) or len(scanruns)!=len(scans)
        or runs!=scanruns or len(runs)!=qc.get("runs_expected") or len(runs)!=qc.get("runs_summarized")):
        raise EvidenceError("Run IDs/counts mismatch among original blinded sources")
    if any(not rid or len(rid)!=4 or not rid.startswith("G") or not rid[1:].isdigit() for rid in runs):
        raise EvidenceError("Invalid blinded run IDs")
    result={"study_id":STUDY_ID,"run_ids":sorted(runs),"source_hashes":hashes,"batches":{},
            "caveat":"Source observations indexed; generated patches and per-run SARIF bytes not implied"}
    for kind in ("original_blinded_manifest","scanner_summary"):
        digest=hashes[kind]
        adapter="s5pair-source-rows:"+kind
        if index.existing(digest,adapter,"1.0"):
            result["batches"][kind]={"status":"ALREADY_INDEXED","rows":len(runs)}
            continue
        path=files[kind]
        sid,_=store.ingest(path,origin_uri=source_prefix+("/input/BLINDED_MANIFEST.csv" if kind=="original_blinded_manifest" else "/results/BLINDED_CODEQL_SUMMARY.csv"),
                           origin_revision="sha256:"+digest,expected_sha256=digest,
                           scientific_status="candidate",sensitivity="restricted",media_type="text/csv",
                           note="Original blinded run source: no historical correctness independently validated")
        current=manifest if kind=="original_blinded_manifest" else scans
        with store._open() as cx:
            batch=index.begin_batch(cx,sid,digest,adapter,"1.0",len(current))
            for rowno,row in enumerate(current,2):
                rec=index.add_record(cx,batch,locus=kind,row_index=rowno,unit_type="generation",
                                     unit_id=STUDY_ID+":"+row["run_id"],stage=STUDY_ID,kind=kind,
                                     payload={"original_headers":list(row),"values":row,
                                              "verification":"source_recorded_not_independently_replayed"})
                for name,value in row.items():
                    if name!="run_id" and value is not None:
                        index.add_annotation(cx,rec,unit_type="generation",unit_id=STUDY_ID+":"+row["run_id"],
                                             stage=STUDY_ID,label_name=kind+":"+name,raw_value=value,
                                             coding_pass="source_recorded",coder_identity="not_a_human_annotation")
        store.link(sid,unit_type="cohort",unit_id=STUDY_ID,
                   evidence_role=kind,analysis_stage="source_reported_blinded_metadata",
                   blinding="blind",method_revision="S5PAIR-source-index-1.0")
        result["batches"][kind]={"status":"SOURCE_ROWS_INDEXED","rows":len(current)}
    # QC is an exact stored source, separate from any asserted result.
    if not index.existing(hashes["blinded_step4_qc"],"s5pair-source-qc","1.0"):
        p=files["blinded_step4_qc"]
        sid,_=store.ingest(p,origin_uri=source_prefix+"/results/STEP4_QC.json",
                           origin_revision="sha256:"+hashes["blinded_step4_qc"],
                           expected_sha256=hashes["blinded_step4_qc"],scientific_status="candidate",
                           sensitivity="restricted",media_type="application/json",
                           note="Source-reported QC; no independent rerun")
        with store._open() as cx:
            batch=index.begin_batch(cx,sid,hashes["blinded_step4_qc"],"s5pair-source-qc","1.0",1)
            index.add_record(cx,batch,locus="STEP4_QC.json",row_index=1,unit_type="cohort",
                             unit_id=STUDY_ID,stage=STUDY_ID,kind="source_recorded_qc",payload=qc)
        store.link(sid,unit_type="cohort",unit_id=STUDY_ID,evidence_role="historical_step4_qc",
                   analysis_stage="source_reported_blinded_metadata",blinding="blind",
                   method_revision="S5PAIR-source-index-1.0")
    result["run_count"]=len(runs)
    return result
