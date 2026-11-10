#!/usr/bin/env python3
"""Fresh read-only full-population MSR EDA of ARNO master, 2026-11-02."""
import sqlite3,collections,datetime,csv,math,random,statistics,json
from pathlib import Path
P=Path.home()/"research_artifacts"
D=P/"ARNO_MASTER_DB"/"ARNO_RESEARCH_MASTER.sqlite"
T=P/"mcp_uploads"/"jobs"/"icse_msr_v6_20261102"/"results"
T.mkdir(parents=True,exist_ok=True)
conn=sqlite3.connect("file:"+str(D)+"?mode=ro",uri=True,timeout=180)
conn.execute("PRAGMA query_only=ON")
def rows(sql):
 c=conn.execute(sql);return [dict(zip([d[0] for d in c.description],r)) for r in c.fetchall()]
def z(x):
 try:return float(x)
 except:return 0.0
def b(x):return int(str(x).lower() in ("true","yes","1"))
def rd(x):return round(x,5)
def q(v,p):
 v=sorted(v)
 if not v:return None
 k=(len(v)-1)*p;i=int(k);return rd(v[i]+(v[min(i+1,len(v)-1)]-v[i])*(k-i))
def wilson(k,n):
 if not n:return [None,None]
 x=k/n;t=1.959964;d=1+t*t/n
 v=(x+t*t/(2*n))/d;h=t*math.sqrt(x*(1-x)/n+t*t/(4*n*n))/d
 return [rd(v-h),rd(v+h)]
def exact(bv,cv):
 n=bv+cv
 return rd(min(1,2*sum(math.comb(n,k)*.5**n for k in range(min(bv,cv)+1)))) if n else 1
def time(x):
 try:return datetime.datetime.fromisoformat(str(x).replace("Z","+00:00"))
 except:return None
Q={}
C={}
for r in rows("""SELECT c.id case_id,r.full_name repo,i.created_at icreated,i.title issue,i.url issue_url,
i.word_count words,LENGTH(COALESCE(i.body,'')) chars,p.created_at pcreated,p.merged_at merged,
p.url pr_url,p.number prno,p.additions adds,p.deletions dels,p.changed_files_count files,
p.review_comments_count reviews,u.has_code_block codeblock,u.has_file_path path,
u.has_function_or_class func,u.has_traceback_or_log traceback,
u.has_suggested_fix suggestion,u.has_dependency_or_version dep
FROM cases c JOIN repos r ON r.id=c.repo_id JOIN issues i ON i.id=c.issue_id
JOIN pull_requests p ON p.id=c.pr_id LEFT JOIN upstream_features u ON u.issue_id=i.id"""):
 r["case_id"]=int(r["case_id"])
 r["lines"]=z(r["adds"])+z(r["dels"])
 a=time(r["icreated"]);v=time(r["pcreated"])
 r["chronology_bad"]=int(bool(a and v and a>v))
 r["month"]=str(r["merged"] or r["pcreated"] or "")[:7]
 C[r["case_id"]]=r
for r in rows("SELECT case_id,is_positive,scanner_opportunity_signature,source_row_json FROM arno_matched_control_C1_opportunity"):
 Q[int(r["case_id"])]={"positive":int(r["is_positive"]),"signature":r["scanner_opportunity_signature"] or "",
 "detail":json.loads(r["source_row_json"] or "{}")}
for i,c in C.items():c["positive"]=Q[i]["positive"];c["sig"]=Q[i]["signature"]
assert len(C)==len(Q)==3809 and sum(c["positive"] for c in C.values())==192
F=collections.defaultdict(list)
scanrows=rows("SELECT case_id,scanner,rule_id,introduced FROM scanner_findings")
for r in scanrows:
 if r["case_id"] is not None:F[int(r["case_id"])].append(r)
positive_raw={i for i,v in F.items() if any(r["introduced"]==1 for r in v)}
positive_c1={i for i,c in C.items() if c["positive"]}
scans={"CodeQL":("codeql","codeql"),"Semgrep":("semgrep","semgrep"),
 "Trivy":("trivy","trivy-scanner"),"OSV":("osv","osv-scanner"),
 "Gitleaks":("gitleaks","gitleaks"),"Dependency diff":("dependency_diff","dependency-diff")}
S=[];SE={}
for label,(key,raw) in scans.items():
 e={i for i,d in Q.items() if b(d["detail"].get(key+"_complete_opportunity"))}
 d={i for i in e if any(v["introduced"]==1 and v["scanner"]==raw for v in F[i])}
 SE[label]=(e,d)
 S.append({"scanner":label,"eligible":len(e),"positive":len(d),
  "rate":rd(len(d)/len(e)) if e else None,"ci95":wilson(len(d),len(e))})
OV=[]
for a in scans:
 for bb in scans:
  if a>=bb:continue
  ea,da=SE[a];eb,db=SE[bb];w=ea&eb
  OV.append({"a":a,"b":bb,"both_eligible":len(w),"a_only":len(w&da-db),
   "b_only":len(w&db-da),"both":len(w&da&db),"neither":len(w-da-db)})
repo=collections.Counter(c["repo"] for c in C.values())
rp=collections.Counter(c["repo"] for c in C.values() if c["positive"])
def hhi(cc):return sum(x*x for x in cc)/(sum(cc)**2) if sum(cc) else 0
def gini(v):
 v=sorted(v);return 2*sum((i+1)*x for i,x in enumerate(v))/(len(v)*sum(v))-(len(v)+1)/len(v)
observed_hhi=hhi(rp.values());observed_top=sum(sorted(rp.values(),reverse=True)[:10])/192
strata=collections.defaultdict(list)
for i,c in C.items():strata[c["sig"]].append(i)
snum={s:sum(C[i]["positive"] for i in ids) for s,ids in strata.items()}
rs=random.Random(20261102);hh=[];tops=[];nrepos=[]
for _ in range(800):
 counts=collections.Counter()
 for s,ids in strata.items():
  for i in rs.sample(ids,snum[s]):counts[C[i]["repo"]]+=1
 hh.append(hhi(counts.values()));tops.append(sum(sorted(counts.values(),reverse=True)[:10])/192)
 nrepos.append(len(counts))
repo_result={"top":[{"repo":name,"workflows":n,"positive":rp[name]} for name,n in repo.most_common(45)],
 "positive_repos":len(rp),"gini":rd(gini([rp[k] for k in repo])),"hhi":rd(observed_hhi),
 "top10_share":rd(observed_top),"null_hhi_mean":rd(statistics.mean(hh)),
 "null_hhi_interval":[q(hh,.025),q(hh,.975)],"null_top_interval":[q(tops,.025),q(tops,.975)],
 "null_top_p":rd((1+sum(t>=observed_top for t in tops))/(len(tops)+1)),
 "null_hhi_p":rd((1+sum(t>=observed_hhi for t in hh))/(len(hh)+1)),
 "null_repos_mean":rd(statistics.mean(nrepos)),"null_repos_interval":[q(nrepos,.025),q(nrepos,.975)],
 "null_condition":"permute positive labels within scanner-opportunity signature","permutations":len(hh)}
pairs=[]
for r in rows("SELECT positive_case_id,control_case_id,match_tier,same_repository,positive_repository FROM arno_matched_control_pairs_C2"):
 i,j=int(r["positive_case_id"]),int(r["control_case_id"])
 if i in C and j in C:pairs.append((i,j,b(r["same_repository"]),r["positive_repository"],r["match_tier"]))
assert len(pairs)==190
def feat(c):
 return {"suggested_fix":b(c["suggestion"]),"codeblock":b(c["codeblock"]),"file_path":b(c["path"]),
  "function_name":b(c["func"]),"traceback":b(c["traceback"]),"dependency_version":b(c["dep"]),
  "words_ge_100":int(z(c["words"])>=100),"words_lt_30":int(z(c["words"])<30),
  "reviews_present":int(z(c["reviews"])>0),"reverse_chronology":c["chronology_bad"]}
ff=list(feat(C[pairs[0][0]]))
def clustered(pairs0,f):
 groups=collections.defaultdict(list)
 for i,j,s,r,t in pairs0:groups[r].append(feat(C[i])[f]-feat(C[j])[f])
 rr=random.Random(123321);names=list(groups);vals=[]
 for _ in range(600):
  ids=[rr.choice(names) for v in names]
  d=[x for repo in ids for x in groups[repo]]
  vals.append(sum(d)/len(d))
 return [q(vals,.025),q(vals,.975)]
E=[]
for f in ff:
 for sub,p0 in (("All matched",pairs),("Same repository",[a for a in pairs if a[2]])):
  bb=sum(feat(C[i])[f]==1 and feat(C[j])[f]==0 for i,j,_,_,_ in p0)
  cc=sum(feat(C[i])[f]==0 and feat(C[j])[f]==1 for i,j,_,_,_ in p0)
  E.append({"feature":f,"subset":sub,"pairs":len(p0),"p_yes":sum(feat(C[i])[f] for i,j,_,_,_ in p0),
   "n_yes":sum(feat(C[j])[f] for i,j,_,_,_ in p0),
   "delta":rd((bb-cc)/len(p0)),"discordant_pos":bb,"discordant_neg":cc,
   "paired_exact_p":exact(bb,cc),"cluster_ci":clustered(p0,f)})
cont=[]
for f in ("words","chars","lines","files"):
 for subset,subsetpair in [("All matched",pairs),("Same repository",[p for p in pairs if p[2]])]:
  d=[math.log1p(z(C[i][f]))-math.log1p(z(C[j][f])) for i,j,_,_,_ in subsetpair]
  cont.append({"variable":f,"subset":subset,"pairs":len(d),"median_ln_ratio":rd(statistics.median(d)),
   "mean_ln_ratio":rd(statistics.mean(d)),"positive_larger":sum(x>0 for x in d),
   "control_larger":sum(x<0 for x in d)})
def bins(key,bound):
 out=[]
 for k in range(len(bound)+1):
  a=[c for c in C.values() if sum(z(c[key])>b for b in bound)==k]
  n=len(a);p=sum(x["positive"] for x in a)
  out.append({"bin":k,"n":n,"positive":p,"rate":rd(p/n) if n else None,"ci95":wilson(p,n)})
 return out
B={"words":{"cuts":[20,50,100,200,500],"data":bins("words",[20,50,100,200,500])},
   "lines":{"cuts":[10,30,100,300,1000],"data":bins("lines",[10,30,100,300,1000])}}
FTR=[]
for f in ff:
 for v in [0,1]:
  allx=[c for c in C.values() if feat(c)[f]==v];p=sum(c["positive"] for c in allx)
  FTR.append({"feature":f,"value":v,"n":len(allx),"positive":p,"rate":rd(p/len(allx)) if allx else None})
# D7 and exact frozen producing-change attribution
D7=P/"mcp_uploads"/"arno_master_20261028"/"D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv"
with D7.open(encoding="utf-8-sig",newline="") as f:R=list(csv.DictReader(f))
assert len(R)==342
A=collections.defaultdict(list)
for v in rows("SELECT root_id,producing_change_id,attribution FROM arno_frozen_broad_attribution"):
 A[v["root_id"]].append(v["attribution"])
assert sum(len(a) for a in A.values())==455
ROOTM=collections.Counter();RT=collections.Counter();EX=[]
for x in R:
 route=x["final_route"];root=x["root_id"];atts=set(A[root])
 at="Direct" if atts=={"Direct"} else ("Side-effect" if atts=={"Side-effect"} else ("Mixed/unclear"))
 ROOTM[(route,at)]+=1;RT[(route,x["final_tier"])]+=1
 EX.append({"root":root,"case_id":int(x["case_id"]),"repo":x["repository"],
  "issue":x["issue_title"],"summary":x["root_summary"],"route":route,"tier":x["final_tier"],
  "attribution":at,"pc":int(x["pc_count"]),"chronology":x.get("final_chronology_ok"),
  "completeness":x.get("final_evidence_complete")})
# Full cohort and canonical-link QC
CO=collections.Counter()
for x in rows("SELECT cohort_key,case_id FROM arno_cohort_membership"):CO[x["cohort_key"]]+=1
LINKS=collections.Counter(x["cohort"] for x in rows("SELECT cohort FROM arno_canonical_id_pc_links"))
CS=rows("SELECT count(*) n FROM arno_original_step1_detail")[0]["n"]
# original O/W/P repl, exact scans, no task success claim
RW=rows("SELECT case_id,arm,target_new_strong,historical_target_rule,functional_status,patch_bytes_match_status FROM arno_rq3_owp14_run_scans")
REPLAY=collections.defaultdict(dict)
for x in RW:REPLAY[x["case_id"]][x["arm"]]=int(x["target_new_strong"] or 0)
TR=[{"case_id":i,"repo":C[i]["repo"] if i in C else "",
 "issue":C[i]["issue"] if i in C else "","O":v.get("O"),"W":v.get("W"),"P":v.get("P")}
 for i,v in sorted(REPLAY.items())]
COMP=[t for t in TR if None not in (t["O"],t["W"],t["P"])]
months=collections.defaultdict(lambda:[0,0])
for c in C.values():
 if len(c["month"])==7:months[c["month"]][0]+=1;months[c["month"]][1]+=c["positive"]
rawcase=collections.Counter({i:sum(r["introduced"]==1 for r in row) for i,row in F.items()})
OUT={"qc":{"cases":len(C),"repositories":len(repo),"positive_c1":len(positive_c1),
 "raw_positive_cases":len(positive_raw),"c1_positive_without_raw":sorted(positive_c1-positive_raw),
 "raw_positive_not_c1":sorted(positive_raw-positive_c1),"scanner_finding_rows":len(scanrows),
 "introduced_raw_rows":sum(x["introduced"]==1 for x in scanrows),
 "root_count":len(R),"pc_count":sum(len(v) for v in A.values()),
 "c1_positives":len(positive_c1),"orig122_canonical":CS,"linked_canonical":dict(LINKS),
 "cohort_sizes":dict(CO)},
 "scanner":S,"scanner_overlap":OV,"repo":repo_result,"matched":E,
 "matched_n":len(pairs),"matched_same_repo":sum(p[2] for p in pairs),
 "matched_size":cont,"full_features":FTR,"full_bins":B,
 "roots":[{"route":a,"attribution":b,"count":n} for (a,b),n in sorted(ROOTM.items())],
 "root_tiers":[{"route":a,"tier":b,"count":n} for (a,b),n in sorted(RT.items())],
 "root_examples":[x for x in EX if x["route"] in ("H","M") and x["tier"] in ("T1","T2","T3")][:55],
 "root_counterexamples":[x for x in EX if x["route"]=="M" and x["tier"]=="T4"][:15],
 "replay":TR,"replay_patterns":dict(collections.Counter(str(x["O"])+str(x["W"])+str(x["P"]) for x in COMP)),
 "replay_n_complete":len(COMP),"replay_functional_status":dict(collections.Counter(x["functional_status"] for x in RW)),
 "chronology":{"reverse_positive":sum(c["positive"]*c["chronology_bad"] for c in C.values()),
  "reverse_controls":sum((1-c["positive"])*c["chronology_bad"] for c in C.values()),
  "examples":[{"case_id":c["case_id"],"repo":c["repo"],"issue":c["issue"],"positive":c["positive"]} for c in C.values() if c["chronology_bad"]][:24]},
 "months":[{"month":m,"workflows":v[0],"positive":v[1]} for m,v in sorted(months.items())],
 "raw_scanner_counts":dict(collections.Counter(v["scanner"] for v in scanrows if v["introduced"]==1)),
 "outlier_raw_cases":[{"case_id":i,"count":v,"repo":C[i]["repo"],"issue":C[i]["issue"],"c1_positive":C[i]["positive"]} for i,v in rawcase.most_common(15)]}
(T/"metrics.json").write_text(json.dumps(OUT,ensure_ascii=False,indent=2))
print("DONE",T/"metrics.json","3809",len(C),"pairs",len(pairs),"roots",len(R),flush=True)
