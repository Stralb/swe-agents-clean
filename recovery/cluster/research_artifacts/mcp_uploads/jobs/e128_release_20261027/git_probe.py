#!/usr/bin/env python3
"""Noninteractive network/auth diagnostic. Never displays tokens, keys or env."""
import subprocess
urls=[
 'git@github.com:Stralb/arc-agi-3-rl-research.git',
 'https://github.com/Stralb/arc-agi-3-rl-research.git',
]
for kind,url in enumerate(urls):
    try:
        cmd=['git','-c','credential.interactive=never','-c','core.askPass=','ls-remote',url,'refs/heads/main']
        if kind==0:cmd=['git','-c','core.sshCommand=ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8', 'ls-remote',url,'refs/heads/main']
        r=subprocess.run(cmd,text=True,capture_output=True,timeout=24)
        print('GIT_REMOTE',kind,'EXIT',r.returncode,'HAS_MAIN',r.stdout.startswith('31d5b3ad6d52f61f1e02ff1b2eddfcfd59d2c2c3'),'STDERR_SUMMARY',r.stderr[-270:].replace('\n',' '),flush=True)
    except Exception as e:print('GIT_REMOTE',kind,'EXCEPTION',type(e).__name__,str(e)[:150],flush=True)
