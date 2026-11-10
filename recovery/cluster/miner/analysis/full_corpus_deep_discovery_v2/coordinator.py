from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

analysis_dir=Path(os.environ["ANALYSIS_DIR"]).resolve()
runroot=Path(os.environ["RUNROOT"]).resolve()
repo=Path(os.environ["REPO"]).resolve()
db=Path(os.environ["DB"]).resolve()
python_bin=os.environ["PYTHON_BIN"]
worker=analysis_dir/"worker.slurm"
logdir=runroot/"logs"; logdir.mkdir(parents=True,exist_ok=True)
manifest=runroot/"00_manifest"/"SUBMITTED_JOBS_V2.json"; manifest.parent.mkdir(parents=True,exist_ok=True)

base_export=f"ALL,ANALYSIS_DIR={analysis_dir},RUNROOT={runroot},REPO={repo},DB={db},PYTHON_BIN={python_bin}"
record={"version":"deep-discovery-v2-scheduler-1","submitted_at":datetime.now(timezone.utc).isoformat(),"runroot":str(runroot),"jobs":{}}

def save():
    tmp=manifest.with_suffix(".tmp")
    tmp.write_text(json.dumps(record,indent=2,sort_keys=True),encoding="utf-8")
    tmp.replace(manifest)

def do_sbatch(cmd):
    print("SBATCH_COMMAND="+" ".join(cmd),flush=True)
    p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    out=(p.stdout or "").strip()
    print(f"SBATCH_EXIT={p.returncode} OUTPUT={out}",flush=True)
    return (out.split(";")[0].strip() if p.returncode==0 and out else None),out

def submit(stage, candidates, dependencies=None):
    if stage in record["jobs"]:
        return record["jobs"][stage]["job_id"]
    failures=[]
    for partition,cpus,mem,wall in candidates:
        cmd=[
            "sbatch","--parsable","--job-name",f"fcdeep-{stage}","--partition",partition,
            "--nodes","1","--ntasks","1","--cpus-per-task",str(cpus),"--mem",mem,"--time",wall,
            "--output",str(logdir/f"fcdeep-{stage}-%j.out"),"--error",str(logdir/f"fcdeep-{stage}-%j.err"),
            "--export",base_export+f",STAGE={stage}",
        ]
        if dependencies:
            cmd += ["--dependency","afterok:"+":".join(dependencies)]
        cmd.append(str(worker))
        jid,out=do_sbatch(cmd)
        if jid:
            record["jobs"][stage]={"job_id":jid,"partition":partition,"cpus":cpus,"mem":mem,"time":wall,"dependencies":dependencies or []}
            save(); print(f"STAGE_SUBMITTED={stage}:{jid}:{partition}",flush=True); return jid
        failures.append({"partition":partition,"cpus":cpus,"mem":mem,"time":wall,"error":out})
    record.setdefault("submission_failures",{})[stage]=failures; save()
    raise RuntimeError(f"ALL_SUBMISSIONS_FAILED stage={stage} failures={failures}")

BIGGPU=[("biggpu",8,"96G","3-00:00:00"),("bigbatch",8,"96G","3-00:00:00")]
BIGBATCH=[("bigbatch",8,"96G","3-00:00:00"),("biggpu",8,"96G","3-00:00:00")]
STAMPEDE=[("stampede",8,"24G","3-00:00:00"),("bigbatch",8,"64G","3-00:00:00")]
BATCH=[("batch",4,"8G","1-00:00:00"),("bigbatch",8,"16G","1-00:00:00")]

# Phase 0: immutable extraction + quality.
j_extract=submit("extract",BIGGPU)
j_quality=submit("quality",BATCH,[j_extract])

# Phase 1: independent schema/raw-representation construction. These are intentionally parallel.
j_struct=submit("structured",BIGGPU,[j_quality])
j_text=submit("text_views",STAMPEDE,[j_quality])
j_path=submit("path_views",STAMPEDE,[j_quality])
j_patch=submit("patch_views",BIGBATCH,[j_quality])
j_syntax=submit("syntax_views",BIGGPU,[j_quality])
reps=[j_struct,j_text,j_path,j_patch,j_syntax]

# Phase 2: expensive independent discovery operators over all representations.
j_models=submit("view_models",BIGGPU,reps)
j_topics=submit("topics",BIGBATCH,reps)
j_templates=submit("templates",STAMPEDE,reps)
j_graphs=submit("graphs",STAMPEDE,reps)

# Cross-view fusion waits for the representations; it can overlap with topics/graphs/templates.
j_cross=submit("crossview",BIGGPU,reps)

# Mixed-type exhaustive associations require latent assignments/topics/templates and cross-view scores.
j_assoc=submit("associations",BIGGPU,[j_models,j_topics,j_templates,j_cross])

# Schema-driven itemset mining and temporal scans branch after the common discovery table exists.
j_freq=submit("frequent_patterns",BIGBATCH,[j_assoc])
j_temp=submit("temporal",STAMPEDE,[j_assoc])
j_stab=submit("stability",BIGGPU,[j_assoc,j_cross])

# Pattern generalizability includes latent/template patterns and the automatically discretized itemsets.
j_gen=submit("generalizability",STAMPEDE,[j_freq,j_models,j_topics,j_templates])

# Deterministic catalogue and report only after all discovery/stability branches are complete.
j_cat=submit("catalog",BATCH,[j_freq,j_temp,j_stab,j_gen,j_graphs,j_templates])
j_report=submit("report",BATCH,[j_cat])
record["final_report_job"]=j_report
record["scheduler_status"]="FULL_DAG_SUBMITTED"
save()
print("COORDINATOR_STATUS=FULL_DEEP_DAG_SUBMITTED",flush=True)
print("FINAL_REPORT_JOB="+j_report,flush=True)
