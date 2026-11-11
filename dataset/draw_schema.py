"""Draw connected physical ERDs from the distributed schema."""
import html,json,sqlite3,subprocess,math,xml.etree.ElementTree as E
from pathlib import Path
R=Path(__file__).resolve().parent;O=R/'erd';O.mkdir(exist_ok=True)
c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.executescript((R/'SCHEMA.sql').read_text());groups=json.loads((R/'domains.json').read_text());T={}
for n,sql in c.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
 T[n]={'columns':[dict(r) for r in c.execute('PRAGMA table_info("'+n+'")')],'foreign_keys':[dict(r) for r in c.execute('PRAGMA foreign_key_list("'+n+'")')],'domain':groups[n]}
F=[]
from collections import defaultdict
for n,t in T.items():
 fs=defaultdict(list)
 for f in t['foreign_keys']:fs[f['id']].append(f)
 for _,v in fs.items():F.append((n,v[0]['table']))
def wrapped(n):
 lines=[];line=''
 for part in n.split('_'):
  if len(line)+len(part)>34:lines.append(line.rstrip('_'));line=''
  line+=part+'_'
 if line:lines.append(line.rstrip('_'))
 return '<BR/>'.join(html.escape(l) for l in lines)
def draw(name,primary,parents=True):
 edges=[(a,b) for a,b in F if a in primary and (parents or b in primary)];names=primary|{b for a,b in edges};q=json.dumps
 lines=['digraph schema {graph [rankdir=TB,splines=ortho,concentrate=false,pack=true,packmode="array_u3",nodesep=0.8,ranksep=1.2,pad=0.3,bgcolor="white",outputorder=edgesfirst];node [shape=plain,fontname="DejaVu Sans",fontsize=12];edge [color="#4d6789",penwidth=1.4,arrowsize=0.75];']
 for n in sorted(names):
  t=T[n];fk={f['from'] for f in t['foreign_keys']};rows=[]
  for col in t['columns']:
   if col['pk'] or col['name'] in fk:
    flags='/'.join((['PK'] if col['pk'] else [])+(['FK'] if col['name'] in fk else []))
    rows.append('<TR><TD ALIGN="LEFT">'+flags+'</TD><TD ALIGN="LEFT">'+html.escape(col['name'])+'</TD><TD>'+html.escape(col['type'])+'</TD></TR>')
  color='#d7e9ff' if n in primary else '#e8eef6'
  lines.append(q(n)+' [label=<<TABLE BORDER="1" COLOR="#70849d" CELLBORDER="0" CELLSPACING="0" CELLPADDING="7"><TR><TD COLSPAN="3" BGCOLOR="'+color+'"><B>'+wrapped(n)+'</B></TD></TR>'+''.join(rows)+'</TABLE>>];')
 for a,b in edges:lines.append(q(a)+' -> '+q(b)+';')
 lines.append('}');dot='\n'.join(lines);p=O/(name+'.dot');p.write_text(dot)
 subprocess.run(['dot','-Tsvg',str(p),'-o',str(O/(name+'.svg'))],check=True)
 r=E.parse(O/(name+'.svg')).getroot();w,h=map(float,r.get('viewBox').split()[2:])
 if w/h>1.8:
  p.write_text(dot.replace('rankdir=TB','rankdir=LR'));alt=O/(name+'_alt.svg');subprocess.run(['dot','-Tsvg',str(p),'-o',str(alt)],check=True);ar=E.parse(alt).getroot();aw,ah=map(float,ar.get('viewBox').split()[2:])
  if abs(math.log(aw/ah/1.2))<abs(math.log(w/h/1.2)):(O/(name+'.svg')).write_bytes(alt.read_bytes())
  else:p.write_text(dot)
  alt.unlink()
 return len(edges)
count=0;D=sorted(set(groups.values()))
for d in D:count+=draw(d,{n for n in T if groups[n]==d})
assert count==len(F)
core={'cases','repos','issues','pull_requests','study_classifications','study_experiment_runs','study_generated_patches','study_experiment_scans'};draw('OVERVIEW',core,False)
NS='http://www.w3.org/2000/svg';E.register_namespace('',NS);parts=[]
for d in D:
 r=E.parse(O/(d+'.svg')).getroot();w,h=map(float,r.get('viewBox').split()[2:]);parts.append((d,r,w,h))
W=max(w for d,r,w,h in parts)+80;root=E.Element('{'+NS+'}svg',{'width':str(W)});y=20
for d,r,w,h in parts:
 t=E.SubElement(root,'{'+NS+'}text',{'x':'40','y':str(y+35),'font-family':'DejaVu Sans','font-size':'28','font-weight':'bold'});t.text=d.replace('_',' ').title();y+=65
 for e in r.iter():
  if 'id' in e.attrib:e.set('id',d+'_'+e.get('id'))
 r.set('x',str((W-w)/2));r.set('y',str(y));r.set('width',str(w));r.set('height',str(h));root.append(r);y+=h+55
root.set('height',str(y));root.set('viewBox',f'0 0 {W} {y}');E.ElementTree(root).write(O/'FULL_DATABASE_ERD.svg',encoding='utf-8',xml_declaration=True)
print(json.dumps({'tables':len(T),'declared_foreign_keys':len(F),'views':c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]}))
