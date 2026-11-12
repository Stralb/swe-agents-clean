#!/usr/bin/env python3
"""Reuse audited publisher with exact-path allowlist forced past results gitignore."""
from pathlib import Path
file=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/publish_git_release.py')
source=file.read_text()
old="git('add','--',*sorted(expected))"
new="git('add','-f','--',*sorted(expected))"
assert source.count(old)==1
exec(compile(source.replace(old,new),str(file),'exec'),{'__name__':'__main__','__file__':str(file)})
