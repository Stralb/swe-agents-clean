"""CLI for the append-only reproducibility evidence store (no network access)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .store import EvidenceError, EvidenceStore


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local SHA-256 evidence archive; no cluster/HF writes")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a NEW empty directory")
    init.add_argument("root")
    put = sub.add_parser("ingest", help="Copy one approved file into the isolated archive")
    put.add_argument("root")
    put.add_argument("file")
    put.add_argument("--origin-uri", required=True)
    put.add_argument("--origin-revision", required=True)
    put.add_argument("--status", default="candidate", choices=["candidate", "verified", "frozen", "exploratory", "superseded", "buggy", "unresolved"])
    put.add_argument("--sensitivity", default="restricted", choices=["restricted", "internal", "approved-for-release"])
    put.add_argument("--media-type", default="application/octet-stream")
    put.add_argument("--expected-sha256")
    put.add_argument("--allow-large", action="store_true")
    put.add_argument("--note", default="")
    link = sub.add_parser("link", help="Append an evidence/unit relationship")
    link.add_argument("root")
    link.add_argument("source_id", type=int)
    link.add_argument("--unit-type", required=True, choices=["workflow","finding","producing_change","root","control_pair","generation","run","cohort","claim","other"])
    link.add_argument("--unit-id", required=True)
    link.add_argument("--role", required=True)
    link.add_argument("--stage", required=True)
    link.add_argument("--blinding", required=True, choices=["blind","unblinded","not-applicable"])
    link.add_argument("--method-revision", required=True)
    derived = sub.add_parser("derive", help="Record an immutable parent to derived-artifact edge")
    derived.add_argument("root")
    derived.add_argument("--parent-sha256", required=True)
    derived.add_argument("--child-sha256", required=True)
    derived.add_argument("--relationship", required=True)
    derived.add_argument("--code-revision", required=True)
    derived.add_argument("--parameters-sha256")
    for name in ("verify", "manifest"):
        op = sub.add_parser(name)
        op.add_argument("root")
    find = sub.add_parser("find")
    find.add_argument("root")
    find.add_argument("--unit-type", required=True)
    find.add_argument("--unit-id", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            EvidenceStore.create(Path(args.root))
            result = {"status": "CREATED", "root": str(Path(args.root).resolve())}
        else:
            store = EvidenceStore(args.root)
            if args.command == "ingest":
                sid, digest = store.ingest(args.file, origin_uri=args.origin_uri, origin_revision=args.origin_revision,
                                          scientific_status=args.status, sensitivity=args.sensitivity,
                                          media_type=args.media_type, note=args.note,
                                          expected_sha256=args.expected_sha256, allow_large=args.allow_large)
                result = {"source_id": sid, "sha256": digest}
            elif args.command == "link":
                lid = store.link(args.source_id, unit_type=args.unit_type, unit_id=args.unit_id,
                                 evidence_role=args.role, analysis_stage=args.stage,
                                 blinding=args.blinding, method_revision=args.method_revision)
                result = {"link_id": lid}
            elif args.command == "derive":
                rid = store.derive(args.parent_sha256, args.child_sha256, relationship=args.relationship,
                                   code_revision=args.code_revision, parameters_sha256=args.parameters_sha256)
                result = {"derivation_id": rid}
            elif args.command == "verify":
                result = store.verify()
            elif args.command == "find":
                result = store.find(args.unit_type, args.unit_id)
            elif args.command == "manifest":
                result = store.manifest()
            else:
                raise EvidenceError("Unsupported command")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not (isinstance(result, dict) and result.get("status") == "FAIL") else 2
    except (EvidenceError, ValueError, OSError, sqlite3.Error) as err:
        print(json.dumps({"status": "ERROR", "message": str(err)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
