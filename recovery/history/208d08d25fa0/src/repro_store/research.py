"""Append-only structured research index above EvidenceStore's byte vault.

This never opens/migrates the original miner database. All imported values remain
source-recorded observations, not independently validated scientific findings.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from .store import EvidenceError, EvidenceStore, _now

RESEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_schema (
    version INTEGER PRIMARY KEY CHECK(version=2)
);
INSERT OR IGNORE INTO research_schema(version) VALUES (2);
CREATE TABLE IF NOT EXISTS research_batches (
    batch_id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    adapter TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    imported_utc TEXT NOT NULL,
    count_records INTEGER NOT NULL CHECK(count_records>=0),
    UNIQUE(source_sha256,adapter,adapter_version)
);
CREATE TABLE IF NOT EXISTS research_records (
    record_id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES research_batches(batch_id),
    locus TEXT NOT NULL,
    row_index INTEGER NOT NULL CHECK(row_index>=0),
    unit_type TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
    UNIQUE(batch_id,locus,row_index)
);
CREATE INDEX IF NOT EXISTS idx_research_records_unit ON research_records(unit_type,unit_id);
CREATE INDEX IF NOT EXISTS idx_research_records_stage ON research_records(stage,kind);
CREATE TABLE IF NOT EXISTS research_edges (
    edge_id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES research_batches(batch_id),
    from_type TEXT NOT NULL, from_id TEXT NOT NULL,
    to_type TEXT NOT NULL, to_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    UNIQUE(batch_id,from_type,from_id,to_type,to_id,relation)
);
CREATE INDEX IF NOT EXISTS idx_research_edges_from ON research_edges(from_type,from_id);
CREATE INDEX IF NOT EXISTS idx_research_edges_to ON research_edges(to_type,to_id);
CREATE TABLE IF NOT EXISTS research_annotations (
    annotation_id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES research_records(record_id),
    unit_type TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    label_name TEXT NOT NULL,
    label_json TEXT NOT NULL,
    coding_pass TEXT NOT NULL,
    coder_identity TEXT NOT NULL,
    verification TEXT NOT NULL DEFAULT 'source_recorded_not_independently_verified',
    UNIQUE(record_id,label_name,coding_pass)
);
CREATE INDEX IF NOT EXISTS idx_research_ann_unit ON research_annotations(unit_type,unit_id,label_name);
CREATE TABLE IF NOT EXISTS archive_members (
    member_id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES research_batches(batch_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    member_path TEXT NOT NULL,
    member_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    member_bytes INTEGER NOT NULL CHECK(member_bytes>=0),
    media_type TEXT NOT NULL,
    inferred_kind TEXT NOT NULL,
    UNIQUE(batch_id,member_path)
);
CREATE INDEX IF NOT EXISTS idx_archive_members_kind ON archive_members(inferred_kind);
CREATE TABLE IF NOT EXISTS experiment_runs (
    run_pk INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES research_batches(batch_id),
    study_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    case_id TEXT,
    pair_id TEXT,
    arm TEXT NOT NULL,
    model TEXT,
    seed TEXT,
    base_commit_sha TEXT,
    generated_commit_sha TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'unverified',
    protocol_revision TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(batch_id,study_id,run_id)
);
CREATE INDEX IF NOT EXISTS idx_run_lookup ON experiment_runs(study_id,run_id,case_id);
CREATE TABLE IF NOT EXISTS experiment_run_assets (
    run_asset_id INTEGER PRIMARY KEY,
    run_pk INTEGER NOT NULL REFERENCES experiment_runs(run_pk),
    evidence_role TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    artifact_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    archive_path TEXT NOT NULL,
    UNIQUE(run_pk,evidence_role,archive_path)
);
CREATE TABLE IF NOT EXISTS evidence_gaps (
    gap_id INTEGER PRIMARY KEY,
    dataset TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    missing_role TEXT NOT NULL,
    explanation TEXT NOT NULL,
    recorded_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_unit ON evidence_gaps(unit_type,unit_id);
CREATE VIEW IF NOT EXISTS reviewer_annotations AS
  SELECT a.unit_type,a.unit_id,a.stage,a.label_name,a.label_json,a.coding_pass,
         a.coder_identity,a.verification,r.locus,r.row_index,b.source_sha256
  FROM research_annotations a JOIN research_records r ON r.record_id=a.record_id
  JOIN research_batches b ON b.batch_id=r.batch_id;
CREATE VIEW IF NOT EXISTS reviewer_experiment_assets AS
  SELECT x.study_id,x.run_id,x.case_id,x.pair_id,x.arm,x.model,x.seed,x.analysis_status,
         a.evidence_role,a.artifact_sha256,a.archive_path
  FROM experiment_runs x JOIN experiment_run_assets a ON a.run_pk=x.run_pk;
"""

IMMUTABLE_TABLES = [
    "research_schema", "research_batches", "research_records", "research_annotations",
    "archive_members", "experiment_runs", "experiment_run_assets", "evidence_gaps", "research_edges",
]

# The exact sheet and column names were inspected in the frozen 122-case master.
# Labels are source-derived historical observations, not new classifications.
WORKBOOK_RULES = {
    "Issue_PR_Master_122": ("workflow", "Case ID", {
        "Upstream Pattern": "issue_pattern", "Instruction Specificity": "instruction_specificity",
        "Request Scope": "legacy_request_scope", "Upstream Request Summary": "issue_summary",
    }),
    "Stage4B_Blind": ("workflow", "Case ID", {
        "Actual Implementation Summary": "implementation_summary_blind",
        "Evidence Completeness": "implementation_evidence_completeness",
    }),
    "Stage4C_Taxonomy": ("workflow", "Case ID", {
        "First-pass Implementation Pattern": "implementation_pattern_first_pass",
        "Final Implementation Pattern": "implementation_pattern_final",
    }),
    "Context_Source_122": ("workflow", "Case ID", {
        "Primary Agentic Tool": "primary_agentic_tool",
        "Primary Provenance Evidence": "agent_provenance_source",
    }),
    "Step1_Canonical_Findings": ("finding", "Canonical Finding ID", {
        "Canonical Finding": "canonical_finding_description", "QC Status": "canonical_finding_qc",
        "Finding Family": "scanner_finding_family",
    }),
    "Step1_Source_Map": ("finding", "Canonical Finding ID", {}),
    "Step2_Finding_Changes": ("producing_change", "Producing Change ID", {
        "Finding-Producing Change": "producing_change_description",
        "Mapping Status": "finding_change_mapping_status",
        "Mapping Basis": "finding_change_mapping_basis",
    }),
    "Step3_Attribution": ("producing_change", "Producing Change ID", {
        "First-pass Attribution": "attribution_first_pass",
        "Final Attribution": "attribution_final",
        "Attribution Reason": "attribution_reason",
    }),
    "Case_Synthesis": ("workflow", "Case ID", {
        "Goal Alignment": "goal_alignment",
        "Case Evidence Summary": "case_evidence_summary",
        "Synthesis QC Status": "case_synthesis_qc",
    }),
    "Risk_Assessment": ("workflow", "Case ID", {
        "First-pass Risk Label": "risk_first_pass",
        "Final Risk Label": "risk_final",
        "Remaining Uncertainty": "risk_uncertainty",
    }),
    "Excluded_16": ("workflow", "Case ID", {
        "Verdict": "exclusion_verdict", "Reason": "exclusion_reason",
    }),
    "Dependency_Cleanup_Source": ("workflow", "Case ID", {
        "Validation Status": "dependency_validation_status",
        "Keep As Introduced": "dependency_keep_as_introduced",
    }),
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def cell_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, time)):
        return {"type": value.__class__.__name__, "value": value.isoformat()}
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str) and value.startswith("="):
        return {"type": "excel_formula", "formula": value}
    return str(value)


class ResearchIndex:
    def __init__(self, store: EvidenceStore):
        self.store = store
        with store._open() as cx:
            cx.executescript(RESEARCH_SCHEMA)
            for table in IMMUTABLE_TABLES:
                for operation in ("UPDATE", "DELETE"):
                    name = f"research_freeze_{table}_{operation.lower()}"
                    cx.execute(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {operation} ON {table} "
                               "BEGIN SELECT RAISE(ABORT,'immutable research record'); END")

    def existing(self, digest: str, adapter: str, version: str) -> dict | None:
        with self.store._open(readonly=True) as cx:
            row = cx.execute("SELECT batch_id,count_records FROM research_batches WHERE source_sha256=? AND adapter=? AND adapter_version=?", (digest, adapter, version)).fetchone()
        return {"batch_id": row[0], "count_records": row[1], "already_imported": True} if row else None

    def begin_batch(self, cx: sqlite3.Connection, source_id: int, digest: str,
                    adapter: str, version: str, count_records: int) -> int:
        cur = cx.execute("INSERT INTO research_batches(source_id,source_sha256,adapter,adapter_version,imported_utc,count_records) VALUES (?,?,?,?,?,?)",
                         (source_id, digest, adapter, version, _now(), count_records))
        return int(cur.lastrowid)

    def add_record(self, cx: sqlite3.Connection, batch_id: int, *, locus: str,
                   row_index: int, unit_type: str, unit_id: str, stage: str,
                   kind: str, payload: dict[str, Any]) -> int:
        text = canonical_json(payload)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cur = cx.execute("INSERT INTO research_records(batch_id,locus,row_index,unit_type,unit_id,stage,kind,payload_json,payload_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                         (batch_id, locus, row_index, unit_type, unit_id, stage, kind, text, digest))
        return int(cur.lastrowid)

    def add_edge(self, cx: sqlite3.Connection, batch_id: int, *,
                 from_type: str, from_id: str, to_type: str, to_id: str, relation: str) -> None:
        if not all([from_type,from_id,to_type,to_id,relation]):
            raise EvidenceError("Evidence edges require complete identifiers")
        cx.execute("INSERT OR IGNORE INTO research_edges(batch_id,from_type,from_id,to_type,to_id,relation) VALUES (?,?,?,?,?,?)",
                   (batch_id,from_type,str(from_id),to_type,str(to_id),relation))

    def add_annotation(self, cx: sqlite3.Connection, record_id: int, *,
                       unit_type: str, unit_id: str, stage: str,
                       label_name: str, raw_value: Any, coding_pass: str = "source_recorded",
                       coder_identity: str = "historical_source_unspecified") -> None:
        cx.execute("INSERT INTO research_annotations(record_id,unit_type,unit_id,stage,label_name,label_json,coding_pass,coder_identity) VALUES (?,?,?,?,?,?,?,?)",
                   (record_id, unit_type, unit_id, stage, label_name,
                    canonical_json(raw_value), coding_pass, coder_identity))

    def case(self, case_id: str | int) -> dict[str, Any]:
        unit_id = str(case_id)
        with self.store._open(readonly=True) as cx:
            records = cx.execute("SELECT stage,kind,locus,row_index,payload_json FROM research_records WHERE unit_type='workflow' AND unit_id=? ORDER BY record_id", (unit_id,)).fetchall()
            annotations = cx.execute("SELECT stage,label_name,label_json,coding_pass,coder_identity,verification FROM research_annotations WHERE unit_type='workflow' AND unit_id=? ORDER BY annotation_id", (unit_id,)).fetchall()
            gaps = cx.execute("SELECT dataset,missing_role,explanation FROM evidence_gaps WHERE unit_type='workflow' AND unit_id=?", (unit_id,)).fetchall()
            edges = cx.execute("SELECT from_type,from_id,to_type,to_id,relation FROM research_edges WHERE (from_type='workflow' AND from_id=?) OR (to_type='workflow' AND to_id=?) ORDER BY edge_id", (unit_id,unit_id)).fetchall()
        return {"case_id":unit_id,
                "records": [{"stage":a,"kind":b,"locus":c,"row":d,"payload":json.loads(e)} for a,b,c,d,e in records],
                "annotations": [{"stage":a,"label":b,"value":json.loads(c),"pass":d,"coder":e,"verification":f} for a,b,c,d,e,f in annotations],
                "gaps": [{"dataset":a,"role":b,"explanation":c} for a,b,c in gaps],
                "related_units": [{"from_type":a,"from_id":b,"to_type":c,"to_id":d,"relation":e} for a,b,c,d,e in edges]}

    def summary(self) -> dict[str, Any]:
        with self.store._open(readonly=True) as cx:
            counts = {k:cx.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0] for k in ["research_batches", "research_records", "research_annotations", "research_edges", "archive_members", "experiment_runs", "experiment_run_assets", "evidence_gaps"]}
            stages = cx.execute("SELECT stage,COUNT(*) FROM research_records GROUP BY stage ORDER BY stage").fetchall()
        return {"status":"SOURCE_RECORDED_NOT_INDEPENDENTLY_VERIFIED", "counts":counts, "stages":dict(stages)}

    def verify(self) -> dict[str, Any]:
        with self.store._open(readonly=True) as cx:
            rows=cx.execute("SELECT record_id,payload_json,payload_sha256 FROM research_records").fetchall()
            invalid=[row_id for row_id,text,digest in rows if hashlib.sha256(text.encode("utf-8")).hexdigest()!=digest]
            fk=cx.execute("PRAGMA foreign_key_check").fetchall()
        b=self.store.verify()
        return {"status":"PASS" if not invalid and not fk and b["status"]=="PASS" else "FAIL",
                "rows_hashed":len(rows),"record_hash_mismatches":invalid,
                "foreign_key_errors":len(fk),"blob_check":b}
