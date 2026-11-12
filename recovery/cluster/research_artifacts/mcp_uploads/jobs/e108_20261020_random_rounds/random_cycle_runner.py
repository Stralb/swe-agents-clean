"""Continue rotating development panels after the unused public pool runs out.
Original three disjoint panels and all results remain untouched. This sampler
explicitly discloses recycling; it never opens any protected family. Every
candidate is source-frozen and unit-tested before the random draw is revealed.
"""
import hashlib,json,random,secrets
from pathlib import Path
from datetime import datetime,timezone
import random_round_runner as base

EXPECTED='fa2fc448aadd255d76fe469341485d904db85f854164e1dbbaa8d87125b5fb62'
if base.sha(base.__file__)!=EXPECTED:raise RuntimeError('Original evaluator changed')
original_draw=base.freeze_and_draw


def freeze_draw(args):
    if args.round<=3:return original_draw(args)
    base.verify(base.FIXED)
    candidate=(base.S/args.candidate).resolve()
    previous=(base.S/args.previous).resolve()
    if candidate.parent!=base.S.resolve() or previous.parent!=base.S.resolve():
        raise RuntimeError('Invalid source location')
    hashes=dict(base.FIXED)
    hashes[str(candidate)]=args.candidate_sha;hashes[str(previous)]=args.previous_sha
    # Freeze inherited policies too, not just the entry point.
    for name,expected in (
        ('policy_r1_v1.py','fa64f8ac36680154ba65f44694d7428e4214ffbdb0c6a4e88b19d8f7a57a116d'),
        ('policy_r2.py','24ed9d333af915f3cd394b75acc928102fb62098cedf25c73076d7032f941014'),
        ('policy_r3.py','2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd')):
        hashes[str(base.S/name)]=expected
    base.verify(hashes)
    split=base.load(base.SPLIT,'protected_inventory')
    protected=sorted(set(split.TEST_FAMILIES))
    eligible=sorted(set(split.TRAIN_FAMILIES+split.FORBIDDEN))
    seen=[];last=[]
    for r in range(1,args.round):
        root=base.WORK/('round_%02d'%r)
        if not (root/'ROUND_RESULT.json').is_file():raise RuntimeError('Previous round not complete')
        record=json.loads((root/'SELECTION_FROZEN.json').read_text())
        seen.extend(record['selected_games']);last=record['selected_games']
    unused=sorted(set(eligible)-set(seen))
    allowed=sorted(set(eligible)-set(last))
    if len(allowed)<5:raise RuntimeError('Insufficient no-immediate-repeat pool')
    root=base.WORK/('round_%02d'%args.round);root.mkdir(parents=True,exist_ok=True)
    lock=root/'SELECTION_FROZEN.json'
    if lock.exists():
        data=json.loads(lock.read_text())
        if data['source_hashes']!=hashes or data['budget']!=args.budget or data['policy_seeds']!=args.seeds:
            raise RuntimeError('Frozen repeat draw/config mismatch')
        return root,data
    policy=base.load(candidate,'unit_next_policy');policy.selftest()
    entropy=secrets.token_hex(16);rng=random.Random(int(entropy,16))
    fresh=rng.sample(unused,min(5,len(unused)))
    fill=rng.sample(sorted(set(allowed)-set(fresh)),5-len(fresh))
    selected=fresh+fill;rng.shuffle(selected)
    assert not set(selected).intersection(protected)
    assert not set(selected).intersection(last)
    data={'round':args.round,'created_utc':datetime.now(timezone.utc).isoformat(),
        'random_seed_hex':entropy,'selected_games':selected,
        'sampling':'remaining never-drawn families, then uniform random earlier families; exclude immediately previous panel',
        'eligible_remaining_before_draw':allowed,'previously_drawn_games':seen,
        'previous_panel':last,'first_draw_in_sequence':fresh,'recycled_development_families':fill,
        'protected_families':protected,'source_hashes':hashes,
        'candidate':candidate.name,'previous':previous.name,
        'budget':args.budget,'policy_seeds':args.seeds,'env_seed':0,
        'arms':['candidate','previous','e106','random'],
        'source_code_frozen_before_random_draw':True,
        'historic_project_exposure_disclosed':True,'fresh_private_holdout_claim':False,
        'promotion_target':'2+ levels in 3+ sampled games and better per-game means than previous',
        'all_failures_counted':True,'runner_sha256':base.sha(__file__),
        'original_runner_sha256':EXPECTED,'recycled_panels_are_not_heldout_tests':True}
    base.write_json(lock,data)
    for p,h in hashes.items():
        dest=root/'frozen_sources'/Path(p).name;dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            if base.sha(dest)!=h:raise RuntimeError('Frozen copy conflict')
        else:
            with dest.open('xb') as f:f.write(Path(p).read_bytes())
    print('RANDOM_FIVE_DRAW',json.dumps({k:data[k] for k in ('round','selected_games','random_seed_hex','candidate','previous','first_draw_in_sequence','recycled_development_families','budget','policy_seeds')},sort_keys=True),flush=True)
    return root,data


base.freeze_and_draw=freeze_draw
if __name__=='__main__':base.main()
