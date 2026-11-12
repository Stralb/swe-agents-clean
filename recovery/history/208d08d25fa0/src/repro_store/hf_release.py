"""Private Hugging Face *release* of an already approved evidence vault.

Default mode is offline preflight. Remote publishing is never implicit and
requires two separate explicit flags. This module contains no credentials.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from .store import EvidenceError, EvidenceStore, _hash_file
from .research import ResearchIndex, canonical_json

DEFAULT_PRIVATE_DATASET="Stralb/malicious-issue-miner-data"


def local_release_manifest(root: str | Path, *, max_bytes: int = 4*1024**3) -> dict:
    store=EvidenceStore(root)
    evidence=ResearchIndex(store).verify()
    if evidence["status"]!="PASS":
        raise EvidenceError("Local archive is not integrity-clean")
    items=[]
    total=0
    for p in sorted(store.root.rglob("*")):
        if p.is_symlink():
            raise EvidenceError("Symlink detected in release directory")
        if not p.is_file():
            continue
        if p.name.endswith(("-wal","-shm","-journal")):
            raise EvidenceError("Live SQLite sidecar in release directory")
        rel=p.relative_to(store.root).as_posix()
        sha,size=_hash_file(p)
        total+=size
        if total>max_bytes:
            raise EvidenceError("Private release exceeds the explicit size limit")
        items.append({"relative_path":rel,"sha256":sha,"bytes":size})
    payload={"format":"arno-evidence-vault","release_schema":1,
             "integrity_status":"PASS", "content_files":items,
             "total_bytes":total,"blinding_boundary":"restricted-private-only",
             "original_research_reproduced":False,
             "human_validated_vulnerabilities":False,
             "remote_publication_completed":False}
    payload["release_id"]=hashlib.sha256(canonical_json(items).encode()).hexdigest()[:24]
    return payload


def publish_private(root: str | Path, *, repo_id: str, max_bytes: int,
                    execute: bool, acknowledged: bool):
    manifest=local_release_manifest(root,max_bytes=max_bytes)
    prefix="reproducibility/releases/"+manifest["release_id"]
    if not execute:
        return {"status":"LOCAL_PREFLIGHT_ONLY","remote_prefix":prefix,"manifest":manifest}
    if not acknowledged:
        raise EvidenceError("Explicit --acknowledge-private-review is required for HF upload")
    if repo_id != DEFAULT_PRIVATE_DATASET:
        raise EvidenceError("HF destination differs from the approved private research dataset")
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise EvidenceError("Install huggingface_hub in an approved environment") from exc
    api=HfApi()
    info=api.repo_info(repo_id=repo_id,repo_type="dataset")
    if not getattr(info,"private",False):
        raise EvidenceError("Refusing upload: target dataset is not private")
    paths=api.list_repo_files(repo_id=repo_id,repo_type="dataset")
    if any(p==prefix or p.startswith(prefix+"/") for p in paths):
        raise EvidenceError("Release prefix already exists; never overwrite HF frozen bytes")
    # upload_folder creates a single Git commit for this folder; its revision
    # is recorded, never assume a moving 'main' alias means frozen evidence.
    result=api.upload_folder(folder_path=str(Path(root).resolve()),repo_id=repo_id,
                             repo_type="dataset",path_in_repo=prefix,
                             commit_message="Add immutable private reproducibility evidence release "+manifest["release_id"])
    oid=getattr(result,"oid",None)
    if not oid:
        raise EvidenceError("HF response lacked immutable revision; inspect remote before publication claims")
    return {"status":"HF_PRIVATE_COMMIT_RECORDED_NOT_DOWNLOADED_VERIFIED",
            "remote_revision":oid,"remote_prefix":prefix,"manifest":manifest}


def main(argv=None):
    p=argparse.ArgumentParser(description="Offline preflight; explicit private HF publication only")
    p.add_argument("vault")
    p.add_argument("--dataset",default=DEFAULT_PRIVATE_DATASET)
    p.add_argument("--max-bytes",type=int,default=4*1024**3)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--acknowledge-private-review",action="store_true")
    args=p.parse_args(argv)
    try:
        r=publish_private(args.vault,repo_id=args.dataset,max_bytes=args.max_bytes,
                          execute=args.execute,acknowledged=args.acknowledge_private_review)
        print(json.dumps(r,indent=2,sort_keys=True))
        return 0
    except (EvidenceError,OSError,ValueError) as ex:
        print(json.dumps({"status":"BLOCKED","error":str(ex)}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
