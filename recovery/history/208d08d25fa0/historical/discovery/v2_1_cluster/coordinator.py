from __future__ import annotations
import json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

analysis_dir=Path(os.environ["ANALYSIS_DIR"]).resolve()
source=Path(os.environ["SOURCE_RUNROOT"]).resolve()
outroot=Path(os.environ["V21_RUNROOT"]).resolve()
python_bin=os.environ["PYTHON_BIN"]
worker=analysis_dir/"worker.slurm"
logdir=outroot/"logs";logdir.mkdir(parents=True,exist_ok=True)
manifest=outroot/"00_audit"/"SUBMITTED_JOBS_V21.json";manifest.parent.mkdir(parents=True,exist_ok=True)
base_export=f"ALL,ANALYSIS_DIR={analysis_dir},SOURCE_RUNROOT={source},V21_RUNROOT={outroot},PYTHON_BIN={python_bin}"
record={"version":"v2.1-qc-scheduler-1","submitted_at":datetime.now(timezone.utc).isoformat(),"source_runroot":str(source),"outroot":str(outroot),"jobs":{}}

def save():
    tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(record,indent=2,sort_keys=True),encoding='utf-8');tmp.replace(manifest)

def do(cmd):
    print('SBATCH_COMMAND='+' '.join(cmd),flush=True)
    p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);o=(p.stdout or '').strip();print(f'SBATCH_EXIT={p.returncode} OUTPUT={o}',flush=True)
    return (o.split(';')[0].strip() if p.returncode==0 and o else None),o

def submit(stage,candidates,deps=None):
    if stage in record['jobs']:return record['jobs'][stage]['job_id']
    failures=[]
    for part,cpus,mem,wall in candidates:
        cmd=['sbatch','--parsable','--job-name',f'fcv21-{stage}','--partition',part,'--nodes','1','--ntasks','1','--cpus-per-task',str(cpus),'--mem',mem,'--time',wall,'--output',str(logdir/f'fcv21-{stage}-%j.out'),'--error',str(logdir/f'fcv21-{stage}-%j.err'),'--export',base_export+f',STAGE={stage}']
        if deps:cmd+=['--dependency','afterok:'+':'.join(deps)]
        cmd.append(str(worker));jid,msg=do(cmd)
        if jid:
            record['jobs'][stage]={"job_id":jid,"partition":part,"cpus":cpus,"mem":mem,"time":wall,"dependencies":deps or []};save();print(f'STAGE_SUBMITTED={stage}:{jid}:{part}',flush=True);return jid
        failures.append({"partition":part,"error":msg})
    record.setdefault('submission_failures',{})[stage]=failures;save();raise RuntimeError(f'ALL_SUBMISSIONS_FAILED stage={stage} failures={failures}')

BATCH=[('batch',4,'8G','1-00:00:00'),('bigbatch',8,'16G','1-00:00:00')]
STAMPEDE=[('stampede',8,'24G','2-00:00:00'),('bigbatch',8,'64G','2-00:00:00')]
BIGBATCH=[('bigbatch',8,'96G','3-00:00:00'),('biggpu',8,'96G','3-00:00:00')]
BIGGPU=[('biggpu',8,'96G','3-00:00:00'),('bigbatch',8,'96G','3-00:00:00')]

j0=submit('audit',BATCH)
j1=submit('redundancy',BIGGPU,[j0])
j2=submit('associations',BIGGPU,[j1])
j3=submit('motifs',BIGBATCH,[j1])
j4=submit('templates',STAMPEDE,[j1])
j5=submit('temporal',BIGGPU,[j1])
j6=submit('patterns',BIGBATCH,[j2])
j7=submit('stability',BIGGPU,[j2,j5,j6])
j8=submit('catalog',BATCH,[j3,j4,j7])
j9=submit('report',BATCH,[j8])
record['final_report_job']=j9;record['scheduler_status']='FULL_V21_DAG_SUBMITTED';save()
print('COORDINATOR_STATUS=FULL_V21_DAG_SUBMITTED',flush=True);print('FINAL_REPORT_JOB='+j9,flush=True)
