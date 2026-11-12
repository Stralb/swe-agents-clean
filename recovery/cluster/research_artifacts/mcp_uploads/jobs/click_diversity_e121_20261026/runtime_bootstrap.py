from __future__ import annotations
import ast,hashlib,io,json,os,sys,types,zipfile
from pathlib import Path
BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
ARCHIVE=BASE/'runtime/arc-prize-2026-arc-agi-3.zip'
SITE=BASE/'runtime/python_site'
ENV=BASE/'runtime/environment_files'
EXPECTED='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
SRC=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')

def extract():
    assert SRC.is_file() and hashlib.sha256(SRC.read_bytes()).hexdigest()==EXPECTED
    assert ARCHIVE.is_file()
    SITE.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        files=[n for n in z.namelist() if n.startswith('environment_files/') and not n.endswith('/')]
        assert len(files)>=50
        for n in files:
            target=BASE/'runtime'/n
            assert target.resolve().is_relative_to((BASE/'runtime').resolve())
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.is_file() or target.stat().st_size != z.getinfo(n).file_size:
                target.write_bytes(z.read(n))
        wheels=['arc_agi-0.9.8-py3-none-any.whl','arcengine-0.9.3-py3-none-any.whl']
        for w in wheels:
            with zipfile.ZipFile(io.BytesIO(z.read('arc_agi_3_wheels/'+w))) as wh:
                for name in wh.namelist():
                    dest=(SITE/name).resolve()
                    assert dest.is_relative_to(SITE.resolve())
                wh.extractall(SITE)
    assert len(list(ENV.glob('*/**/*.py')))>=25
    print('STAGED_GAME_FAMILIES',len(list(ENV.iterdir())),flush=True)
    print('STAGED_SDK',SITE,flush=True)

def smoke():
    import importlib.util
    os.environ['OPERATION_MODE']='offline'
    os.environ['ENVIRONMENTS_DIR']=str(ENV)
    os.environ['ARC_ENV_ROOT']=str(ENV)
    sys.path.insert(0,str(SITE))
    fake=types.ModuleType('agents');fake.__path__=[]
    sub=types.ModuleType('agents.agent')
    class Agent:pass
    sub.Agent=Agent
    sys.modules['agents']=fake;sys.modules['agents.agent']=sub
    import numpy as np
    import torch
    import scipy
    from arc_agi import Arcade,OperationMode
    from arcengine import GameAction,GameState
    torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('n117_source_e121',str(SRC))
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    assert hasattr(mod,'AuditedCrossLevelCore')
    arc=Arcade(operation_mode=OperationMode.OFFLINE,environments_dir=str(ENV),recordings_dir=str(BASE/'runtime/recordings'))
    env=arc.make('tu93',seed=47)
    assert env is not None
    obs=env.observation_space
    print('ARC_INITIAL_STATE',str(obs.state),'FRAME_LEN',len(obs.frame),'LEVEL',obs.levels_completed,flush=True)
    if obs.state is GameState.NOT_PLAYED:
        obs=env.step(GameAction.RESET)
        print('ARC_AFTER_RESET',str(obs.state),obs.levels_completed,flush=True)
    frame=np.asarray(obs.frame[-1],dtype=np.uint8).copy()
    assert frame.shape==(64,64)
    legal=np.zeros(7,dtype=bool)
    for ac in obs.available_actions or []:
        legal[int(getattr(ac,'value',ac))-1]=True
    print('ARC_LEGAL',legal.tolist(),'FRAME_SHA',hashlib.sha256(frame.tobytes()).hexdigest(),flush=True)
    core=mod.AuditedCrossLevelCore(checkpoint=None,seed=76,learning=True,prior_enabled=True,puct=True,uniform=False,c=.1,temperature=2.0,mode='local')
    core.start_level(int(obs.levels_completed),frame)
    actions=[]
    for t in range(12):
        pre=np.asarray(obs.frame[-1],np.uint8).copy()
        l=np.zeros(7,dtype=bool)
        for a in obs.available_actions or []:l[int(getattr(a,'value',a))-1]=True
        if not l.any():break
        k=int(core.choose(pre,l))
        legal_code=([1,2,3,4,5,7][k] if k<6 else 6)
        assert l[legal_code-1],('illegal',k,legal_code)
        data=None if k<6 else {'x':int((k-6)%64),'y':int((k-6)//64)}
        new=env.step(GameAction['ACTION'+str(legal_code)],data=data)
        assert new is not None
        post=np.asarray(new.frame[-1],dtype=np.uint8)
        l2=np.zeros(7,dtype=bool)
        for a in new.available_actions or []:l2[int(getattr(a,'value',a))-1]=True
        core.observe(post,l2,int(new.levels_completed),terminal=new.state in (GameState.GAME_OVER,GameState.WIN))
        actions.append({'a':k,'delta':int(np.count_nonzero(pre!=post)),'level':int(new.levels_completed)})
        obs=new
        if new.state in (GameState.GAME_OVER,GameState.WIN):break
    print('SMOKE_ACTIONS',json.dumps(actions),flush=True)
    print('SMOKE_REPORT',json.dumps(core.report()),flush=True)
    (BASE/'runtime/smoke.json').write_text(json.dumps({'source_sha256':EXPECTED,'events':actions,'frames_origin_sha256':hashlib.sha256(frame.tobytes()).hexdigest()},indent=2)+'\n')

if __name__=='__main__':
    if sys.argv[1]=='extract':extract()
    elif sys.argv[1]=='smoke':smoke()
    else:raise SystemExit('usage: python runtime_bootstrap.py extract|smoke')
