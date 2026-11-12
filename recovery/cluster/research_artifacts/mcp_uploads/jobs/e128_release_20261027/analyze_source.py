#!/usr/bin/env python3
import ast,hashlib
from pathlib import Path
R=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
src=R/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
s=src.read_text()
print('SOURCE',len(s),len(s.splitlines()),hashlib.sha256(src.read_bytes()).hexdigest())
astroot=ast.parse(s)
lines=s.splitlines()
for n in astroot.body:
 if isinstance(n,ast.ClassDef) and n.name in ('MyAgent','PretrainedPUCTCore','AuditedCrossLevelCore'):
  print('CLASS',n.name,n.lineno,n.end_lineno)
  for x in n.body:
   if isinstance(x,ast.FunctionDef):print('METHOD',x.name,x.lineno,x.end_lineno)
   if isinstance(x,ast.FunctionDef) and x.name in ('__init__','choose_action','is_done','choose','puct_probabilities','start_level'):
    print('BEGIN_METHOD',n.name,x.name)
    for i in range(x.lineno-1,min(x.end_lineno,x.lineno+85)):print(str(i+1)+': '+lines[i][:200])
    print('END_METHOD')
peer=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')
print('PEER_BYTES',peer.stat().st_size,'PEER_SHA',hashlib.sha256(peer.read_bytes()).hexdigest())
for p in [R/'n117_kaggle_20261026_dataset1/private_dataset',R/'click_integrated_audit_e127_20261026/analysis']:
 print('DIRECTORY',p)
 for x in sorted(p.iterdir()):
  if x.is_file():print('FILE',x.name,x.stat().st_size)
print('FILE_SOURCE_HEADER')
for i,line in enumerate(lines[:95],1):print(str(i)+': '+line[:230])
