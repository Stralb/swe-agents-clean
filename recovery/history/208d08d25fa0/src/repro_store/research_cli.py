"""Import and retrieve private research evidence without touching source trees."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .store import EvidenceError, EvidenceStore
from .research import ResearchIndex
from .importers import import_archive, import_workbook, register_runs, import_csv_explicit
from .reviewer import ReviewerView
from .remote_index import RemoteEvidenceLedger
from .source_runs import index_blinded_run_metadata


def make_parser():
    p=argparse.ArgumentParser(description="Create-only evidence import into a new isolated vault")
    sub=p.add_subparsers(dest="cmd",required=True)
    init=sub.add_parser("init",help="Create a completely NEW private evidence-vault directory")
    init.add_argument("vault")
    for name in ("import-workbook","import-archive","register-runs","import-csv"):
        q=sub.add_parser(name)
        q.add_argument("vault")
        q.add_argument("file")
        q.add_argument("--origin-uri",required=True)
        q.add_argument("--origin-revision",required=True)
        q.add_argument("--expected-sha256")
        if name=="import-csv":
            q.add_argument("--stage",required=True)
            q.add_argument("--unit-type",required=True)
            q.add_argument("--key-column",action="append",required=True)
            q.add_argument("--relate",nargs=3,action="append",metavar=("SOURCE_COLUMN","UNIT_TYPE","RELATION"))
    q=sub.add_parser("index-s5pair-metadata",help="Index original blinded source rows without inferring arms or patch bytes")
    q.add_argument("vault")
    q.add_argument("manifest_csv")
    q.add_argument("summary_csv")
    q.add_argument("qc_json")
    q=sub.add_parser("register-expectations",help="Index source-expected files without pretending their bytes were imported")
    q.add_argument("vault")
    q.add_argument("file")
    q.add_argument("--origin-uri",required=True)
    q.add_argument("--origin-revision",required=True)
    q.add_argument("--expected-sha256")
    q=sub.add_parser("expectations-coverage")
    q.add_argument("vault")
    q.add_argument("study_id")
    q=sub.add_parser("case-dossier",help="Retrieve source-grounded case, findings and producing-change records")
    q.add_argument("vault")
    q.add_argument("case_id")
    q=sub.add_parser("run-dossier",help="List real run bytes, source metadata and gaps")
    q.add_argument("vault")
    q.add_argument("study_id")
    q.add_argument("run_id")
    q=sub.add_parser("study-coverage",help="Count captured roles and unresolved run metadata")
    q.add_argument("vault")
    q.add_argument("study_id")
    for name in ("summary","verify"):
        q=sub.add_parser(name)
        q.add_argument("vault")
    q=sub.add_parser("case",help="Show source-annotated records for one case")
    q.add_argument("vault")
    q.add_argument("case_id")
    q=sub.add_parser("export-artifact",help="Create a NEW copy from stored bytes by SHA")
    q.add_argument("vault")
    q.add_argument("sha256")
    q.add_argument("output")
    return p


def main(argv=None):
    args=make_parser().parse_args(argv)
    try:
        if args.cmd=="init":
            EvidenceStore.create(args.vault)
            result={"status":"CREATED","vault":str(Path(args.vault).resolve())}
        else:
            store=EvidenceStore(args.vault)
            if args.cmd=="import-workbook":
                result=import_workbook(store,args.file,origin_uri=args.origin_uri,
                                       origin_revision=args.origin_revision,
                                       expected_sha256=args.expected_sha256)
            elif args.cmd=="import-archive":
                result=import_archive(store,args.file,origin_uri=args.origin_uri,
                                      origin_revision=args.origin_revision,
                                      expected_sha256=args.expected_sha256)
            elif args.cmd=="import-csv":
                result=import_csv_explicit(store,args.file,origin_uri=args.origin_uri,
                                           origin_revision=args.origin_revision,
                                           stage=args.stage,unit_type=args.unit_type,
                                           key_columns=args.key_column,
                                           related_columns=[tuple(x) for x in (args.relate or [])],
                                           expected_sha256=args.expected_sha256)
            elif args.cmd=="register-runs":
                result=register_runs(store,args.file,origin_uri=args.origin_uri,
                                     origin_revision=args.origin_revision,
                                     expected_sha256=args.expected_sha256)
            elif args.cmd=="index-s5pair-metadata":
                result=index_blinded_run_metadata(store,args.manifest_csv,args.summary_csv,args.qc_json)
            elif args.cmd=="register-expectations":
                result=RemoteEvidenceLedger(store).register(args.file,origin_uri=args.origin_uri,
                    origin_revision=args.origin_revision,expected_sha256=args.expected_sha256)
            elif args.cmd=="expectations-coverage":
                result=RemoteEvidenceLedger(store).coverage(args.study_id)
            elif args.cmd=="case-dossier":
                result=ReviewerView(store).case_dossier(args.case_id)
            elif args.cmd=="run-dossier":
                result=ReviewerView(store).run_dossier(args.study_id,args.run_id)
            elif args.cmd=="study-coverage":
                result=ReviewerView(store).study_coverage(args.study_id)
            elif args.cmd=="summary":
                result=ResearchIndex(store).summary()
            elif args.cmd=="verify":
                result=ResearchIndex(store).verify()
            elif args.cmd=="case":
                result=ResearchIndex(store).case(args.case_id)
            elif args.cmd=="export-artifact":
                destination=Path(args.output)
                # Never overwrite any existing path, including a symlink.
                data=store.bytes_for_digest(args.sha256)
                fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                try:
                    with os.fdopen(fd,"wb") as f:
                        f.write(data)
                        f.flush();os.fsync(f.fileno())
                except BaseException:
                    destination.unlink(missing_ok=True)
                    raise
                result={"status":"EXPORTED_PRIVATE_COPY","output":str(destination.absolute()),"sha256":args.sha256}
            else:
                raise EvidenceError("Unknown command")
        print(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False))
        return 0 if result.get("status")!="FAIL" else 2
    except (EvidenceError,OSError,ValueError,RuntimeError) as exc:
        print(json.dumps({"status":"ERROR","error":str(exc)}),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
