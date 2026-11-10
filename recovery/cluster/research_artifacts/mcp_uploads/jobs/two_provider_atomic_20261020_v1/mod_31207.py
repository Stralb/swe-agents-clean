def modify(repo):
 def swap(name,old,new):
  p=repo/name
  t=p.read_text()
  assert t.count(old)==1,(name,t.count(old))
  p.write_text(t.replace(old,new,1))
 swap('ai/services/fleet/composedFleetServer.mjs',"app.use(cors({origin: '*'}));","app.use(cors({origin: false}));")
 swap('ai/scripts/diagnostics/fleetHealthcheck.mjs',"import {readFile} from 'node:fs/promises';\n","")
 swap('ai/scripts/diagnostics/fleetHealthcheck.mjs',"""    const file = process.env.NEO_MCP_HEALTHCHECK_TOKEN_FILE;
    const token = file ? (await readFile(file, 'utf8')).trim() : process.env.NEO_MCP_HEALTHCHECK_TOKEN;""",
   """    const token = process.env.NEO_MCP_HEALTHCHECK_TOKEN;""")
 p=repo/'ai/deploy/docker-compose.local-agent-os.yml'
 t=p.read_text()
 anchor="""    secrets:
      - mcp-auth-token

  chroma:"""
 extra="""    secrets:
      - mcp-auth-token
    # Keep the Docker secret file; inject it only into the short-lived probe.
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          token=$$(cat /run/secrets/mcp-auth-token) &&
          test -n "$$token" &&
          NEO_MCP_HEALTHCHECK_TOKEN="$$token"
          node ./ai/scripts/diagnostics/fleetHealthcheck.mjs
          --url http://127.0.0.1:3103/fleet/probe
          --expected-fleet-data-root /app/.neo-ai-data/fleet

  chroma:"""
 assert t.count(anchor)==1
 p.write_text(t.replace(anchor,extra,1))
