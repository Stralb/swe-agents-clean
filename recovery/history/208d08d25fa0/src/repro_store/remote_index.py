"""Append-only locator ledger for missing ORIGINAL research evidence bytes.

A locator is *not* an imported artifact, a proof that a remote file exists, or
an independently checked checksum. The separate content-addressed vault holds
actual artifact bytes. Query status is resolved dynamically, without rewriting
frozen expectations or replacing historical manifest observations.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .research import ResearchIndex, canonical_json
from .store import EvidenceError, EvidenceStore, _hash_file, _now

HEX = re.compile(r"[a-f0-9]{64}\Z")

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_expectation_schema (
    version INTEGER PRIMARY KEY CHECK(version=1)
);
INSERT OR IGNORE INTO evidence_expectation_schema(version) VALUES (1);
CREATE TABLE IF NOT EXISTS expected_evidence (
    expected_id INTEGER PRIMARY KEY,
    manifest_source_id INTEGER NOT NULL REFERENCES sources(source_id),
    manifest_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    study_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    case_id TEXT,
    evidence_role TEXT NOT NULL,
    remote_uri TEXT NOT NULL,
    expected_sha256 TEXT,
    expected_bytes INTEGER,
    hash_authority TEXT NOT NULL,
    identity_basis TEXT NOT NULL,
    blinding TEXT NOT NULL CHECK(blinding IN ('blind','unblinded','not-applicable')),
    observation_status TEXT NOT NULL CHECK(observation_status IN
        ('remote_source_reported','connector_listed','locally_hash_checked')),
    observed_date TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    UNIQUE(manifest_sha256,study_id,run_id,evidence_role,remote_uri),
    CHECK(expected_sha256 IS NULL OR length(expected_sha256)=64),
    CHECK(expected_bytes IS NULL OR expected_bytes>=0)
);
CREATE INDEX IF NOT EXISTS idx_expectations_study_run ON expected_evidence(study_id,run_id);
CREATE INDEX IF NOT EXISTS idx_expectations_digest ON expected_evidence(expected_sha256);
CREATE TRIGGER IF NOT EXISTS expected_evidence_no_update BEFORE UPDATE ON expected_evidence
  BEGIN SELECT RAISE(ABORT,'immutable expected evidence'); END;
CREATE TRIGGER IF NOT EXISTS expected_evidence_no_delete BEFORE DELETE ON expected_evidence
  BEGIN SELECT RAISE(ABORT,'immutable expected evidence'); END;
"""


class RemoteEvidenceLedger:
    def __init__(self, store: EvidenceStore):
        self.store = store
        ResearchIndex(store)
        with store._open() as cx:
            cx.executescript(LEDGER_SCHEMA)

    def register(self, manifest_path: str | Path, *, origin_uri: str,
                 origin_revision: str, expected_sha256: str | None = None) -> dict:
        src = Path(manifest_path).absolute()
        digest, size = _hash_file(src)
        if expected_sha256 and digest != expected_sha256:
            raise EvidenceError("Remote locator manifest SHA mismatch")
        data = json.loads(src.read_text(encoding="utf-8"))
        if data.get("format") != "arno-readonly-source-expectations-v1":
            raise EvidenceError("Unknown remote locator manifest format")
        observations = data.get("observations")
        if not isinstance(observations,list) or len(observations)>50000:
            raise EvidenceError("Invalid remote locator observations")
        study_id = data.get("study_id")
        obs_date=data.get("observed_date")
        if not isinstance(study_id,str) or not study_id or not isinstance(obs_date,str) or len(obs_date)!=10:
            raise EvidenceError("Missing study/date metadata")
        seen = set()
        prepared=[]
        for i, item in enumerate(observations):
            if not isinstance(item,dict):
                raise EvidenceError("Expected locator object")
            keys = ("run_id", "role", "remote_uri", "hash_authority", "identity_basis", "blinding", "observation_status")
            if any(not isinstance(item.get(k),str) or not item[k].strip() for k in keys):
                raise EvidenceError(f"Missing locator field at index {i}")
            if item["observation_status"] not in ("remote_source_reported","connector_listed","locally_hash_checked"):
                raise EvidenceError("Unsupported observation status")
            if item["blinding"] not in ("blind","unblinded","not-applicable"):
                raise EvidenceError("Unsupported blinding status")
            if item["remote_uri"].startswith("file://") or ".." in item["remote_uri"].split("/"):
                raise EvidenceError("Unsafe remote path")
            sha=item.get("expected_sha256")
            count=item.get("expected_bytes")
            if sha is not None and (not isinstance(sha,str) or not HEX.fullmatch(sha)):
                raise EvidenceError("Expected SHA must be valid lowercase hexadecimal or null")
            if count is not None and (type(count) is not int or count < 0):
                raise EvidenceError("Expected byte count must be nonnegative integer or null")
            if item["observation_status"] == "locally_hash_checked" and (sha is None or count is None):
                raise EvidenceError("Locally checked byte assertion lacks hash or size")
            key=(item["run_id"],item["role"],item["remote_uri"])
            if key in seen:
                raise EvidenceError("Duplicate locator in one frozen inventory")
            seen.add(key)
            prepared.append((item["run_id"],item.get("case_id"),item["role"],item["remote_uri"],sha,count,
                             item["hash_authority"],item["identity_basis"],item["blinding"],item["observation_status"]))
        with self.store._open(readonly=True) as cx:
            duplicate = cx.execute("SELECT COUNT(*) FROM expected_evidence WHERE manifest_sha256=?",(digest,)).fetchone()[0]
        if duplicate:
            return {"status":"ALREADY_REGISTERED_UNCHANGED","manifest_sha256":digest,"expectations":duplicate}
        sid,_=self.store.ingest(src,origin_uri=origin_uri,origin_revision=origin_revision,
                                scientific_status="candidate",sensitivity="restricted",
                                media_type="application/json",expected_sha256=digest,
                                note="Source-reported remote file candidate: no local bytes implied")
        with self.store._open() as cx:
            for rid,cid,role,uri,sha,count,authority,basis,blind,status in prepared:
                cx.execute("""INSERT INTO expected_evidence(
                     manifest_source_id,manifest_sha256,study_id,run_id,case_id,evidence_role,
                     remote_uri,expected_sha256,expected_bytes,hash_authority,identity_basis,
                     blinding,observation_status,observed_date,recorded_utc
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid,digest,study_id,rid,cid,role,uri,sha,count,authority,basis,
                     blind,status,obs_date,_now()))
        self.store.link(sid,unit_type="cohort",unit_id=study_id,evidence_role="source_locator_inventory_not_byte_capture",
                        analysis_stage="remote_candidate_inventory",blinding="blind" if any(x[8]=="blind" for x in prepared) else "not-applicable",
                        method_revision="remote-locator-ledger-1.0")
        return {"status":"LOCATORS_REGISTERED_NO_REMOTE_BYTES_INGESTED",
                "manifest_sha256":digest,"expectations":len(prepared)}

    def coverage(self, study_id: str) -> dict[str, Any]:
        with self.store._open(readonly=True) as cx:
            rows=cx.execute("""SELECT run_id,evidence_role,expected_sha256,expected_bytes,
                remote_uri,hash_authority,identity_basis,observation_status
                FROM expected_evidence WHERE study_id=? ORDER BY expected_id""",(study_id,)).fetchall()
            actual={row[0]:row[1] for row in cx.execute("SELECT sha256,bytes FROM artifacts WHERE sha256 IN (SELECT expected_sha256 FROM expected_evidence WHERE study_id=?)",(study_id,)).fetchall()}
        statuses=[]
        for rid,role,sha,size,uri,authority,basis,observation_status in rows:
            if sha and sha in actual and (size is None or actual[sha]==size):
                try:
                    self.store.bytes_for_digest(sha)
                    state="PRESENT_WITH_VERIFIED_BYTES"
                except EvidenceError:
                    state="PRESENT_BUT_CORRUPT"
            else:
                state="EXPECTED_HASH_NOT_LOCALLY_CAPTURED" if sha else "NO_SOURCE_HASH_AND_NOT_LOCALLY_CAPTURED"
            statuses.append({"run_id":rid,"role":role,"state":state,"sha256":sha,"bytes":size,
                             "source_authority":authority,"identity_basis":basis,"observation_status":observation_status,
                             "remote_uri":uri})
        out={"study_id":study_id,"expected_total":len(rows),"distinct_run_ids":len(set(x[0] for x in rows)),
             "states":{state:sum(x["state"]==state for x in statuses) for state in sorted(set(x["state"] for x in statuses))},
             "rows":statuses,
             "caveat":"Remote locator rows are not preserved patch/scanner bytes; only PRESENT_WITH_VERIFIED_BYTES qualifies as captured"}
        return out
