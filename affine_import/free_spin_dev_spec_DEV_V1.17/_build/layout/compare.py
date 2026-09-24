#!/usr/bin/env python3
"""比對 AFFiNE 現況與來源 .md：回報 .md 裡有、但頁面上找不到的行。"""
import re, json, sys, os, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from affine_cli import MCP, workspace_id

PKG = "/Users/milulee/Library/CloudStorage/GoogleDrive-milulee.tw@gmail.com/共用雲端硬碟/Force相關(藍玥)/github.milu/affine_import/free_spin_dev_spec_DEV_V1.17"


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r'<br\s*/?>', '', s, flags=re.I)      # 表格內換行：.md 用 <br>、AFFiNE 是真換行
    s = re.sub(r'\]\([^)]*\)', ']', s)               # 連結網址：affine:// 佔位已換成真實網址
    s = re.sub(r'https?://\S+', '', s)
    return re.sub(r'[*`>|#\[\]\-\s]', '', s)


def md_lines(path):
    for raw in open(path, encoding="utf-8"):
        t = raw.strip()
        if not t or t.startswith("#") or t.startswith("!["):
            continue
        if set(t) <= set("|-: "):
            continue
        n = norm(t)
        if len(n) < 4:
            continue
        yield t, n


def live_text(m, ws, doc):
    live = json.loads(m.call("read_doc", {"docId": doc, "workspaceId": ws}))
    parts = [live["plainText"]]
    for b in live["blocks"]:
        if b.get("tableData"):
            for r in b["tableData"]:
                parts.append(" ".join(r))
    return norm("\n".join(parts)), live


def load_map():
    rows, seen = [], set()
    for line in open(os.path.join(PKG, "affine-map.md"), encoding="utf-8"):
        m = re.match(r'\|\s*([0-9]{2}(?:-[A-Z])?)\s*\|\s*([^|]+?)\s*\|\s*([A-Za-z0-9_-]{8,})\s*\|', line)
        if m and m.group(1) not in seen and 'W' not in m.group(1):
            seen.add(m.group(1))
            if os.path.exists(os.path.join(PKG, m.group(1) + ".md")):
                rows.append((m.group(1), m.group(3)))
    return rows


if __name__ == "__main__":
    only = set(sys.argv[1:])
    rows = [r for r in load_map() if not only or r[0] in only]
    m = MCP(); m.start(); ws = workspace_id()
    bad = []
    try:
        for code, doc in rows:
            page, _ = live_text(m, ws, doc)
            miss = [t for t, n in md_lines(os.path.join(PKG, code + ".md")) if n not in page]
            print(f"  {code:<5} {'OK' if not miss else '缺 %d' % len(miss)}")
            if miss:
                bad.append((code, miss))
    finally:
        m.close()
    print()
    for c, ms in bad:
        print(f"{c}:")
        for x in ms[:8]:
            print("   ✗", x[:110])
    print(f"\n對不上的頁：{len(bad)} / {len(rows)}")
