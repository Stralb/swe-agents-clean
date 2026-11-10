#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMMON_INSTRUCTION_PATTERNS = [
    'AGENTS.md','CLAUDE.md','CONTRIBUTING.md','CONTRIBUTING*','README.md','README*',
    '.github/copilot-instructions.md','.github/instructions/**','.cursor/rules/**','.cursor/rules',
    '.windsurfrules','.cursorrules'
]
TEST_RE = re.compile(r'(^|/)(test|tests|__tests__|spec|specs)(/|$)|\.(test|spec)\.[A-Za-z0-9]+$', re.I)

def run(cmd, cwd=None, timeout=180, text=True):
    try:
        p=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=text,timeout=timeout)
        return p.returncode,p.stdout,p.stderr
    except Exception as e:
        return 999,'' if text else b'',repr(e)

def gh_json(endpoint):
    rc,out,err=run(['gh','api',endpoint,'--paginate'],timeout=240)
    if rc!=0:
        return None,err
    try:
        # gh --paginate can concatenate arrays; usually valid JSON array for one page, multiple arrays otherwise.
        return json.loads(out),''
    except Exception:
        # parse concatenated JSON values and flatten arrays
        vals=[]; dec=json.JSONDecoder(); i=0
        try:
            while i < len(out):
                while i<len(out) and out[i].isspace(): i+=1
                if i>=len(out): break
                v,j=dec.raw_decode(out,i); i=j
                if isinstance(v,list): vals.extend(v)
                else: vals.append(v)
            return vals,''
        except Exception as e:
            return None,f'json parse failed: {e}; stderr={err[:1000]}'

def safe_name(s): return re.sub(r'[^A-Za-z0-9_.-]+','__',str(s))[:180]

def ensure_repo(cache:Path, repo:str, base_sha:str, head_sha:str, default_branch:str):
    d=cache/safe_name(repo)
    if not (d/'.git').exists():
        d.mkdir(parents=True,exist_ok=True)
        run(['git','init','-q'],cwd=d)
        run(['git','remote','add','origin',f'https://github.com/{repo}.git'],cwd=d)
    # Fetch exact PR commits and the current default branch. Avoid full history where possible.
    for ref in [base_sha,head_sha]:
        if ref:
            run(['git','fetch','-q','--filter=blob:none','--no-tags','origin',ref],cwd=d,timeout=600)
    if default_branch:
        run(['git','fetch','-q','--filter=blob:none','--no-tags','origin',f'+refs/heads/{default_branch}:refs/remotes/origin/{default_branch}'],cwd=d,timeout=900)
    return d

def git_show(repo_dir, commit, path, max_chars=250000):
    if not commit or not path: return '', 'missing commit/path'
    rc,out,err=run(['git','show',f'{commit}:{path}'],cwd=repo_dir,timeout=300)
    if rc!=0: return '',err
    if len(out)>max_chars: out=out[:max_chars]+'\n[TRUNCATED]\n'
    return out,''

def git_diff(repo_dir, base, head, path, unified=100, max_chars=350000):
    rc,out,err=run(['git','diff',f'--unified={unified}',base,head,'--',path],cwd=repo_dir,timeout=300)
    if rc!=0: return '',err
    if len(out)>max_chars: out=out[:max_chars]+'\n[TRUNCATED]\n'
    return out,''

def normalize_code_line(line):
    s=line.strip()
    if not s or s.startswith('//') or s.startswith('#') or s.startswith('*') or s in {'{','}','(',')','[',']',',',';'}: return None
    s=re.sub(r'\s+',' ',s)
    return s

def added_lines_from_diff(diff):
    out=[]
    for ln in diff.splitlines():
        if ln.startswith('+++') or ln.startswith('@@'): continue
        if ln.startswith('+'):
            n=normalize_code_line(ln[1:])
            if n and len(n)>=4: out.append(n)
    # dedupe preserving order
    seen=set(); z=[]
    for x in out:
        if x not in seen: seen.add(x); z.append(x)
    return z

def persistence_fraction(lines, content):
    if not lines: return None
    norm='\n'.join(normalize_code_line(x) or '' for x in content.splitlines())
    hit=sum(1 for x in lines if x in norm)
    return hit/len(lines)

def parse_iso(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception: return None

def commit_before(repo_dir, ref, dt):
    if not ref or not dt: return None
    rc,out,err=run(['git','rev-list','-1',f'--before={dt.isoformat()}',ref],cwd=repo_dir,timeout=180)
    return out.strip() if rc==0 and out.strip() else None

def grep_base(repo_dir, base_sha, anchors, cap_each=40):
    lines=[]
    for term in anchors:
        term=term.strip()
        if len(term)<4: continue
        rc,out,err=run(['git','grep','-n','-I','-F',term,base_sha,'--',':!node_modules',':!vendor',':!dist',':!build'],cwd=repo_dir,timeout=180)
        hits=out.splitlines()[:cap_each] if rc in (0,1) else []
        lines.append(f'===== TERM: {term} | hits_shown={len(hits)} =====')
        lines.extend(hits)
    return '\n'.join(lines)+'\n'

def instruction_files(repo_dir, base_sha):
    # enumerate tree once, then select likely instruction/docs files
    rc,out,err=run(['git','ls-tree','-r','--name-only',base_sha],cwd=repo_dir,timeout=240)
    if rc!=0: return ''
    files=[]
    for p in out.splitlines():
        low=p.lower()
        bn=Path(p).name.lower()
        if bn in {'agents.md','claude.md','.cursorrules','.windsurfrules'} or low=='.github/copilot-instructions.md' or low.startswith('.cursor/rules/') or low.startswith('.github/instructions/'):
            files.append(p)
        elif bn.startswith('contributing') and len(files)<30:
            files.append(p)
    chunks=[]
    for p in files[:40]:
        txt,e=git_show(repo_dir,base_sha,p,max_chars=50000)
        if txt: chunks.append(f'===== {p} =====\n{txt}')
    return '\n\n'.join(chunks)

def target_review_summary(review_comments, reviews, issue_comments, target_path):
    path_comments=[]
    for x in review_comments or []:
        if isinstance(x,dict) and x.get('path')==target_path:
            path_comments.append(x)
    return {
        'target_file_review_comment_count':len(path_comments),
        'target_file_review_comments':path_comments,
        'review_count':len(reviews or []),
        'reviews':reviews or [],
        'pr_conversation_comments':issue_comments or [],
    }

def process_side(row,side,out_root,cache):
    repo=row[f'{side}_repository']; issue=int(row[f'{side}_issue_number']); pr=int(row[f'{side}_pr_number']); path=row[f'{side}_file_path']
    anchors=[x for x in str(row.get(f'{side}_search_anchors','')).split(';') if x and x!='nan']
    d=out_root/row['pair_id']/side.upper(); d.mkdir(parents=True,exist_ok=True)
    errors=[]
    prj,e=gh_json(f'repos/{repo}/pulls/{pr}');
    if not isinstance(prj,dict):
        (d/'ERROR.txt').write_text('PR metadata failed: '+str(e),encoding='utf-8'); return {'status':'FAILED','error':e}
    repoj,e2=gh_json(f'repos/{repo}')
    default_branch=(repoj or {}).get('default_branch') if isinstance(repoj,dict) else prj.get('base',{}).get('ref')
    base_sha=prj.get('base',{}).get('sha'); head_sha=prj.get('head',{}).get('sha'); merged_at=prj.get('merged_at')
    repo_dir=ensure_repo(cache,repo,base_sha,head_sha,default_branch)
    # Ensure base/head objects exist; pull ref fallback
    if head_sha:
        rc,_,_=run(['git','cat-file','-e',head_sha],cwd=repo_dir)
        if rc!=0: run(['git','fetch','-q','--filter=blob:none','origin',f'pull/{pr}/head'],cwd=repo_dir,timeout=600)
    base_txt,berr=git_show(repo_dir,base_sha,path); head_txt,herr=git_show(repo_dir,head_sha,path)
    diff,derr=git_diff(repo_dir,base_sha,head_sha,path)
    if berr: errors.append('base_file:'+berr[:500])
    if herr: errors.append('head_file:'+herr[:500])
    if derr: errors.append('diff:'+derr[:500])
    (d/'BASE_TARGET_FILE.txt').write_text(base_txt,encoding='utf-8')
    (d/'HEAD_TARGET_FILE.txt').write_text(head_txt,encoding='utf-8')
    (d/'TARGET_DIFF.txt').write_text(diff,encoding='utf-8')
    (d/'PRECHANGE_GREP_HITS.txt').write_text(grep_base(repo_dir,base_sha,anchors),encoding='utf-8')
    (d/'PROJECT_AGENT_INSTRUCTIONS.txt').write_text(instruction_files(repo_dir,base_sha),encoding='utf-8')
    # PR files and test diffs
    files,e=gh_json(f'repos/{repo}/pulls/{pr}/files?per_page=100')
    test_chunks=[]; changed_files=[]
    if isinstance(files,list):
        for f in files:
            if not isinstance(f,dict): continue
            fn=f.get('filename',''); changed_files.append(fn)
            if TEST_RE.search(fn):
                patch=f.get('patch') or ''
                if not patch:
                    patch,_=git_diff(repo_dir,base_sha,head_sha,fn,unified=60,max_chars=120000)
                test_chunks.append(f'===== {fn} =====\n{patch}')
    (d/'PATCH_RELEVANT_TEST_DIFFS.txt').write_text('\n\n'.join(test_chunks),encoding='utf-8')
    # Review / discussion evidence
    review_comments,e=gh_json(f'repos/{repo}/pulls/{pr}/comments?per_page=100')
    reviews,e=gh_json(f'repos/{repo}/pulls/{pr}/reviews?per_page=100')
    pr_comments,e=gh_json(f'repos/{repo}/issues/{pr}/comments?per_page=100')
    issue_comments,e=gh_json(f'repos/{repo}/issues/{issue}/comments?per_page=100')
    review_summary=target_review_summary(review_comments if isinstance(review_comments,list) else [], reviews if isinstance(reviews,list) else [], pr_comments if isinstance(pr_comments,list) else [], path)
    (d/'REVIEW_EVIDENCE.json').write_text(json.dumps(review_summary,indent=2),encoding='utf-8')
    (d/'ISSUE_COMMENTS.json').write_text(json.dumps(issue_comments if isinstance(issue_comments,list) else [],indent=2),encoding='utf-8')
    # Commit chronology
    commits,e=gh_json(f'repos/{repo}/pulls/{pr}/commits?per_page=100')
    (d/'PR_COMMITS.json').write_text(json.dumps(commits if isinstance(commits,list) else [],indent=2),encoding='utf-8')
    # Persistence on default branch at +30/+90 days
    added=added_lines_from_diff(diff)
    mdt=parse_iso(merged_at); ref=f'refs/remotes/origin/{default_branch}' if default_branch else ''
    pers={'merge_time':merged_at,'default_branch':default_branch,'added_decision_file_lines':added,'added_line_count':len(added)}
    for days in (30,90):
        dt=mdt+timedelta(days=days) if mdt else None
        commit=commit_before(repo_dir,ref,dt)
        txt,er=git_show(repo_dir,commit,path) if commit else ('','no commit')
        frac=persistence_fraction(added,txt) if txt else None
        status='UNAVAILABLE' if frac is None else ('PERSISTENT' if frac>=0.80 else ('PARTIAL_OR_MODIFIED' if frac>0 else 'NOT_PRESENT'))
        pers[f'day{days}']={'commit':commit,'fraction_exact_normalized_added_lines_present':frac,'status':status,'file_error':er}
    # later touches within 90d
    if mdt and ref:
        until=mdt+timedelta(days=90)
        rc,log,err=run(['git','log',ref,f'--since={mdt.isoformat()}',f'--until={until.isoformat()}','--format=%H%x09%aI%x09%s','--',path],cwd=repo_dir,timeout=240)
        pers['target_file_commits_first_90d']=log.splitlines()[:100] if rc==0 else []
    (d/'PERSISTENCE.json').write_text(json.dumps(pers,indent=2),encoding='utf-8')
    meta={
        'pair_id':row['pair_id'],'side':side.upper(),'repository':repo,'issue_number':issue,'pr_number':pr,'target_file_path':path,
        'decision_family':row['decision_family'],'decision_summary':row[f'{side}_decision_summary'],'mechanism_summary':row[f'{side}_mechanism_summary'],
        'search_anchors':anchors,'base_sha':base_sha,'head_sha':head_sha,'merged_at':merged_at,'default_branch':default_branch,
        'changed_files':changed_files,'target_file_review_comment_count':review_summary['target_file_review_comment_count'],'errors':errors,'status':'PASS' if diff else 'PARTIAL'
    }
    if side=='positive':
        meta['positive_rule_group']=row.get('positive_rule_group'); meta['positive_rule_ids']=row.get('positive_rule_ids')
    (d/'META.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); ap.add_argument('--out',required=True); ap.add_argument('--cache',required=True); args=ap.parse_args()
    manifest=Path(args.manifest); out=Path(args.out); cache=Path(args.cache); out.mkdir(parents=True,exist_ok=True); cache.mkdir(parents=True,exist_ok=True)
    rows=list(csv.DictReader(manifest.open(encoding='utf-8-sig')))
    summaries=[]
    for i,row in enumerate(rows,1):
        print(f'[{i}/{len(rows)}] {row["pair_id"]}',flush=True)
        for side in ('positive','control'):
            try:
                meta=process_side(row,side,out,cache); summaries.append(meta)
            except Exception as e:
                summaries.append({'pair_id':row['pair_id'],'side':side.upper(),'status':'FAILED','error':repr(e)})
                print('ERROR',row['pair_id'],side,repr(e),flush=True)
    # summary csv/json
    (out/'COLLECTION_SUMMARY.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    fields=sorted({k for x in summaries for k in x.keys() if not isinstance(x.get(k),(dict,list))})
    with (out/'COLLECTION_SUMMARY.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader();
        for x in summaries: w.writerow({k:x.get(k) for k in fields})
    # hashes
    sha=[]
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name!='SHA256SUMS.txt':
            try: h=hashlib.sha256(p.read_bytes()).hexdigest(); sha.append(f'{h}  {p.relative_to(out)}')
            except Exception: pass
    (out/'SHA256SUMS.txt').write_text('\n'.join(sha)+'\n',encoding='utf-8')
    passed=sum(1 for x in summaries if x.get('status')=='PASS'); partial=sum(1 for x in summaries if x.get('status')=='PARTIAL'); failed=len(summaries)-passed-partial
    print(json.dumps({'sides':len(summaries),'pass':passed,'partial':partial,'failed':failed,'out':str(out)},indent=2))

if __name__=='__main__': main()
