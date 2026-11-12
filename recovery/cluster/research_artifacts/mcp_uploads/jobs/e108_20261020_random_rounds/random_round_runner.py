"""Random-five development rounds. Policy source is frozen before the draw.
No game source or heldout environment is inspected. All outcomes, including
errors, are retained. This is development, not a fresh private benchmark.
"""
import argparse, hashlib, importlib.util, json, logging, os, random, resource
import secrets, sys, time, traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
logging.disable(logging.CRITICAL)
H = Path('/home-mscluster/astrauss')
S = H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
WORK = H/'e108_random_development_rounds'
E106 = H/'research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent'
PROJECT = H/'RL-ARC-AGI-3-Project'
SPLIT = H/'E074_HUMAN_TO_POLICY_20261019/vendor/e068/code/e068_split.py'
FIXED = {
 str(SPLIT): 'b749c2009f0a083afd3b33cefe35224af40832104df213aaa32d24e3492b7989',
 str(PROJECT/'src/adapter.py'): 'c2f3545d65b8d447bc6511312a7ab27f199d97952c5b95e1b9b08926a4e0bd55',
 str(E106/'E106_perception_v0.py'): '78f3d86b77fd05c4409d0a3d900b7353d534ec095b285677e50abff8c1840d2f',
 str(E106/'E106_online_explorer_v0.py'): '9bbcb04e7f1c2c1797e878e60aceeb4150bdbd0bf5a2346bb661859682dca304'
}


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()


def write_json(path, data):
    with Path(path).open('x') as f: json.dump(data, f, indent=2)


def load(path, label):
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(files):
    for name, digest in files.items():
        if sha(name) != digest: raise RuntimeError('Source hash mismatch: '+name)


def freeze_and_draw(args):
    verify(FIXED)
    candidate = (S/args.candidate).resolve()
    if candidate.parent != S.resolve(): raise ValueError('Candidate outside versioned directory')
    verify({str(candidate):args.candidate_sha})
    frozen = dict(FIXED, **{str(candidate):args.candidate_sha})
    if args.previous:
        previous = (S/args.previous).resolve()
        if previous.parent != S.resolve(): raise ValueError('Previous source outside directory')
        verify({str(previous):args.previous_sha})
        frozen[str(previous)] = args.previous_sha
    helper = load(SPLIT, 'frozen_inventory')
    protected = sorted(set(helper.TEST_FAMILIES))
    eligible = sorted(set(helper.TRAIN_FAMILIES + helper.FORBIDDEN))
    assert not set(eligible).intersection(protected)
    root = WORK/('round_%02d'%args.round)
    root.mkdir(parents=True, exist_ok=True)
    selection = root/'SELECTION_FROZEN.json'
    previous_draws=[]
    for r in range(1,args.round):
        p=WORK/('round_%02d'%r)/'SELECTION_FROZEN.json'
        d=json.loads(p.read_text())
        previous_draws.extend(d['selected_games'])
    available = sorted(set(eligible)-set(previous_draws))
    if len(available)<5: raise RuntimeError('Fewer than five unused eligible families; no silent recycling')
    if selection.exists():
        d=json.loads(selection.read_text())
        if d['source_hashes']!=frozen or d['budget']!=args.budget or d['policy_seeds']!=args.seeds:
            raise RuntimeError('Existing frozen draw/config cannot be changed')
        return root,d
    # Verify synthetic mechanics BEFORE drawing the next game sample.
    policy=load(candidate,'unit_policy')
    policy.selftest()
    entropy=secrets.token_hex(16)
    rng=random.Random(int(entropy,16))
    selected=rng.sample(available,5)
    arms=['candidate','previous' if args.previous else 'no_memory','e106','random']
    d={'round':args.round,'created_utc':datetime.now(timezone.utc).isoformat(),
       'random_seed_hex':entropy,'selected_games':selected,'sampling':'uniform without replacement',
       'eligible_remaining_before_draw':available,'previously_drawn_games':previous_draws,
       'protected_families':protected,'source_hashes':frozen,
       'candidate':candidate.name,'previous':args.previous,'budget':args.budget,
       'policy_seeds':args.seeds,'env_seed':0,'arms':arms,
       'source_code_frozen_before_random_draw':True,
       'historic_project_exposure_disclosed':True,'fresh_private_holdout_claim':False,
       'promotion_target':'2+ levels in 3+ sampled games and better per-game means than previous',
       'all_failures_counted':True,'runner_sha256':sha(__file__)}
    write_json(selection,d)
    # Immutable copies allow team to reproduce without mutable external references.
    for path,h in frozen.items():
        out=root/'frozen_sources'/Path(path).name
        out.parent.mkdir(exist_ok=True)
        if out.exists():
            if sha(out)!=h:raise RuntimeError('Frozen source copy conflict')
        else:
            with out.open('xb') as f:f.write(Path(path).read_bytes())
    print('RANDOM_FIVE_DRAW',json.dumps({k:d[k] for k in ('round','selected_games','random_seed_hex','candidate','previous','budget','policy_seeds')},sort_keys=True),flush=True)
    return root,d


def worker(game, rootstr, protocol):
    sys.path[:0]=[str(PROJECT),str(E106),str(S)]
    verify(protocol['source_hashes'])
    import arc_agi
    from arc_agi import OperationMode
    from src.adapter import ArcSession,index_to_action,sample_type_uniform
    from E106_perception_v0 import candidates,descriptor
    from E106_online_explorer_v0 import AdaptiveExplorer
    current=load(S/protocol['candidate'],'current_policy')
    old=load(S/protocol['previous'],'previous_policy') if protocol['previous'] else None
    root=Path(rootstr); arc=arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
    records=[]
    for seed in protocol['policy_seeds']:
        firsts=[]
        for arm in protocol['arms']:
            folder=root/game/str(seed)/arm
            out=folder/'result.json'
            if out.exists():
                rec=json.loads(out.read_text()); records.append(rec)
                if not rec.get('error'):firsts.append(rec['initial_frame_sha256'])
                continue
            folder.mkdir(parents=True,exist_ok=False)
            t0=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_SELF)
            counter=None; result=None
            try:
                random.seed(0);np.random.seed(0)
                session=ArcSession(arc=arc)
                obs=session.start_run(game,protocol['budget'],0)
                counter=session.tracker
                first=hashlib.sha256(obs.frame.tobytes()).hexdigest(); firsts.append(first)
                if arm=='candidate':policy=current.Agent(seed,candidates,descriptor,True)
                elif arm=='no_memory':policy=current.Agent(seed,candidates,descriptor,False)
                elif arm=='previous':policy=old.Agent(seed,candidates,descriptor,True)
                elif arm=='e106':policy=AdaptiveExplorer(seed,'full');policy.reset(obs.frame)
                else:policy=None
                rng=np.random.default_rng(seed)
                frames=[np.asarray(obs.frame,dtype=np.int8).copy()]
                curves=[];actions=0;fatal_states=0;cut160=None
                initial_mask=obs.mask.copy()
                trace=folder/'trace.jsonl'
                with trace.open('x') as f:
                    while not session.done:
                        o=session.obs
                        if arm=='random':a=sample_type_uniform(rng,o.mask);reason='type_uniform_random';prediction=None
                        elif arm=='e106':a,reason,prediction=policy.decide(o.frame,o.mask)
                        else:a,reason,prediction=policy.decide(o.frame,o.mask)
                        if not o.mask[a]:raise RuntimeError('Illegal action selected')
                        aid,xy=index_to_action(int(a));before_actions=counter.actions
                        tr=session.step(int(a));actions+=1
                        advance=tr.reward>0
                        if policy is None:update={}
                        elif arm=='e106':update=policy.update(tr.obs.frame,tr.next_obs.frame,a,tr.reward,advance)
                        else:update=policy.update(tr.obs.frame,tr.next_obs.frame,a,tr.reward,advance,tr.terminal)
                        frames.append(np.asarray(tr.next_obs.frame,dtype=np.int8).copy())
                        terminal_idx=len(frames)-1;post_reset=None
                        if tr.terminal and tr.info.get('state')=='GAME_OVER':
                            fatal_states+=1
                            if not session.done:
                                if arm not in ('random','e106'):policy.episode_reset()
                                frames.append(np.asarray(session.obs.frame,dtype=np.int8).copy())
                                post_reset=len(frames)-1
                        if advance:curves.append({'charged_action':counter.actions,'native_reward':tr.reward,'completed_levels':counter.high_water,'action_id':aid})
                        if cut160 is None and counter.actions>=160:cut160=counter.high_water
                        row={'decision':actions,'charged_before':before_actions,'charged_after':counter.actions,
                             'native_action_id':aid,'index':int(a),'xy':xy,'reason':reason,'prediction':prediction,
                             'observation_update':update,'native_reward':tr.reward,'high_water':counter.high_water,
                             'progress':tr.next_obs.progress,'terminal':tr.terminal,'episode':tr.info.get('episode'),
                             'next_frame_index':terminal_idx,'post_reset_frame_index':post_reset}
                        f.write(json.dumps(row,default=str)+'\n')
                card=session.scorecard()
                if card is None or 'score' not in card:raise RuntimeError('SDK scorecard missing; no fake zero')
                with (folder/'observations.npz').open('xb') as f:np.savez_compressed(f,frames=np.stack(frames))
                write_json(folder/'native_scorecard.json',card)
                if actions+counter.resets!=counter.env_commands:raise RuntimeError('Raw command accounting mismatch')
                if counter.actions!=actions+counter.resets-1:raise RuntimeError('Scorer accounting mismatch')
                if counter.actions>protocol['budget']:raise RuntimeError('Native budget exceeded')
                result={'game':game,'seed':seed,'arm':arm,'completed_levels':counter.high_water,
                    'total_levels':session.obs.win_levels,'won':session.status=='won','score':card['score'],
                    'actions':counter.actions,'decisions':actions,'resets':counter.resets,
                    'raw_commands':counter.env_commands,'game_overs':fatal_states,
                    'progress_at_160':cut160 if cut160 is not None else counter.high_water,
                    'native_progress':curves,'initial_frame_sha256':first,
                    'legal_types':list(map(int,np.flatnonzero(initial_mask[:6]))),
                    'legal_clicks':int(initial_mask[6:].sum()),'stats':dict(policy.stats) if policy else {},
                    'trace_sha256':sha(trace),'frames_sha256':sha(folder/'observations.npz'),
                    'scorecard_sha256':sha(folder/'native_scorecard.json'),'status':session.status,
                    'no_game_id_passed_to_policy':True,'no_recorded_replay':True,
                    'memory_scope':'one game/run; transient state reset on retry; models separated at level changes',
                    'neural_gradient_updates':0}
            except Exception as exc:
                result={'game':game,'seed':seed,'arm':arm,'error':type(exc).__name__+': '+str(exc),
                        'traceback':traceback.format_exc(),'known_charged_actions':getattr(counter,'actions',0)}
            cpu1=resource.getrusage(resource.RUSAGE_SELF)
            result.update({'wall_seconds':round(time.monotonic()-t0,3),
                'cpu_seconds':round(cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,3),
                'process_peak_rss_kb':cpu1.ru_maxrss})
            write_json(out,result);records.append(result)
            print('ROUND_TRIAL',json.dumps({k:result.get(k) for k in ('game','seed','arm','completed_levels','score','actions','game_overs','wall_seconds','error')},sort_keys=True),flush=True)
        if len(set(firsts))>1:raise RuntimeError('Different initial states in paired arms: '+game)
    return records


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--round',type=int,required=True)
    p.add_argument('--candidate',required=True);p.add_argument('--candidate-sha',required=True)
    p.add_argument('--previous',default=None);p.add_argument('--previous-sha',default=None)
    p.add_argument('--seeds',nargs='+',type=int,default=[28901,28902,28903])
    p.add_argument('--budget',type=int,default=512);p.add_argument('--workers',type=int,default=2)
    args=p.parse_args();root,d=freeze_and_draw(args)
    final=root/'ROUND_RESULT.json'
    if final.exists():
        print('ALREADY_COMPLETE_NO_DUPLICATE',str(final),flush=True);return
    outcomes=[]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        tasks={ex.submit(worker,g,str(root),d):g for g in d['selected_games']}
        for future in as_completed(tasks):
            try:outcomes.extend(future.result())
            except Exception as err:
                outcomes.append({'game':tasks[future],'worker_error':str(err),'traceback':traceback.format_exc()})
    result={'round':args.round,'selection':d,'results':outcomes,
        'completed_trials':sum('completed_levels' in x for x in outcomes),
        'errors':[x for x in outcomes if 'error' in x or 'worker_error' in x],
        'expected_trials':5*len(args.seeds)*len(d['arms']),
        'all_updates_are_online_experimental_not_neural_RL':True}
    write_json(final,result)
    summary={g:{arm:[next((x.get('completed_levels','ERR') for x in outcomes if x.get('game')==g and x.get('arm')==arm and x.get('seed')==seed),'MISSING') for seed in args.seeds] for arm in d['arms']} for g in d['selected_games']}
    print('RANDOM_ROUND_COMPLETE',json.dumps({'round':args.round,'results':summary,
        'file':str(final),'sha256':sha(final),'completed':result['completed_trials'],'errors':len(result['errors'])}),flush=True)

if __name__=='__main__': main()
