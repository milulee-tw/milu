#!/usr/bin/env python3
"""依序呼叫多個 MCP 工具；每步印出結果。"""
import json, sys
sys.path.insert(0, "/private/tmp/claude-501/-Users-milulee-Library-CloudStorage-GoogleDrive-milulee-tw-gmail-com--------Force-------github-milu/2477f17b-c6cd-47ac-8194-bd34ae972ce4/scratchpad")
from affine_cli import MCP, workspace_id

steps = json.load(open(sys.argv[1]))
m = MCP(); m.start()
ws = workspace_id()
try:
    for i, s in enumerate(steps, 1):
        a = dict(s["args"]); a.setdefault("workspaceId", ws)
        try:
            out = m.call(s["tool"], a)
            ok = '"ok":true' in out or '"deleted":true' in out or 'error' not in out.lower()
            print(f"{i:>2} {s['tool']:<26} {'OK ' if ok else 'ERR'} {out[:150]}")
        except Exception as e:
            print(f"{i:>2} {s['tool']:<26} FAIL {e}")
finally:
    m.close()
