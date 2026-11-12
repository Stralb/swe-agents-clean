"""Immutable game-family firewall for E068. Evaluation game IDs never enter actors."""
from pathlib import Path
import hashlib
TRAIN_FAMILIES=('sb26','s5i5','lf52','tn36','g50t')
TEST_FAMILIES=('ar25','cn04','dc22','lp85','m0r0','r11l','re86','sk48','tu93')
FORBIDDEN=('bp35','ka59','ls20','su15','tr87','cd82','ft09','sc25','sp80','vc33','wa30')
assert len(set(TRAIN_FAMILIES+TEST_FAMILIES+FORBIDDEN))==25

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as fp:
  while b:=fp.read(1<<20):h.update(b)
 return h.hexdigest()
