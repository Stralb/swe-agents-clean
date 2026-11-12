"""Submit the reviewed dataset cleanup from an authenticated cluster terminal."""
import argparse,datetime,hashlib,shlex,sqlite3,subprocess,urllib.request,uuid
from pathlib import Path

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path);parser.add_argument('--path-token',action='append',default=[]);args=parser.parse_args()
 root=Path.home()/'research_artifacts'
 if args.database:database=args.database
 else:
  candidates=list(root.glob('*REVIEW_RELEASE*/*RESEARCH_MASTER_REVIEW.sqlite'))
  assert len(candidates)==1,'Pass --database with the exact completed review snapshot path'
  database=candidates[0]
 assert database.is_file(),database
 conn=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
 names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_classifications'")];conn.close()
 assert len(names)==1,'Source annotation table is ambiguous'
 original_prefix=names[0][:-len('classifications')].rstrip('_')
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 job=root/'mcp_uploads/jobs'/('dataset_cleanup_'+stamp+'_'+uuid.uuid4().hex[:6]);job.mkdir(parents=True,exist_ok=False);(job/'logs').mkdir()
 revision='f335e5dfc27f88710754e1c008601c55e4dabc36'
 url='https://raw.githubusercontent.com/Stralb/swe-agents-clean/'+revision+'/dataset/clean_hub.py'
 data=urllib.request.urlopen(url,timeout=60).read()
 assert hashlib.sha256(data).hexdigest()=='6a862d5f9e0fe53da8719509494544204649f8d7cd2539255c6037ffbcecd538','Downloaded source checksum mismatch'
 script=job/'clean_hub.py';script.write_bytes(data)
 python=Path.home()/'.venvs/huggingface/bin/python';assert python.is_file(),python
 cmd=[str(python),'-u',str(script),'--bootstrap','--database',str(database),'--output',str(job/'exports'),'--publish','--code-revision',revision]
 for token in dict.fromkeys([original_prefix,*args.path_token]):
  if token:cmd.extend(['--path-token',token])
 batch=job/'job.sbatch';batch.write_text('#!/bin/bash\n#SBATCH --job-name=dataset-cleanup\n#SBATCH --partition=batch\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=4G\n#SBATCH --time=01:00:00\n'+shlex.join(cmd)+'\n')
 result=subprocess.run(['sbatch','--parsable','--chdir',str(job),'--output',str(job/'logs/%j.out'),'--error',str(job/'logs/%j.err'),str(batch)],check=True,text=True,capture_output=True)
 print('Submitted job:',result.stdout.strip());print('Job directory:',job);print('Completion receipt:',job/'exports/UPLOAD_RECEIPT.json')
if __name__=='__main__':main()
