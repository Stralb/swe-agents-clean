#!/bin/bash
#SBATCH --job-name=arno_hf_inventory_v2
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G

python3 - <<'PY'
import collections
import datetime
import json
import netrc
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

repo="Stralb/malicious-issue-miner-data"
root=Path.home()/"research_artifacts"/"mcp_uploads"/"jobs"/"hf_inventory_20261028_v2"
root.mkdir(parents=True,exist_ok=True)
report={
    "purpose":"Hugging Face remote metadata inventory, read-only",
    "repo_id":repo,
    "collected_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "token_available":False,
    "token_source_type":None,
    "remote_access":"unverified",
    "file_count":0,
    "files":[],
    "errors":[],
}

def credential():
    for key in ("HF_TOKEN","HUGGING_FACE_HUB_TOKEN","HUGGINGFACE_HUB_TOKEN"):
        v=os.environ.get(key)
        if v:
            return v,"environment"
    candidates=[]
    if os.environ.get("HF_TOKEN_PATH"):candidates.append(Path(os.environ["HF_TOKEN_PATH"]))
    if os.environ.get("HF_HOME"):candidates.append(Path(os.environ["HF_HOME"])/"token")
    candidates.extend((Path.home()/".cache"/"huggingface"/"token",Path.home()/".huggingface"/"token"))
    for file in candidates:
        try:
            if file.is_file():
                v=file.read_text().strip()
                if v:return v,"huggingface_token_file"
        except OSError:pass
    try:
        obj=netrc.netrc()
        auth=obj.authenticators("huggingface.co")
        if auth and auth[2]:return auth[2],"netrc"
    except Exception:pass
    return None,None

token,source=credential()
report["token_available"]=bool(token)
report["token_source_type"]=source

def request_json(url):
    req=urllib.request.Request(url,headers={
        "Accept":"application/json",
        "User-Agent":"arno-research-readonly-inventory/1.0",
        **({"Authorization":"Bearer "+token} if token else {})
    },method="GET")
    with urllib.request.urlopen(req,timeout=25) as rsp:
        obj=json.load(rsp)
        link=rsp.headers.get("Link","")
        return obj,link

def safe_next(link):
    for piece in link.split(","):
        segment=piece.strip()
        if 'rel="next"' not in segment and "rel=next" not in segment:continue
        if "<" not in segment or ">" not in segment:continue
        candidate=segment[segment.find("<")+1:segment.find(">")]
        parsed=urllib.parse.urlparse(candidate)
        if parsed.scheme=="https" and parsed.hostname=="huggingface.co" and parsed.path.startswith("/api/datasets/"):
            return candidate
    return None

info_url="https://huggingface.co/api/datasets/"+urllib.parse.quote(repo,safe="/")
try:
    info,_=request_json(info_url)
    report["remote_access"]="dataset_metadata_read"
    report["head_sha"]=info.get("sha")
    report["last_modified"]=info.get("lastModified")
    report["private"]=info.get("private")
    report["gated"]=info.get("gated")
    report["sdk"]=info.get("cardData",{}).get("datasets") if isinstance(info.get("cardData"),dict) else None
    siblings=info.get("siblings") or []
    report["metadata_sibling_count"]=len(siblings)
    report["metadata_filenames"]=[a.get("rfilename") for a in siblings if isinstance(a,dict)]
except Exception as exc:
    report["errors"].append("dataset metadata: "+type(exc).__name__+": "+str(exc)[:500])

if report["remote_access"]=="dataset_metadata_read":
    url="https://huggingface.co/api/datasets/"+urllib.parse.quote(repo,safe="/")+"/tree/main?recursive=true&expand=true"
    seen=set()
    for page in range(1,201):
        try:
            arr,link=request_json(url)
            if not isinstance(arr,list):
                report["errors"].append("unexpected tree response, page "+str(page))
                break
            for entry in arr:
                if not isinstance(entry,dict):continue
                name=entry.get("path")
                if not name or name in seen:continue
                seen.add(name)
                lfs=entry.get("lfs")
                report["files"].append({
                    "path":name,
                    "type":entry.get("type"),
                    "size":entry.get("size"),
                    "oid":entry.get("oid"),
                    "lfs_size":lfs.get("size") if isinstance(lfs,dict) else None
                })
            url=safe_next(link)
            if not url:
                report["pagination_pages"]=page
                break
        except Exception as exc:
            report["errors"].append("tree page "+str(page)+": "+type(exc).__name__+": "+str(exc)[:400])
            break
    report["file_count"]=sum(x["type"]=="file" for x in report["files"])
    report["folder_count"]=sum(x["type"]=="directory" for x in report["files"])
    report["root_folder_counts"]=dict(collections.Counter(x["path"].split("/")[0] for x in report["files"] if x["type"]=="file"))
    report["parquet_file_count"]=sum(x["path"].lower().endswith(".parquet") for x in report["files"])
    report["snapshot_db_file_count"]=sum(x["path"].lower().endswith((".db",".sqlite",".sqlite3")) for x in report["files"])
    report["remote_access"]="tree_read" if report["files"] or report.get("metadata_sibling_count")==0 else "metadata_only"

out=root/"HF_REMOTE_MANIFEST_READONLY.json"
out.write_text(json.dumps(report,indent=2,default=str)+"\n")
summary={k:report.get(k) for k in ("repo_id","remote_access","token_available","token_source_type","private","head_sha","last_modified","file_count","folder_count","parquet_file_count","snapshot_db_file_count","root_folder_counts","errors")}
summary["inventory_path"]=str(out)
(root/"HF_REMOTE_SUMMARY_READONLY.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))
PY
