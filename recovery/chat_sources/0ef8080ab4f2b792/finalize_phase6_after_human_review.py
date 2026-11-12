#!/usr/bin/env python3
from __future__ import annotations
import csv, json, argparse
from pathlib import Path
from collections import Counter

def read_csv(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(p, rows, fields=None):
    if fields is None: fields=list(rows[0].keys()) if rows else []
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def kappa(a,b):
    pairs=[(x,y) for x,y in zip(a,b) if x and y]
    if not pairs: return None
    n=len(pairs); po=sum(x==y for x,y in pairs)/n
    la=Counter(x for x,_ in pairs); lb=Counter(y for _,y in pairs)
    cats=set(la)|set(lb)
    pe=sum((la[c]/n)*(lb[c]/n) for c in cats)
    return 1.0 if pe==1 and po==1 else ((po-pe)/(1-pe) if pe<1 else None)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase2', required=True)
    ap.add_argument('--phase3-adjudication', required=True)
    ap.add_argument('--phase3-negative-controls', required=True)
    ap.add_argument('--phase3-dependency-check', required=True)
    ap.add_argument('--phase4-candidates', required=True)
    ap.add_argument('--phase5-adjudication', required=True)
    ap.add_argument('--outdir', required=True)
    args=ap.parse_args(); out=Path(args.outdir); out.mkdir(parents=True,exist_ok=True)

    p2=read_csv(args.phase2); p3=read_csv(args.phase3_adjudication); neg=read_csv(args.phase3_negative_controls)
    dep=read_csv(args.phase3_dependency_check); p4=read_csv(args.phase4_candidates); p5=read_csv(args.phase5_adjudication)
    missing={
      'phase3_priority':sum(not r['Adjudicated Final Label'].strip() for r in p3),
      'phase3_negative_controls':sum(not r['Reviewer Validity Label'].strip() for r in neg),
      'phase3_dependency_cases':sum(not r['Reviewer Check'].strip() for r in dep),
      'phase5_intent_cases':sum(not r['Adjudicated Intent Label'].strip() for r in p5),
    }
    if any(missing.values()):
        result={'status':'BLOCKED_MISSING_HUMAN_REVIEW','missing':missing}
        (out/'PHASE6_FINALIZATION_RESULT.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2)); raise SystemExit(2)

    p3map={r['Study Producing Change ID']:r['Adjudicated Final Label'].strip() for r in p3}
    final=[]
    for r in p2:
        x=dict(r)
        x['Final Human Validity Label']=p3map.get(r['Study Producing Change ID'],r['Final AI-assisted Validity Label'])
        final.append(x)

    current_p4={r['Study Producing Change ID'] for r in p4}
    human_vcw={r['Study Producing Change ID'] for r in final if r['Final Human Validity Label']=='VALID_CODE_WEAKNESS'}
    expansion=sorted(human_vcw-current_p4)
    if expansion:
        rows=[r for r in final if r['Study Producing Change ID'] in expansion]
        write_csv(out/'PHASE6_REQUIRES_PHASE4_PATHWAY_ENRICHMENT.csv',rows)
        result={'status':'BLOCKED_NEW_VALID_CODE_WEAKNESSES_REQUIRE_PHASE4_PHASE5_ENRICHMENT','new_pc_count':len(expansion),'new_pcs':expansion}
        (out/'PHASE6_FINALIZATION_RESULT.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2)); raise SystemExit(3)

    p5cases={r['Case ID']:r['Adjudicated Intent Label'].strip() for r in p5}
    missing_intent_cases=sorted({r['Case ID'] for r in final if r['Final Human Validity Label']=='VALID_CODE_WEAKNESS'}-set(p5cases))
    if missing_intent_cases:
        result={'status':'BLOCKED_NEW_VALID_CASES_REQUIRE_PHASE5_INTENT_REVIEW','cases':missing_intent_cases}
        (out/'PHASE6_FINALIZATION_RESULT.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2)); raise SystemExit(4)

    write_csv(out/'PHASE6_FINAL_HUMAN_VALIDITY_455.csv',final)
    v=Counter(r['Final Human Validity Label'] for r in final)
    p3_overlap=[r for r in p3 if r['Reviewer A Label'].strip() and r['Reviewer B Label'].strip()]
    p5_both=[r for r in p5 if r['Reviewer A Final Public-Intent Label'].strip() and r['Reviewer B Final Public-Intent Label'].strip()]
    summary={
      'status':'FINAL_HUMAN_VALIDATED_READY',
      'validity_counts':dict(v),
      'human_valid_code_weakness_pcs':v.get('VALID_CODE_WEAKNESS',0),
      'phase3_overlap_n':len(p3_overlap),
      'phase3_raw_agreement':(sum(r['Reviewer A Label']==r['Reviewer B Label'] for r in p3_overlap)/len(p3_overlap) if p3_overlap else None),
      'phase3_cohen_kappa':kappa([r['Reviewer A Label'] for r in p3_overlap],[r['Reviewer B Label'] for r in p3_overlap]),
      'phase5_doublecoded_n':len(p5_both),
      'phase5_raw_agreement':(sum(r['Reviewer A Final Public-Intent Label']==r['Reviewer B Final Public-Intent Label'] for r in p5_both)/len(p5_both) if p5_both else None),
      'phase5_cohen_kappa':kappa([r['Reviewer A Final Public-Intent Label'] for r in p5_both],[r['Reviewer B Final Public-Intent Label'] for r in p5_both]),
      'note':'Pathway and intent prevalence must be recomputed only over human-valid code-weakness PCs. No new human-valid PCs were missing from the provisional Phase4 population.'
    }
    (out/'PHASE6_FINAL_HUMAN_SUMMARY.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
