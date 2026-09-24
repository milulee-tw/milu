#!/usr/bin/env python3
"""把 built/<代碼>.md 套到 AFFiNE，並把圖片語法換成真正的 image 區塊。

markdown 匯入不會接上 blob（相對路徑變純文字、網址變書籤卡），
所以流程是：整頁覆蓋 → 找出那些「只有圖片語法」的區塊 → 在原位插 image 再刪掉它。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from affine_cli import MCP, workspace_id

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = ("/Users/milulee/Library/CloudStorage/GoogleDrive-milulee.tw@gmail.com/"
       "共用雲端硬碟/Force相關(藍玥)/github.milu/affine_import/free_spin_dev_spec_DEV_V1.17")
ASSETS = os.path.join(PKG, "design_assets")
CROPS = os.path.join(HERE, "crops")

IMG_RE = re.compile(r'^\u27e6IMG:([^\u27e7]+)\u27e7$')


def blob_size(name):
    for d in (CROPS, os.path.join(ASSETS, "regions"), ASSETS):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return os.path.getsize(p)
    raise SystemExit(f"找不到圖檔 {name}")


def doc_ids():
    out, seen = {}, set()
    for line in open(os.path.join(PKG, "affine-map.md"), encoding="utf-8"):
        m = re.match(r'\|\s*([0-9]{2}(?:-[A-Z])?)\s*\|\s*[^|]+?\s*\|\s*([A-Za-z0-9_-]{8,})\s*\|', line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out[m.group(1)] = m.group(2)
    return out


def apply_page(m, ws, code, doc):
    md = open(os.path.join(HERE, "built", code + ".md"), encoding="utf-8").read()
    res = json.loads(m.call("replace_doc_with_markdown",
                            {"docId": doc, "markdown": md, "workspaceId": ws}))
    if not res.get("ok"):
        return f"覆蓋失敗：{res}"

    live = json.loads(m.call("read_doc", {"docId": doc, "workspaceId": ws}))
    todo = []
    for b in live["blocks"]:
        t = (b.get("text") or "").strip()
        mm = IMG_RE.match(t)
        if mm:
            todo.append((b["id"], os.path.basename(mm.group(1))))

    fixed = 0
    for bid, name in todo:
        m.call("append_block", {
            "docId": doc, "type": "image", "sourceId": name,
            "size": blob_size(name), "placement": {"afterBlockId": bid},
            "workspaceId": ws})
        m.call("delete_block", {"docId": doc, "blockId": bid, "workspaceId": ws})
        fixed += 1

    after = json.loads(m.call("read_doc", {"docId": doc, "workspaceId": ws}))
    kinds = {}
    leftover = 0
    for b in after["blocks"]:
        f = b["flavour"].replace("affine:", "")
        kinds[f] = kinds.get(f, 0) + 1
        if IMG_RE.match((b.get("text") or "").strip()):
            leftover += 1
    return (f"callout{kinds.get('callout', 0):>3} divider{kinds.get('divider', 0):>3} "
            f"image{kinds.get('image', 0):>3} table{kinds.get('table', 0):>3} "
            f"bookmark{kinds.get('bookmark', 0):>2} 圖片修復{fixed:>2} 殘留{leftover}")


if __name__ == "__main__":
    ids = doc_ids()
    codes = sys.argv[1:]
    m = MCP(); m.start(); ws = workspace_id()
    try:
        for code in codes:
            print(f"  {code:<6} {apply_page(m, ws, code, ids[code])}", flush=True)
    finally:
        m.close()
