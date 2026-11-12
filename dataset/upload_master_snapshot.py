"""Upload a certified SQLite snapshot and verify its remote size and content ID."""
import argparse,json,os,sqlite3,tempfile,time,shutil
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--workdir',type=Path,required=True);p.add_argument('--repo',default='Stralb/adversarial-swe-agents');a=p.parse_args()
 a.workdir.mkdir(parents=True,exist_ok=True);db=a.database.resolve();cert=json.loads((a.database.parent/'MANIFEST.json').read_text());record=cert['files'][a.database.name]
 expected_hash=record['sha256'];expected_size=db.stat().st_size
 before=(db.stat().st_dev,db.stat().st_ino,db.stat().st_size,db.stat().st_mtime_ns)
 remote_path='archives/master-snapshots/'+expected_hash[:16]+'/adversarial-swe-agents.sqlite'
 report={'state':'VALIDATE_SOURCE','dataset_id':a.repo,'path':remote_path,'database_filename':'adversarial-swe-agents.sqlite','expected_sha256':expected_hash,'expected_bytes':expected_size,'validation_basis':'Existing integrity-checked snapshot certificate; uploader and remote content identifiers verify the bytes. No new full SQLite integrity pass is implied.'}
 def save():
  (a.workdir/'status.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
 save()
 c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);assert c.execute('SELECT COUNT(*) FROM cases').fetchone()[0]==3809;assert c.execute('SELECT COUNT(*) FROM review_v_runs').fetchone()[0]==68;c.close()
 cache=Path(tempfile.gettempdir())/('snapshot-upload-'+os.environ.get('SLURM_JOB_ID','manual'));cache.mkdir(mode=0o700,exist_ok=True)
 os.environ['HF_XET_CACHE']=str(cache/'xet');os.environ['HF_HUB_CACHE']=str(cache/'hub')
 from huggingface_hub import HfApi,hf_hub_download,CommitOperationAdd
 api=HfApi();info=api.repo_info(a.repo,repo_type='dataset',files_metadata=True);assert info.private and info.id==a.repo
 def digest(f):
  lfs=getattr(f,'lfs',None)
  return lfs.get('sha256') if isinstance(lfs,dict) else getattr(lfs,'sha256',None)
 existing=next((f for f in info.siblings if f.rfilename==remote_path),None)
 if existing:
  assert digest(existing)==expected_hash and existing.size==expected_size,'An immutable snapshot path contains unexpected bytes'
  snapshot_commit=info.sha
 else:
  report['state']='UPLOADING';save()
  for attempt in range(1,4):
   report['attempt']=attempt;save()
   try:
    result=api.upload_file(repo_id=a.repo,repo_type='dataset',path_or_fileobj=str(db),path_in_repo=remote_path,commit_message='Back up the complete certified research SQLite snapshot')
    snapshot_commit=result.oid;break
   except Exception as e:
    report.update(last_error_type=type(e).__name__,last_http_status=getattr(getattr(e,'response',None),'status_code',None));save()
    if attempt==3:
     report['state']='UPLOAD_FAILED';save();raise RuntimeError('Snapshot upload failed; see status.json') from None
    time.sleep(10)
 current=db.stat();assert before==(current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns),'Source snapshot changed during transfer'
 info=api.repo_info(a.repo,repo_type='dataset',revision=snapshot_commit,files_metadata=True)
 remote=next(f for f in info.siblings if f.rfilename==remote_path)
 assert digest(remote)==expected_hash and remote.size==expected_size,'Remote size/content SHA-256 mismatch'
 report.update(state='REMOTE_SNAPSHOT_VERIFIED',snapshot_commit=snapshot_commit,remote_sha256=digest(remote),remote_bytes=remote.size,source_changed_during_upload=False,full_sqlite_upload_verified=True)
 receipt=json.dumps(report,indent=2).encode();(a.workdir/'receipt.json').write_bytes(receipt)
 # Update current pointers only after the full object has passed its identity checks.
 latest=api.repo_info(a.repo,repo_type='dataset');base=latest.sha
 pointer=json.loads(Path(hf_hub_download(a.repo,'DATASET.json',repo_type='dataset',revision=base)).read_text())
 naming=json.loads(Path(hf_hub_download(a.repo,'DATABASE_NAME.json',repo_type='dataset',revision=base)).read_text())
 pointer.update(full_sqlite_backup_verified=True,sqlite_snapshot_path=remote_path,sqlite_snapshot_sha256=expected_hash)
 naming.update(full_sqlite_upload_verified=True,sqlite_snapshot_path=remote_path,sqlite_snapshot_commit=snapshot_commit)
 card=Path(hf_hub_download(a.repo,'README.md',repo_type='dataset',revision=base)).read_text()
 link='https://huggingface.co/datasets/'+a.repo+'/blob/'+snapshot_commit+'/'+remote_path
 card+='\n## Complete SQLite snapshot\n\n[adversarial-swe-agents.sqlite]('+link+') — '+str(expected_size)+' bytes. Remote content SHA-256 matches the certified source snapshot: `'+expected_hash+'`. Original source schemas and evidence are retained in this archive. [Backup verification](SQLITE_BACKUP.json).\n'
 ops=[CommitOperationAdd(path_in_repo='SQLITE_BACKUP.json',path_or_fileobj=receipt),CommitOperationAdd(path_in_repo='DATASET.json',path_or_fileobj=json.dumps(pointer,indent=2).encode()),CommitOperationAdd(path_in_repo='DATABASE_NAME.json',path_or_fileobj=json.dumps(naming,indent=2).encode()),CommitOperationAdd(path_in_repo='README.md',path_or_fileobj=card.encode())]
 meta=api.create_commit(repo_id=a.repo,repo_type='dataset',operations=ops,parent_commit=base,commit_message='Record verified full SQLite backup and download pointer')
 check=json.loads(Path(hf_hub_download(a.repo,'SQLITE_BACKUP.json',repo_type='dataset',revision=meta.oid)).read_text());assert check['remote_sha256']==expected_hash
 report.update(state='COMPLETE',metadata_commit=meta.oid);save()
 print('Full snapshot backup complete and remotely verified',flush=True)
if __name__=='__main__':main()
