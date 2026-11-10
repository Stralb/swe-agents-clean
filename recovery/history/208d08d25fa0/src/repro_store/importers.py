"""Read-only source importers for private workbook, archive and run evidence.

Never infer validity, human adjudication, a scanner outcome or arm identity from
an archive filename. All source bytes are copied, never altered.
"""
from __future__ import annotations

import hashlib
import csv
import itertools
import json
import mimetypes
import os
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .research import ResearchIndex, WORKBOOK_RULES, cell_value, canonical_json
from .store import EvidenceError, EvidenceStore, _hash_file, _now

MAX_MEMBERS = 20000
MAX_MEMBER_SIZE = 128 * 1024 * 1024
MAX_ARCHIVE_EXPANDED = 2 * 1024 * 1024 * 1024


def _sha(path: Path) -> str:
    return _hash_file(path)[0]


def _id(v) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and float(v).is_integer():
        return str(int(v))
    return str(v).strip() or None


def _archive_path(name: str) -> str:
    p=PurePosixPath(name)
    if (not name or "\\" in name or "\0" in name or p.is_absolute()
            or any(part in {"..", ""} for part in p.parts) or name.startswith("/")
            or ":" in p.parts[0]):
        raise EvidenceError(f"Unsafe member path: {name!r}")
    if any(part in {".env", "id_rsa", "id_ed25519", ".ssh"} for part in p.parts) or p.suffix.lower() in {".pem", ".key", ".p12"}:
        raise EvidenceError(f"Private-key/secret candidate cannot be bulk-imported: {name!r}")
    return str(p)


def _kind(path: str) -> str:
    p=path.lower()
    if p.endswith((".patch", ".diff")):
        return "candidate_patch"
    if p.endswith(".sarif"):
        return "candidate_scanner_sarif"
    if p.endswith(".ipynb"):
        return "notebook"
    if p.endswith((".json", ".jsonl")):
        return "structured_source"
    if p.endswith(".csv"):
        return "tabular_source"
    if p.endswith((".txt", ".md", ".log")):
        return "text_source"
    return "unclassified_binary"


def import_workbook(store: EvidenceStore, workbook: str | Path, *,
                    origin_uri: str, origin_revision: str,
                    expected_sha256: str | None = None) -> dict:
    """Copies whole .xlsx bytes, preserving every nonempty original cell.

    Structured rows/labels are only a *convenience index* over the original
    workbook; the source workbook remains the audit authority.
    """
    from openpyxl import load_workbook
    path=Path(workbook)
    if path.suffix.lower() != ".xlsx":
        raise EvidenceError("Only .xlsx source workbooks supported")
    index=ResearchIndex(store)
    digest=_sha(path)
    if expected_sha256 and expected_sha256.lower()!=digest:
        raise EvidenceError("Workbook expected digest mismatch")
    prior=index.existing(digest,"xlsx-lossless-index","2.0")
    if prior:
        return {**prior, "source_sha256":digest}
    wb=load_workbook(path,read_only=True,data_only=False,keep_links=False)
    prepared=[]
    try:
        for ws in wb:
            rows=ws.iter_rows(values_only=True)
            first=next(rows,None)
            if first is None:
                continue
            headers=[str(x).strip() if x is not None else "" for x in first]
            rule=WORKBOOK_RULES.get(ws.title)
            key_col=next((i for i,x in enumerate(headers) if rule and x==rule[1]),None)
            for row_index, values in enumerate(itertools.chain((first,),rows),1):
                cells={str(i+1):cell_value(x) for i,x in enumerate(values) if x is not None}
                if not cells:
                    continue
                # Keep 1-based positions and original headers; header ties and blank
                # headers are represented without discarding side-by-side tables.
                raw={"sheet":ws.title,"row":row_index,"cells_by_1based_column":cells,
                     "original_header_values":headers}
                unit_type="document_row"
                unit_id=f"{ws.title}:{row_index}"
                if rule and key_col is not None and row_index>=2:
                    value=values[key_col] if key_col<len(values) else None
                    detected=_id(value)
                    if detected:
                        unit_type=rule[0]
                        unit_id=detected
                annotations=[]
                edges=[]
                if row_index>=2:
                    named={h:values[i] for i,h in enumerate(headers) if h and i<len(values)}
                    case=_id(named.get("Case ID"))
                    finding=_id(named.get("Canonical Finding ID"))
                    producing=_id(named.get("Producing Change ID"))
                    if case and finding:
                        edges.append(("finding",finding,"workflow",case,"finding_in_workflow"))
                    if case and producing:
                        edges.append(("producing_change",producing,"workflow",case,"change_in_workflow"))
                    if finding and producing:
                        edges.append(("producing_change",producing,"finding",finding,"produced_finding"))
                if unit_type!="document_row" and rule:
                    for original_col, normalized_label in rule[2].items():
                        col=next((i for i,h in enumerate(headers) if h==original_col),None)
                        if col is not None and col<len(values) and values[col] is not None:
                            annotations.append((normalized_label,cell_value(values[col])))
                prepared.append((ws.title,row_index,unit_type,unit_id,raw,annotations,edges))
    finally:
        wb.close()
    source_id,_=store.ingest(path,origin_uri=origin_uri,origin_revision=origin_revision,
                             scientific_status="candidate",sensitivity="restricted",
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             expected_sha256=digest,allow_large=True,
                             note="Historical source workbook; classifications not independently validated")
    counts={}
    with store._open() as cx:
        batch_id=index.begin_batch(cx,source_id,digest,"xlsx-lossless-index","2.0",len(prepared))
        for sheet,rowno,unit_type,unit_id,raw,annotations,edges in prepared:
            rec=index.add_record(cx,batch_id,locus=f"xlsx:{sheet}",row_index=rowno,
                                 unit_type=unit_type,unit_id=unit_id,stage=sheet,
                                 kind="workbook-row-as-recorded",payload=raw)
            for label,value in annotations:
                index.add_annotation(cx,rec,unit_type=unit_type,unit_id=unit_id,
                                     stage=sheet,label_name=label,raw_value=value)
            for from_type,from_id,to_type,to_id,relation in edges:
                index.add_edge(cx,batch_id,from_type=from_type,from_id=from_id,
                               to_type=to_type,to_id=to_id,relation=relation)
            counts[sheet]=counts.get(sheet,0)+1
    store.link(source_id,unit_type="cohort",unit_id="HISTORICAL_MASTER_122",evidence_role="original_review_workbook",
               analysis_stage="historical_122",blinding="not-applicable",method_revision="source_workbook_as_recorded")
    return {"status":"IMPORTED_SOURCE_RECORDED_UNVERIFIED","batch_id":batch_id,
            "source_sha256":digest,"indexed_rows":len(prepared),"sheets":counts}


def _members(path: Path):
    """Yield (name, expected_size, stream-opener) after metadata QC."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            members=[]
            for m in z.infolist():
                if m.is_dir():
                    continue
                mode=(m.external_attr>>16) & 0o170000
                if mode==stat.S_IFLNK:
                    raise EvidenceError("ZIP links are forbidden")
                members.append((m.filename,m.file_size,m))
            _validate_member_plan([(n,size) for n,size,_ in members])
            for name,size,meta in members:
                with z.open(meta,"r") as stream:
                    yield name,size,stream
    elif tarfile.is_tarfile(path):
        with tarfile.open(path,"r:*") as tf:
            members=[]
            for m in tf.getmembers():
                if m.isdir():
                    continue
                if not m.isfile():
                    raise EvidenceError(f"Non-regular TAR member: {m.name!r}")
                members.append((m.name,m.size,m))
            _validate_member_plan([(n,size) for n,size,_ in members])
            for name,size,meta in members:
                stream=tf.extractfile(meta)
                if stream is None:
                    raise EvidenceError("Could not read archive member")
                with stream:
                    yield name,size,stream
    else:
        raise EvidenceError("Expected a readable .zip / tar archive")


def _validate_member_plan(plan):
    if len(plan)>MAX_MEMBERS:
        raise EvidenceError("Archive exceeds permitted member count")
    seen=set()
    total=0
    for name,size in plan:
        name=_archive_path(name)
        if name in seen:
            raise EvidenceError("Ambiguous duplicate archive member path")
        seen.add(name)
        if size<0 or size>MAX_MEMBER_SIZE:
            raise EvidenceError(f"Archive member size above safe bound: {name}")
        total+=size
    if total>MAX_ARCHIVE_EXPANDED:
        raise EvidenceError("Archive expanded-size budget exceeded")


def import_archive(store: EvidenceStore, archive: str | Path, *,
                   origin_uri: str, origin_revision: str,
                   expected_sha256: str | None = None) -> dict:
    """Indexes all allowed archive members, stores their real bytes, no extraction."""
    path=Path(archive)
    index=ResearchIndex(store)
    digest=_sha(path)
    if expected_sha256 and digest!=expected_sha256.lower():
        raise EvidenceError("Archive expected digest mismatch")
    prior=index.existing(digest,"archive-member-capture","2.0")
    if prior:
        return {**prior,"source_sha256":digest}
    # Complete metadata validation occurs before archive bytes or members are staged.
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            _validate_member_plan([(m.filename,m.file_size) for m in z.infolist() if not m.is_dir()])
    elif tarfile.is_tarfile(path):
        with tarfile.open(path,"r:*") as tf:
            plan=[]
            for m in tf.getmembers():
                if not m.isdir():
                    if not m.isfile():
                        raise EvidenceError(f"Non-regular TAR member: {m.name}")
                    plan.append((m.name,m.size))
            _validate_member_plan(plan)
    else:
        raise EvidenceError("Not a readable ZIP/TAR archive")
    archive_source,_=store.ingest(path,origin_uri=origin_uri,origin_revision=origin_revision,
                                  scientific_status="candidate",sensitivity="restricted",
                                  media_type="application/octet-stream",expected_sha256=digest,
                                  allow_large=True,note="Source archive retained intact; member names not proof of run validity")
    manifest=[]
    for name,expected_size,stream in _members(path):
        with tempfile.NamedTemporaryFile(prefix="repro-capture-",delete=False) as tmp:
            tmp_path=Path(tmp.name)
            try:
                total=0
                while True:
                    chunk=stream.read(1024*1024)
                    if not chunk:
                        break
                    total+=len(chunk)
                    if total>expected_size or total>MAX_MEMBER_SIZE:
                        raise EvidenceError("Archive member actual size exceeds declared/safe limit")
                    tmp.write(chunk)
                tmp.flush();os.fsync(tmp.fileno())
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
        try:
            if total!=expected_size:
                raise EvidenceError("Archive member byte count mismatch")
            source_id,sha=store.ingest(tmp_path,origin_uri=f"{origin_uri}#sha256:{digest}/{name}",
                                       origin_revision=f"archive-sha256:{digest}",
                                       scientific_status="candidate",sensitivity="restricted",
                                       media_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
                                       note=f"Original archive member {name}",allow_large=True)
            manifest.append((name,total,source_id,sha))
        finally:
            tmp_path.unlink(missing_ok=True)
    with store._open() as cx:
        batch_id=index.begin_batch(cx,archive_source,digest,"archive-member-capture","2.0",len(manifest))
        for ordinal,(name,size,source_id,sha) in enumerate(manifest,1):
            mt=mimetypes.guess_type(name)[0] or "application/octet-stream"
            cx.execute("INSERT INTO archive_members(batch_id,source_id,member_path,member_sha256,member_bytes,media_type,inferred_kind) VALUES (?,?,?,?,?,?,?)",
                       (batch_id,source_id,name,sha,size,mt,_kind(name)))
            index.add_record(cx,batch_id,locus="archive:"+name,row_index=ordinal,
                             unit_type="archive_member",unit_id=f"{digest}:{name}",
                             stage="raw_capture",kind="byte_preserved_unclassified",
                             payload={"archive_sha256":digest,"path":name,"sha256":sha,"bytes":size})
    store.link(archive_source,unit_type="other",unit_id="archive:"+digest,
               evidence_role="original_archive",analysis_stage="source_intake",blinding="not-applicable",
               method_revision="archive_member_capture_2.0")
    return {"status":"ARCHIVE_AND_MEMBERS_CAPTURED_UNCLASSIFIED", "batch_id":batch_id,
            "source_sha256":digest, "members":len(manifest),"member_types":{k:sum(_kind(n)==k for n,_,_,_ in manifest) for k in sorted(set(_kind(n) for n,_,_,_ in manifest))}}


def register_runs(store: EvidenceStore, manifest_file: str | Path, *,
                  origin_uri: str, origin_revision: str,
                  expected_sha256: str | None = None) -> dict:
    """Explicit versioned experiment-run crosswalk. Never guess run identities.

    Format: {schema_version:1, source_archive_sha256:<64-hex>, study_id,<...>,
             protocol_revision, runs:[{run_id,arm,case_id?,model?,seed?,files:{role:path}}]}
    All files MUST already exist in a captured archive. No missing asset is
    silently interpreted as a scanner-negative, no-patch or zero failure.
    """
    path=Path(manifest_file)
    digest=_sha(path)
    if expected_sha256 and expected_sha256.lower()!=digest:
        raise EvidenceError("Manifest digest mismatch")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version")!=1:
        raise EvidenceError("Unsupported run manifest schema")
    archive=data.get("source_archive_sha256")
    study=data.get("study_id")
    protocol=data.get("protocol_revision")
    runs=data.get("runs")
    if not all([archive,study,protocol]) or not isinstance(runs,list) or len(runs)>20000:
        raise EvidenceError("Malformed experiment manifest")
    index=ResearchIndex(store)
    prior=index.existing(digest,"explicit-experiment-run-crosswalk","1.0")
    if prior:
        return {**prior,"source_sha256":digest}
    seen=set()
    prepared=[]
    with store._open(readonly=True) as cx:
        rows=cx.execute("SELECT am.member_path,am.member_sha256,am.source_id FROM archive_members am JOIN research_batches b ON b.batch_id=am.batch_id WHERE b.source_sha256=? AND b.adapter='archive-member-capture'",(archive,)).fetchall()
    lookup={a:(b,c) for a,b,c in rows}
    if not lookup:
        raise EvidenceError("Source archive is not imported in this catalog")
    for run in runs:
        if not isinstance(run,dict) or not run.get("run_id") or not run.get("arm") or not isinstance(run.get("files"),dict):
            raise EvidenceError("Run lacks explicit ID, arm or evidence file mapping")
        run_id=str(run["run_id"])
        if run_id in seen:
            raise EvidenceError("Duplicate run ID within study manifest")
        seen.add(run_id)
        assets=[]
        for role, member_path in run["files"].items():
            if not isinstance(member_path,str):
                raise EvidenceError("Run evidence mapping requires an exact member path")
            item=lookup.get(member_path)
            if item is None:
                raise EvidenceError(f"Unrecoverable declared run artifact: {run_id}/{role}/{member_path}")
            assets.append((role,member_path,item[0],item[1]))
        prepared.append((run,assets))
    source_id,_=store.ingest(path,origin_uri=origin_uri,origin_revision=origin_revision,
                             scientific_status="candidate",sensitivity="restricted",
                             media_type="application/json",expected_sha256=digest,
                             note="Explicit experiment-run crosswalk; does not validate outcomes")
    with store._open() as cx:
        batch_id=index.begin_batch(cx,source_id,digest,"explicit-experiment-run-crosswalk","1.0",len(prepared))
        for ordinal,(run,assets) in enumerate(prepared,1):
            case=_id(run.get("case_id"));pair=_id(run.get("pair_id"))
            cur=cx.execute("""INSERT INTO experiment_runs(batch_id,study_id,run_id,case_id,pair_id,arm,model,seed,base_commit_sha,generated_commit_sha,analysis_status,protocol_revision,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (batch_id,study,str(run["run_id"]),case,pair,str(run["arm"]),
                            run.get("model"),_id(run.get("seed")),run.get("base_commit_sha"),
                            run.get("generated_commit_sha"),"unverified",protocol,canonical_json(run)))
            run_pk=cur.lastrowid
            index.add_record(cx,batch_id,locus="run_manifest",row_index=ordinal,unit_type="generation",
                             unit_id=f"{study}:{run['run_id']}",stage=study,kind="declared_run",payload=run)
            for role,member_path,blob_sha,member_source in assets:
                cx.execute("INSERT INTO experiment_run_assets(run_pk,evidence_role,source_id,artifact_sha256,archive_path) VALUES (?,?,?,?,?)",
                           (run_pk,role,member_source,blob_sha,member_path))
            for needed in ("prompt", "generated_patch", "scanner_after"):
                if needed not in run["files"]:
                    cx.execute("INSERT INTO evidence_gaps(dataset,unit_type,unit_id,missing_role,explanation,recorded_utc) VALUES (?,?,?,?,?,?)",
                               (study,"generation",f"{study}:{run['run_id']}",needed,
                                "Not declared in source manifest, cannot assume absence or success",_now()))
    return {"status":"EXPLICIT_RUN_MAP_INDEXED_UNVERIFIED","batch_id":batch_id,
            "source_sha256":digest,"study_id":study,"runs":len(prepared),
            "run_asset_links":sum(len(x[1]) for x in prepared)}


def import_csv_explicit(store: EvidenceStore, path: str | Path, *,
                        origin_uri: str, origin_revision: str, stage: str,
                        unit_type: str, key_columns: list[str],
                        related_columns: list[tuple[str,str,str]] | None = None,
                        expected_sha256: str | None = None) -> dict:
    """Generic CSV importer with *declared* semantic keys and edges.

    Every value remains the exact source string. Use an explicit manifest of
    key/relationship columns; never infer 'final' labels or scan truth.
    """
    if not stage or not unit_type or not key_columns:
        raise EvidenceError("CSV import requires stage, unit and explicit key columns")
    related_columns=related_columns or []
    path=Path(path)
    digest=_sha(path)
    if expected_sha256 and digest!=expected_sha256.lower():
        raise EvidenceError("CSV expected hash mismatch")
    rules={"stage":stage,"unit":unit_type,"keys":key_columns,"links":related_columns}
    adapter="csv-explicit:"+hashlib.sha256(canonical_json(rules).encode()).hexdigest()
    index=ResearchIndex(store)
    prior=index.existing(digest,adapter,"1.0")
    if prior:
        return {**prior,"source_sha256":digest}
    csv.field_size_limit(16*1024*1024)
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f,restkey="__EXTRA_COLUMNS__",restval=None)
        names=reader.fieldnames
        if not names or len(names)>300 or any(not x for x in names):
            raise EvidenceError("CSV headers absent or ambiguous")
        if len(names)!=len(set(names)):
            raise EvidenceError("Duplicate CSV column names are not losslessly addressable")
        for required in key_columns+[v[0] for v in related_columns]:
            if required not in names:
                raise EvidenceError("Missing declared CSV column: "+required)
        prepared=[]
        for rowno,row in enumerate(reader,2):
            if "__EXTRA_COLUMNS__" in row:
                raise EvidenceError("CSV row contains excess fields")
            values=[row.get(k) for k in key_columns]
            uid="|".join(str(x).strip() for x in values) if all(v and str(v).strip() for v in values) else f"csv-row:{rowno}"
            utype=unit_type if all(v and str(v).strip() for v in values) else "document_row"
            edges=[]
            if utype!= "document_row":
                for col,related_type,relation in related_columns:
                    target=row.get(col)
                    if target not in (None,""):
                        edges.append((unit_type,uid,related_type,str(target).strip(),relation))
            prepared.append((rowno,utype,uid,{"headers":names,"fields":row,"row":rowno},edges))
    source_id,_=store.ingest(path,origin_uri=origin_uri,origin_revision=origin_revision,
                             scientific_status="candidate",sensitivity="restricted",
                             media_type="text/csv",expected_sha256=digest,
                             note="CSV rows imported byte-for-byte, stage/keys declared")
    with store._open() as cx:
        batch_id=index.begin_batch(cx,source_id,digest,adapter,"1.0",len(prepared))
        for rowno,utype,uid,payload,edges in prepared:
            index.add_record(cx,batch_id,locus="csv:"+stage,row_index=rowno,unit_type=utype,
                             unit_id=uid,stage=stage,kind="source_csv_row",payload=payload)
            for fr_type,fr_id,to_type,to_id,relation in edges:
                index.add_edge(cx,batch_id,from_type=fr_type,from_id=fr_id,
                               to_type=to_type,to_id=to_id,relation=relation)
    return {"status":"CSV_SOURCE_RECORDED_UNVERIFIED","batch_id":batch_id,
            "source_sha256":digest,"rows":len(prepared),"stage":stage,
            "key_columns":key_columns,"related_columns":related_columns}
