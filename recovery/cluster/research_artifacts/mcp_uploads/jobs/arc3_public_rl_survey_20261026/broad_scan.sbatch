#!/bin/bash
#SBATCH --job-name=arc3rlcatalogscan
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:19:00
set -euo pipefail
umask 077
BASE="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
CLI="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle"
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/home_broad"
export HOME="$BASE/home_broad"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
export SURVEY_KAGGLE_CLI="$CLI"
export SURVEY_OUT_DIR="$BASE"
python3 - <<'PY'
import json,os,re,subprocess,time
from pathlib import Path
cli=os.environ['SURVEY_KAGGLE_CLI']
base=Path(os.environ['SURVEY_OUT_DIR'])
q=['arc-agi-3','ARC3','Reinforcement','DQN','PPO','Q-learning','Goose','FORGE','BFS','Dreamer','ICM','World Model','neural','policy','explorer','training','MCTS','Go Explore','value','adaptive','model-based','RL']
specs=[('competition-popular-'+str(i),['--competition','arc-prize-2026-arc-agi-3','--page-size','200','-p',str(i),'--sort-by','voteCount']) for i in range(1,5)]
specs += [('search-'+str(i)+'-'+re.sub(r'[^a-z0-9]+','-',term.lower()),['--competition','arc-prize-2026-arc-agi-3','--page-size','200','-s',term,'--sort-by','relevance']) for i,term in enumerate(q)]
dedup={}
summaries=[]
for idx,(name,args) in enumerate(specs):
    cmd=[cli,'kernels','list',*args,'--format','json']
    try:
        v=subprocess.run(cmd,text=True,capture_output=True,timeout=48)
        if v.returncode:
            print('QUERY_FAILED',name,v.returncode,v.stderr.strip()[:170],flush=True)
            continue
        data=json.loads(v.stdout)
        (base/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False))
        if isinstance(data,dict):
            if isinstance(data.get('results'),list): data=data['results']
            elif isinstance(data.get('items'),list): data=data['items']
            else: data=[data]
        if not isinstance(data,list):
            print('BAD_JSON_TYPE',name,type(data).__name__,flush=True)
            continue
        for x in data:
            if not isinstance(x,dict):continue
            k=x.get('ref') or x.get('id') or x.get('kernelRef')
            if k and isinstance(k,str):
                if k not in dedup:dedup[k]={'title':x.get('title',''),'author':x.get('author',''),'votes':x.get('totalVotes',0),'ref':k,'foundBy':[]}
                dedup[k]['foundBy'].append(name)
        summaries.append((name,len(data),len(dedup)))
        print('SCANNED',idx+1,'OF',len(specs),name,'COUNT',len(data),'UNIQUE',len(dedup),flush=True)
    except Exception as e:
        print('QUERY_EXCEPTION',name,type(e).__name__,str(e)[:120],flush=True)
    time.sleep(.15)
items=sorted(dedup.values(),key=lambda x:(-int(x.get('votes') or 0),x['ref']))
(base/'catalog_merged.json').write_text(json.dumps(items,indent=2,ensure_ascii=False))
print('FINAL_UNIQUE',len(items))
for x in items[:130]:
    print('CANDIDATE',x.get('ref'), '|',str(x.get('votes')),'|',str(x.get('title'))[:90])
print('SAVED_FULL_CATALOG',base/'catalog_merged.json')
PY
