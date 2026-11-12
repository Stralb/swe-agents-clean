import csv, json, re, sys
from pathlib import Path

base_sarif, head_sarif, diff_path, pair, repo, base_sha, head_sha, target, out = sys.argv[1:]

def results(path):
    d=json.load(open(path,encoding='utf-8'))
    out=[]
    for run in d.get('runs',[]):
        for r in run.get('results',[]):
            rid=r.get('ruleId','')
            if rid != target:
                continue
            msg=(r.get('message') or {}).get('text','')
            for loc in r.get('locations',[])[:1]:
                pl=(loc.get('physicalLocation') or {})
                art=(pl.get('artifactLocation') or {}).get('uri','')
                reg=pl.get('region') or {}
                line=int(reg.get('startLine') or 0)
                out.append((rid,art,line,msg))
    return out

def added_lines(path):
    added={}
    cur=None
    rx=re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
    for raw in open(path,encoding='utf-8',errors='replace'):
        line=raw.rstrip('\n')
        if line.startswith('+++ b/'):
            cur=line[6:]
            added.setdefault(cur,set())
        elif line.startswith('+++ /dev/null'):
            cur=None
        elif cur:
            m=rx.match(line)
            if m:
                start=int(m.group(1)); count=int(m.group(2) or '1')
                added[cur].update(range(start,start+count))
    return added

def norm(p):
    p=p.replace('file://','').lstrip('./')
    return p

b=results(base_sarif); h=results(head_sarif); add=added_lines(diff_path)
bkeys={(norm(f),ln,m) for _,f,ln,m in b}
introduced=[x for x in h if (norm(x[1]),x[2],x[3]) not in bkeys]
linked=[]
for x in h:
    f=norm(x[1]); ln=x[2]
    # tolerate CodeQL URIs containing a checkout directory prefix
    match=None
    for df, lines in add.items():
        if f==df or f.endswith('/'+df):
            match=(df,lines); break
    if match and ln in match[1]: linked.append(x)
status='PASS' if len(h)>0 and len(linked)>0 else 'FAIL'
row={
 'pair_id':pair,'repository':repo,'base_sha':base_sha,'head_sha':head_sha,'target_rule':target,
 'base_target_count':len(b),'head_target_count':len(h),'introduced_target_count':len(introduced),
 'head_target_on_added_line_count':len(linked),'historical_validation':status,
 'linked_locations':' | '.join(f'{norm(x[1])}:{x[2]}' for x in linked)
}
with open(out,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=row.keys()); w.writeheader(); w.writerow(row)
print(','.join(f'{k}={v}' for k,v in row.items()))
