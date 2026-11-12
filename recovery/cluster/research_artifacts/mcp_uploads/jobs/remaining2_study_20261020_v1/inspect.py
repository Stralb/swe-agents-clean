from pathlib import Path
root=Path.home()/"research_artifacts/prevention_pilot_phase2/seven_case_scans_20261020"
targets={
"08152":["src/ui/app.tsx","src/telegram/bridge.ts","src/utils/settings.ts"],
"31207":["ai/deploy/docker-compose.yml","ai/deploy/docker-compose.local-agent-os.yml","ai/scripts/diagnostics/fleetHealthcheck.mjs"]}
terms={"08152":["startTelegramBridge","getTelegramBotToken","saveUserSettings({ telegram","transcribeTelegramVoice","botToken"],"31207":["fleetHealthcheck","NEO_MCP_HEALTHCHECK_TOKEN","mcp-auth-token","fleet-server:"]}
for case,files in targets.items():
 r=root/case/"scratch"/("seven_"+case+("_10338" if case=="08152" else "_1594332"))/"after"/"REPO"
 for f in files:
  p=r/f
  lines=p.read_text().splitlines()
  print("\n===",case,f,len(lines),"===")
  positions=[]
  for i,line in enumerate(lines):
   if any(term in line for term in terms[case]):positions.append(i)
  covered=set()
  for i in positions:
   for j in range(max(0,i-5),min(len(lines),i+9)):
    if j not in covered:print(str(j+1)+": "+lines[j]);covered.add(j)
   print("--")
