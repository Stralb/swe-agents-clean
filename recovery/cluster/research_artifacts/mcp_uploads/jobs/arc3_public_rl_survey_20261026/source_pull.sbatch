#!/bin/bash
#SBATCH --job-name=arc3rlsourceaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:24:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026
CLI=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/home_pull"
export HOME="$BASE/home_pull"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
export SURVEY_CLI="$CLI"
export SURVEY_BASE="$BASE"
python3 - <<'PY'
import hashlib,json,os,re,subprocess,time
from pathlib import Path
base=Path(os.environ['SURVEY_BASE'])
cli=os.environ['SURVEY_CLI']
refs=[
'marynaborovska/hybrid-search-and-learn-agent-0-35-lb',
'rauffauzanrambe/arc-reinforcement-learning-for-agi',
'rauffauzanrambe/arc3-agi-reinforcement-agents',
'rauffauzanrambe/arc-agi-3-agent-running-training-v17',
'sinethembanani/dqn-agent',
'princemolakeng/psalm91-agent-dqn-region-clicks',
'thezetaproject/dqn-linalg-arc-agi-3',
'ipfilidzhade/ppo-improvement-2',
'iddrisabdulnasir/arc-agi-3-pamdp-baseline-active-epistemic-rl',
'thomasferraz/arc-agi-3-td-jepa-first-submission-5k-bfs',
'avikdas567/arc-agi-3-neural-world-models-for-spatial-pomdps',
'suneetsaini/arc-agi-3-dreamerv3-icm-agent',
'thezetaproject/theorycoder-rlvr-arc-agi-3',
'nihilisticneuralnet/0-46-arc-agi-3-persistent-memory-bfs-arc-solver',
'inversion/arc3-sample-submission-stochastic-goose',
'ashvinsingh/ash-s-arc-agi-3-agent',
'projectforty2/forge-arc-agi-3-agent',
'vyankteshdwivedi/arc-agi-3-hybrid-solver-bfs-cnn-heuristics',
'imaadmahmood/stochasticgoose-cnn-frame-change-agent',
'gourabr0y555/improved-bfs-curiosity-driven-cnn-fallback',
'ravikaash/qor-arc-agi-3-agent',
'poonszesen/redpill-latent-imaginations-in-dream-rollouts',
'nihilisticneuralnet/0-17-arc-agi-3-residual-cnn-state-graph',
'nihilisticneuralnet/arc-agi-3-monte-carlo-tree-search-solver',
'tkhanna96/arc3-borovska-hybrid-rtx-s5',
'poby7722/versrion-47-is-bset-score-0-54',
'rauffauzanrambe/trigger-aware-bfs-for-game-simulation-score-0-35',
'rauffauzanrambe/arc-agi-3-smart-decision-agent',
'suneetsaini/lb-0-25-arc-agi-3-agent-tuned',
'koushikkumardinda/arc-prize-2026-arc-agi-3-interactive-agent',
'brenorb/arc3-baseline-stochastic-goose',
'ser8147/arc-agi-3-dual-process-agent',
'gourabr0y555/arc-agi-3-graph-based-exploration-agent',
'nihilisticneuralnet/arc-agi-3-graph-based-exploration-lightweight',
'rao?placeholder/no',
]
refs=[x for x in refs if '?placeholder' not in x]
folder=base/'source_archive'
folder.mkdir(exist_ok=True)
report=[]
patterns={
'rl':r'\b(DQN|DoubleDQN|PPO|Q.?learn|actor.?critic|REINFORCE|GAE|TD\(|temporal.diff|bellman|policy.gradient|reward|critic|advantage|replay.buffer)\b',
'update':r'(optimizer\.step|\.backward\(|train_on_batch|GradientTape|optax|partial_fit|train_step)',
'vision':r'(conv2d|Conv2d|torch\.nn|tensorflow|torch\.optim)',
'llm':r'(Qwen|Llama|Gemma|vllm|transformers|AutoTokenizer|AutoModelForCausalLM|langgraph|openai|anthropic|gemini|mistral)',
'engine':r'(load_game|environment_files|deepcopy\(|arcengine|game\.py|importlib)',
}
for i,ref in enumerate(refs):
    d=folder/ref.replace('/','__')
    d.mkdir(exist_ok=True)
    args=[cli,'kernels','pull',ref,'-p',str(d)]
    try:
        res=subprocess.run(args,capture_output=True,text=True,timeout=45)
        if res.returncode:
            print('PULL_FAILED',i+1,ref,res.stderr.strip()[-180:],flush=True)
            report.append({'ref':ref,'error':res.stderr[-300:]})
            continue
        files=list(d.iterdir())
        names=[x.name for x in files if x.is_file()]
        texts=[]
        for f in files:
            if f.is_file() and f.suffix in ('.ipynb','.py','.txt'):
                raw=f.read_text(errors='replace')
                if f.suffix=='.ipynb':
                    try:
                        nb=json.loads(raw)
                        raw='\n\n'.join(''.join(c.get('source',[])) for c in nb.get('cells',[]))
                    except Exception:pass
                texts.append(raw)
        code='\n'.join(texts)
        found={k:len(re.findall(v,code,flags=re.I)) for k,v in patterns.items()}
        excerpt=[]
        for ln in code.splitlines():
            if re.search(r'\b(class (DQN|PPO|.*Agent|.*WorldModel|.*Trainer)|optimizer\.step|\.backward\(|ActorCritic|learn\(|frame.changed|reward.shap|q.?learning|online.train|A2C)\b',ln,flags=re.I):
                excerpt.append(ln.strip()[:140])
            if len(excerpt)>=12:break
        item={'ref':ref,'files':names,'bytes_source':len(code.encode()),'flags':found,'evidence_lines':excerpt,'source_path':str(d)}
        report.append(item)
        print('PULLED',i+1,'/',len(refs),ref,'KB',round(len(code)/1000),'FLAGS',found,'EXCERPT',repr(excerpt[:3]),flush=True)
    except Exception as e:
        print('PULL_EXCEPTION',ref,type(e).__name__,str(e)[:150],flush=True)
        report.append({'ref':ref,'error':str(e)})
    time.sleep(.12)
(base/'source_classification.json').write_text(json.dumps(report,indent=2))
print('DONE',len(report),'OK',sum('error' not in x for x in report))
PY
