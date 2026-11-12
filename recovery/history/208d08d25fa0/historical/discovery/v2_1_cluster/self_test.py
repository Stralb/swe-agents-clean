from pathlib import Path
import tempfile
import numpy as np
import pandas as pd

from v21_common import save_frame
from v21_analysis import eta_omega_squared, stage_redundancy, stage_associations, stage_patterns

rng=np.random.default_rng(123)
# Direct eta/omega correctness.
cat=np.repeat(['a','b','c','d'],100)
x=rng.normal(size=400)
eta,omega,n,k=eta_omega_squared(x,cat)
assert eta < 0.05, (eta,omega)
y=np.repeat([0.,10.,20.,30.],100)+rng.normal(scale=.01,size=400)
eta2,omega2,_,_=eta_omega_squared(y,cat)
assert eta2 > .99 and omega2 > .99, (eta2,omega2)

with tempfile.TemporaryDirectory() as td:
    source=Path(td)/'source';out=Path(td)/'v21';(source/'09_associations').mkdir(parents=True)
    n=800
    repo=np.repeat(np.arange(80),10)
    a=rng.normal(size=n)
    df=pd.DataFrame({
        'case_id':np.arange(n),'repo_id':repo,
        'a':a,'a_duplicate':a,
        'noise':rng.normal(size=n),
        'binary_event':(rng.random(n)<.2).astype(int),
        'category':rng.choice(['x','y','z'],size=n),
        'template__synthetic__T00001':(rng.random(n)<.1).astype(int),
        'text__issue_body__word__topic':rng.integers(0,5,size=n),
        'text__issue_body__word__topic_weight':rng.random(n),
        'text__reltext_ai_markers_marker_text__char__lof':rng.normal(size=n),
        'numeric_by_category':rng.normal(size=n),
    })
    # Add a real category effect.
    df['numeric_by_category'] += df.category.map({'x':0,'y':2,'z':4}).astype(float)
    save_frame(df,source/'09_associations'/'discovery_feature_table')
    stage_redundancy(source,out)
    fa=pd.read_csv(out/'01_redundancy'/'feature_audit.csv')
    for blocked in ['template__synthetic__T00001','text__issue_body__word__topic','text__issue_body__word__topic_weight','text__reltext_ai_markers_marker_text__char__lof']:
        row=fa[fa.feature==blocked].iloc[0]
        assert row.analysis_role != 'primary_observed' and not bool(row.included_in_primary_discovery), row
    pruned=pd.read_parquet(out/'01_redundancy'/'feature_table_pruned.parquet') if (out/'01_redundancy'/'feature_table_pruned.parquet').exists() else pd.read_pickle(out/'01_redundancy'/'feature_table_pruned.pkl')
    assert not any(c.startswith('template__') or c.endswith('__topic') or c.endswith('__topic_weight') for c in pruned.columns)
    stage_associations(source,out)
    rel=pd.read_csv(out/'02_associations'/'relationships_v21.csv')
    r=rel[((rel.a=='numeric_by_category')&(rel.b=='category'))|((rel.b=='numeric_by_category')&(rel.a=='category'))]
    assert len(r)==1 and float(r.iloc[0].effect)<1 and float(r.iloc[0].effect)>.5, r
    stage_patterns(source,out)
    items=pd.read_csv(out/'03_patterns'/'itemization_v21.csv')
    assert not items['item'].astype(str).str.contains('__MISSING__').any()
    assert not items['item'].astype(str).str.contains('binary_event::LEVEL::0|binary_event::V::0').any()
    assert items['item'].astype(str).str.contains('binary_event::PRESENT').any()
print('V21_SELF_TEST=PASS')
