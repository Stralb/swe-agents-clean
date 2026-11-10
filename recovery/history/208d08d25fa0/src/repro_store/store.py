"""Immutable local research-evidence catalog.

Original inputs are never changed. This is NOT the historical miner database.
Private/sensitive bytes require separate distribution authorization.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class EvidenceError(Exception):
    """Invalid or unsafe evidence operation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE schema_info (version INTEGER NOT NULL CHECK(version = 1));
INSERT INTO schema_info(version) VALUES (1);
CREATE TABLE artifacts (
    sha256 TEXT PRIMARY KEY CHECK(length(sha256)=64),
    bytes INTEGER NOT NULL CHECK(bytes>=0),
    storage TEXT NOT NULL CHECK(storage IN ('inline','object')),
    object_relpath TEXT,
    inline_bytes BLOB,
    media_type TEXT NOT NULL,
    indexed_utc TEXT NOT NULL,
    CHECK ((storage='inline' AND inline_bytes IS NOT NULL AND object_relpath IS NULL)
        OR (storage='object' AND inline_bytes IS NULL AND object_relpath IS NOT NULL))
);
CREATE TABLE sources (
    source_id INTEGER PRIMARY KEY,
    sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    origin_uri TEXT NOT NULL,
    origin_revision TEXT NOT NULL,
    original_name TEXT NOT NULL,
    captured_utc TEXT NOT NULL,
    scientific_status TEXT NOT NULL CHECK(scientific_status IN
      ('candidate','verified','frozen','exploratory','superseded','buggy','unresolved')),
    sensitivity TEXT NOT NULL CHECK(sensitivity IN ('restricted','internal','approved-for-release')),
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE evidence_links (
    link_id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    unit_type TEXT NOT NULL CHECK(unit_type IN
      ('workflow','finding','producing_change','root','control_pair','generation','run','cohort','claim','other')),
    unit_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    analysis_stage TEXT NOT NULL,
    blinding TEXT NOT NULL CHECK(blinding IN ('blind','unblinded','not-applicable')),
    method_revision TEXT NOT NULL,
    linked_utc TEXT NOT NULL
);
CREATE TABLE derivations (
    derivation_id INTEGER PRIMARY KEY,
    parent_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    child_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    relationship TEXT NOT NULL,
    code_revision TEXT NOT NULL,
    parameters_sha256 TEXT,
    recorded_utc TEXT NOT NULL,
    CHECK (parent_sha256 <> child_sha256)
);
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    reference TEXT NOT NULL,
    event_utc TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX idx_sources_sha ON sources(sha256);
CREATE INDEX idx_links_unit ON evidence_links(unit_type,unit_id);
CREATE INDEX idx_links_source ON evidence_links(source_id);
CREATE INDEX idx_derivations_parent ON derivations(parent_sha256);
CREATE INDEX idx_derivations_child ON derivations(child_sha256);
-- Freeze all content and provenance rows; corrections are new inserts.
CREATE TRIGGER freeze_artifacts_update BEFORE UPDATE ON artifacts
  BEGIN SELECT RAISE(ABORT, 'immutable artifacts'); END;
CREATE TRIGGER freeze_artifacts_delete BEFORE DELETE ON artifacts
  BEGIN SELECT RAISE(ABORT, 'immutable artifacts'); END;
CREATE TRIGGER freeze_sources_update BEFORE UPDATE ON sources
  BEGIN SELECT RAISE(ABORT, 'immutable sources'); END;
CREATE TRIGGER freeze_sources_delete BEFORE DELETE ON sources
  BEGIN SELECT RAISE(ABORT, 'immutable sources'); END;
CREATE TRIGGER freeze_links_update BEFORE UPDATE ON evidence_links
  BEGIN SELECT RAISE(ABORT, 'immutable evidence links'); END;
CREATE TRIGGER freeze_links_delete BEFORE DELETE ON evidence_links
  BEGIN SELECT RAISE(ABORT, 'immutable evidence links'); END;
CREATE TRIGGER freeze_derivations_update BEFORE UPDATE ON derivations
  BEGIN SELECT RAISE(ABORT, 'immutable derivations'); END;
CREATE TRIGGER freeze_derivations_delete BEFORE DELETE ON derivations
  BEGIN SELECT RAISE(ABORT, 'immutable derivations'); END;
CREATE TRIGGER freeze_events_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'immutable events'); END;
CREATE TRIGGER freeze_events_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'immutable events'); END;
"""


class EvidenceStore:
    """Append-only catalog with SQLite metadata and SHA-256 objects.

    Bytes <= inline_limit are stored directly in SQLite; larger files are copied
    to a SHA-addressed immutable object under the SAME logical dataset root.
    Both components must travel together in any HF dataset snapshot.
    """

    def __init__(self, root: Path | str, *, inline_limit: int = 1024 * 1024):
        self.root = Path(root).resolve()
        self.db_path = self.root / "catalog.sqlite"
        self.object_root = self.root / "objects"
        self.inline_limit = inline_limit
        if inline_limit < 0:
            raise EvidenceError("inline_limit must be nonnegative")
        if not self.db_path.is_file():
            raise EvidenceError("No initialized evidence store at " + str(self.root))

    @classmethod
    def create(cls, root: Path | str, *, inline_limit: int = 1024 * 1024) -> "EvidenceStore":
        target = Path(root).absolute()
        # New isolated workspace only: never reuse an original research tree.
        if target.exists():
            raise EvidenceError("Store destination already exists; refusing to reuse it")
        target.mkdir(parents=True)
        try:
            (target / "objects").mkdir()
            db = target / "catalog.sqlite"
            cx = sqlite3.connect(db)
            try:
                cx.executescript(SCHEMA)
                cx.commit()
            finally:
                cx.close()
            return cls(target, inline_limit=inline_limit)
        except Exception:
            shutil.rmtree(target)
            raise

    @contextmanager
    def _open(self, *, readonly: bool = False):
        if readonly:
            cx = sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)
        else:
            cx = sqlite3.connect(self.db_path, timeout=30)
        try:
            cx.execute("PRAGMA foreign_keys=ON")
            cx.execute("PRAGMA trusted_schema=OFF")
            if readonly:
                cx.execute("PRAGMA query_only=ON")
            ver = cx.execute("SELECT version FROM schema_info").fetchone()
            if ver != (1,):
                raise EvidenceError("Unexpected catalog schema version")
            yield cx
            if not readonly:
                cx.commit()
        except BaseException:
            if not readonly:
                cx.rollback()
            raise
        finally:
            cx.close()

    def ingest(
        self, path: Path | str, *, origin_uri: str, origin_revision: str,
        scientific_status: str = "candidate", sensitivity: str = "restricted",
        media_type: str = "application/octet-stream", note: str = "",
        expected_sha256: str | None = None, allow_large: bool = False,
    ) -> tuple[int, str]:
        path = Path(path).absolute()
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            raise EvidenceError("Only regular, non-symlink source files may be ingested")
        if not origin_uri.strip() or not origin_revision.strip():
            raise EvidenceError("A source URI and an exact version or revision are required")
        if scientific_status not in {"candidate", "verified", "frozen", "exploratory", "superseded", "buggy", "unresolved"}:
            raise EvidenceError("Unknown scientific status")
        if sensitivity not in {"restricted", "internal", "approved-for-release"}:
            raise EvidenceError("Unknown sensitivity status")
        if not media_type.strip():
            raise EvidenceError("media_type required")
        if before.st_size > 512 * 1024 * 1024 and not allow_large:
            raise EvidenceError("File over 512 MiB; explicitly permit large-file copy")
        if self.root == path or self.root in path.parents:
            raise EvidenceError("Cannot ingest store's own files")
        sha, size = _hash_file(path)
        after = path.lstat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise EvidenceError("Source changed during hashing")
        if expected_sha256 is not None and sha != expected_sha256.lower():
            raise EvidenceError("Source SHA-256 differs from expected digest")
        is_inline = size <= self.inline_limit
        relative = None if is_inline else f"objects/{sha[:2]}/{sha[2:]}"
        data = path.read_bytes() if is_inline else None
        if is_inline and hashlib.sha256(data).hexdigest() != sha:
            raise EvidenceError("Source changed during inline capture")
        if not is_inline:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                current_hash, current_size = _hash_file(destination)
                if (current_hash, current_size) != (sha, size):
                    raise EvidenceError("Stored object digest collision or corruption")
            else:
                with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".pending-", delete=False) as tmp:
                    temporary = Path(tmp.name)
                    try:
                        with path.open("rb") as inp:
                            shutil.copyfileobj(inp, tmp, 1024 * 1024)
                        tmp.flush()
                        os.fsync(tmp.fileno())
                    except Exception:
                        temporary.unlink(missing_ok=True)
                        raise
                if _hash_file(temporary) != (sha, size):
                    temporary.unlink(missing_ok=True)
                    raise EvidenceError("Source changed during content-addressed copy")
                # Create-only publication; never replace existing digest paths.
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    if _hash_file(destination) != (sha, size):
                        raise EvidenceError("Concurrent object collision")
                finally:
                    temporary.unlink(missing_ok=True)
        with self._open() as cx:
            cx.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?,?,?)", (
                sha, size, "inline" if is_inline else "object", relative,
                sqlite3.Binary(data) if is_inline else None, media_type, _now()
            ))
            existing = cx.execute("SELECT bytes,storage,object_relpath FROM artifacts WHERE sha256=?", (sha,)).fetchone()
            # A digest may already be present with a different inline threshold.
            if existing[0] != size:
                raise EvidenceError("Catalog integrity error: mismatched stored size")
            cur = cx.execute(
                "INSERT INTO sources(sha256,origin_uri,origin_revision,original_name,captured_utc,scientific_status,sensitivity,note) VALUES (?,?,?,?,?,?,?,?)",
                (sha, origin_uri, origin_revision, path.name, _now(), scientific_status, sensitivity, note),
            )
            source_id = int(cur.lastrowid)
            self._event(cx, "ingest", str(source_id), {"sha256": sha})
        return source_id, sha

    def link(self, source_id: int, *, unit_type: str, unit_id: str, evidence_role: str,
             analysis_stage: str, blinding: str, method_revision: str) -> int:
        if not all([unit_id, evidence_role, analysis_stage, method_revision]):
            raise EvidenceError("Evidence links require meaningful identifiers")
        with self._open() as cx:
            cur = cx.execute("INSERT INTO evidence_links(source_id,unit_type,unit_id,evidence_role,analysis_stage,blinding,method_revision,linked_utc) VALUES (?,?,?,?,?,?,?,?)",
                             (source_id, unit_type, unit_id, evidence_role, analysis_stage, blinding, method_revision, _now()))
            lid = int(cur.lastrowid)
            self._event(cx, "link", str(lid), {"source_id": source_id})
        return lid

    def derive(self, parent: str, child: str, *, relationship: str, code_revision: str,
               parameters_sha256: str | None = None) -> int:
        if not relationship or not code_revision:
            raise EvidenceError("Derivation must name its relationship and executable code revision")
        with self._open() as cx:
            cur = cx.execute("INSERT INTO derivations(parent_sha256,child_sha256,relationship,code_revision,parameters_sha256,recorded_utc) VALUES (?,?,?,?,?,?)",
                             (parent, child, relationship, code_revision, parameters_sha256, _now()))
            rid = int(cur.lastrowid)
            self._event(cx, "derive", str(rid), {"parent": parent, "child": child})
        return rid

    @staticmethod
    def _event(cx: sqlite3.Connection, event: str, ref: str, details: dict[str, Any]) -> None:
        cx.execute("INSERT INTO events(event_type,reference,event_utc,details_json) VALUES (?,?,?,?)",
                   (event, ref, _now(), json.dumps(details, sort_keys=True)))

    def _bytes_for(self, sha: str, storage: str, relpath: str | None, blob: bytes | None) -> bytes | Path:
        if storage == "inline":
            if blob is None:
                raise EvidenceError("Inline artifact bytes missing")
            return blob
        expected = f"objects/{sha[:2]}/{sha[2:]}"
        if relpath != expected:
            raise EvidenceError("Invalid content-addressed object location")
        candidate = self.root / expected
        if candidate.is_symlink() or not candidate.is_file():
            raise EvidenceError("Content-addressed object missing or symlinked")
        return candidate

    def verify(self) -> dict[str, Any]:
        with self._open(readonly=True) as cx:
            integrity = cx.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise EvidenceError("SQLite integrity_check failure: " + integrity)
            rows = cx.execute("SELECT sha256, bytes,storage,object_relpath,inline_bytes FROM artifacts ORDER BY sha256").fetchall()
            bad = []
            for sha, size, storage, relative, blob in rows:
                try:
                    obj = self._bytes_for(sha, storage, relative, blob)
                    actual = (hashlib.sha256(obj).hexdigest(), len(obj)) if isinstance(obj, bytes) else _hash_file(obj)
                    if actual != (sha, size):
                        bad.append({"sha256": sha, "reason": "digest/size mismatch"})
                except Exception as exc:
                    bad.append({"sha256": sha, "reason": str(exc)})
            return {"status": "PASS" if not bad else "FAIL", "artifacts": len(rows), "bad": bad,
                    "sources": cx.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                    "links": cx.execute("SELECT COUNT(*) FROM evidence_links").fetchone()[0]}

    def manifest(self) -> dict[str, Any]:
        with self._open(readonly=True) as cx:
            art = cx.execute("SELECT sha256,bytes,storage,object_relpath,media_type FROM artifacts ORDER BY sha256").fetchall()
            sources = cx.execute("SELECT source_id,sha256,origin_uri,origin_revision,scientific_status,sensitivity FROM sources ORDER BY source_id").fetchall()
            links = cx.execute("SELECT source_id,unit_type,unit_id,evidence_role,analysis_stage,blinding,method_revision FROM evidence_links ORDER BY link_id").fetchall()
            d = cx.execute("SELECT parent_sha256,child_sha256,relationship,code_revision,parameters_sha256 FROM derivations ORDER BY derivation_id").fetchall()
        return {
            "schema_version": 1,
            "artifacts": [dict(zip(("sha256","bytes","storage","object_relpath","media_type"),x)) for x in art],
            "sources": [dict(zip(("source_id","sha256","origin_uri","origin_revision","scientific_status","sensitivity"),x)) for x in sources],
            "evidence_links": [dict(zip(("source_id","unit_type","unit_id","evidence_role","analysis_stage","blinding","method_revision"),x)) for x in links],
            "derivations": [dict(zip(("parent_sha256","child_sha256","relationship","code_revision","parameters_sha256"),x)) for x in d],
        }

    def find(self, unit_type: str, unit_id: str) -> list[dict[str, Any]]:
        with self._open(readonly=True) as cx:
            rows = cx.execute("""SELECT a.sha256,a.bytes,s.origin_uri,s.origin_revision,s.scientific_status,
                s.sensitivity,l.evidence_role,l.analysis_stage,l.blinding,l.method_revision
                FROM evidence_links l JOIN sources s ON l.source_id=s.source_id
                JOIN artifacts a ON a.sha256=s.sha256
                WHERE l.unit_type=? AND l.unit_id=? ORDER BY l.link_id""", (unit_type, unit_id)).fetchall()
        fields = ("sha256","bytes","origin_uri","origin_revision","scientific_status","sensitivity",
                  "evidence_role","analysis_stage","blinding","method_revision")
        return [dict(zip(fields, row)) for row in rows]

    def bytes_for_digest(self, digest: str) -> bytes:
        """Retrieve exact immutable evidence; caller must enforce access policy."""
        with self._open(readonly=True) as cx:
            row = cx.execute("SELECT storage,object_relpath,inline_bytes FROM artifacts WHERE sha256=?", (digest,)).fetchone()
        if row is None:
            raise EvidenceError("Digest not found")
        obj = self._bytes_for(digest, *row)
        data = obj if isinstance(obj, bytes) else obj.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise EvidenceError("Evidence digest mismatch")
        return data
