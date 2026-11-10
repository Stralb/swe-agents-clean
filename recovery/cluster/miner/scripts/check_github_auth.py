from __future__ import annotations

import os
import re
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

raw = os.getenv("GITHUB_TOKENS") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
tokens = [t.strip() for t in re.split(r"[,;\s]+", raw or "") if t.strip()]
if not tokens:
    print("ERROR: No GitHub token detected. Put GITHUB_TOKENS=token1,token2 in .env.cluster or pass GH_TOKEN=... to make.", file=sys.stderr)
    sys.exit(2)

ok = 0
for i, token in enumerate(tokens, start=1):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    resp = requests.get("https://api.github.com/rate_limit", headers=headers, timeout=20)
    if resp.status_code in {401, 403}:
        print(f"ERROR: GitHub token #{i} was rejected or exhausted: HTTP {resp.status_code} {resp.text[:160]}", file=sys.stderr)
        continue
    if resp.status_code >= 400:
        print(f"ERROR: GitHub auth check failed for token #{i}: HTTP {resp.status_code} {resp.text[:160]}", file=sys.stderr)
        continue
    data = resp.json()
    core = data.get("resources", {}).get("core", {})
    search = data.get("resources", {}).get("search", {})
    core_remaining = int(core.get("remaining", 0) or 0)
    search_remaining = int(search.get("remaining", 0) or 0)
    print(f"GitHub token #{i} OK | core_remaining={core_remaining} | search_remaining={search_remaining} | token hidden")
    if core_remaining >= 25:
        ok += 1

if ok <= 0:
    print("ERROR: No usable GitHub token has enough core rate limit for collection.", file=sys.stderr)
    sys.exit(5)
print(f"Usable GitHub tokens: {ok}/{len(tokens)}")
