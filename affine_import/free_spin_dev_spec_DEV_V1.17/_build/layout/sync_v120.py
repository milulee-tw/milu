#!/usr/bin/env python3
"""DEV V1.20 → AFFiNE 一鍵同步（依文件矛盾審查報告修正）（內網通了之後直接跑這支）。

做四件事：
1. 上傳兩張新截圖（fs_hist_01／fs_hist_02）
2. 把 40 個規格頁套上新版內容＋A／B／C 版面
3. 只改 7 個 Hub 的「依據」那一行（不整頁覆蓋，避免清掉子頁連結）
4. 收尾驗證

可以重複執行；已經是最新的頁面再跑一次結果相同。
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from affine_cli import MCP, workspace_id          # noqa: E402
from apply_layout import apply_page, doc_ids      # noqa: E402

PKG = ("/Users/milulee/Library/CloudStorage/GoogleDrive-milulee.tw@gmail.com/"
       "共用雲端硬碟/Force相關(藍玥)/github.milu/affine_import/free_spin_dev_spec_DEV_V1.17")
ASSETS = os.path.join(PKG, "design_assets")
NEW_IMAGES = []
HUBS = ["00", "01", "02", "03", "04", "05", "09"]
OLD_BASIS = ("依據：規格 DEV V1.19（上限欄位統一為 max_bonus；新增結算狀態機、注單機制與玩家端錯誤文案；"
             "其餘產品規則沿用 DEV V1.15）")
NEW_BASIS = ("依據：規格 DEV V1.20（依文件矛盾審查報告修正結算觸發、逐局注單、到期結算時點與歷程顯示；"
             "上限欄位統一為 max_bonus；其餘產品規則沿用 DEV V1.15）")
OLD_CELL = "每個幣值一組 1★–5★，營運只填「每轉押注」一個數字，其餘全部自動算。"
NEW_CELL = "每個幣值一組 1★–5★，營運填「每轉押注」，次數與封頂倍數也可逐段調整（預設 10 次、×10）；face_value 與 max_bonus 自動算。"


def reachable():
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "10", "http://10.10.66.10:3010/"],
                       capture_output=True, text=True)
    return r.stdout.strip() not in ("", "000")


def signed_in():
    """用一個讀取呼叫確認帳號真的登入了（網路通 ≠ 認證通）。"""
    m = MCP(); m.start()
    try:
        out = m.call("get_doc", {"docId": doc_ids()["00"], "workspaceId": workspace_id()})
    finally:
        m.close()
    return out.lstrip().startswith("{"), out[:160]


def step_images():
    print("\n【1／4】上傳新截圖（本版無）")
    for name in NEW_IMAGES:
        out = subprocess.run([sys.executable, os.path.join(HERE, "affine_cli.py"),
                              "upload", os.path.join(ASSETS, name)],
                             capture_output=True, text=True).stdout.strip()
        print("  ", "OK " if '"key"' in out else "失敗 ", name, out[-110:])


def step_pages(ids):
    print("\n【2／4】套用 40 個規格頁")
    codes = sorted(c for c in ids
                   if c not in HUBS and os.path.exists(os.path.join(HERE, "built", c + ".md")))
    m = MCP(); m.start(); ws = workspace_id()
    try:
        for code in codes:
            try:
                print(f"   {code:<6} {apply_page(m, ws, code, ids[code])}", flush=True)
            except Exception as e:
                print(f"   {code:<6} 失敗：{e}", flush=True)
    finally:
        m.close()


def step_hubs(ids):
    print("\n【3／4】只改 7 個 Hub 的依據行（不整頁覆蓋）")
    m = MCP(); m.start(); ws = workspace_id()
    try:
        for code in HUBS:
            doc = ids[code]
            live = json.loads(m.call("read_doc", {"docId": doc, "workspaceId": ws}))
            for b in live["blocks"]:
                for r, row in enumerate(b.get("tableData") or []):
                    for c, cell in enumerate(row):
                        if cell == OLD_CELL:
                            m.call("update_table_cell", {"docId": doc, "blockId": b["id"], "row": r,
                                                         "column": c, "text": NEW_CELL, "workspaceId": ws})
                            print(f"   Hub {code}  01-C 一句話已更新")
            hit = [b for b in live["blocks"] if OLD_BASIS in (b.get("text") or "")]
            if not hit:
                print(f"   Hub {code}  已是新版或找不到依據行，略過")
                continue
            b = hit[0]
            m.call("update_block", {"docId": doc, "blockId": b["id"],
                                    "text": b["text"].replace(OLD_BASIS, NEW_BASIS),
                                    "workspaceId": ws})
            print(f"   Hub {code}  依據行已更新")
    finally:
        m.close()


def step_verify(ids):
    print("\n【4／4】驗證")
    m = MCP(); m.start(); ws = workspace_id()
    tot = {"callout": 0, "divider": 0, "image": 0, "table": 0, "bookmark": 0}
    old_ver = leftover = 0
    try:
        for code, doc in ids.items():
            live = json.loads(m.call("read_doc", {"docId": doc, "workspaceId": ws}))
            for b in live["blocks"]:
                f = b["flavour"].replace("affine:", "")
                if f in tot:
                    tot[f] += 1
                t = b.get("text") or ""
                if "規格 DEV V1.17" in t or "規格 DEV V1.18" in t or "規格 DEV V1.19" in t or "max_conversion" in t and "原稱" not in t and "原本使用" not in t:
                    old_ver += 1
                if "⟦IMG:" in t or "affine://" in t:
                    leftover += 1
        # 子頁連結
        broken = []
        for code in HUBS:
            r = json.loads(m.call("list_children", {"docId": ids[code], "workspaceId": ws}))
            broken.append((code, r["count"]))
    finally:
        m.close()
    print("   區塊統計：", tot)
    print("   殘留舊版號或舊欄位名的區塊：", old_ver, "（應為 0；修改紀錄頁的歷史列除外）")
    print("   殘留佔位符／affine:// ：", leftover, "（應為 0）")
    print("   各 Hub 子頁數：", broken, "（應為 00=9 01=5 02=6 03=6 04=6 05=4 09=10）")


if __name__ == "__main__":
    if not reachable():
        sys.exit("❌ 連不到 http://10.10.66.10:3010 —— 先確認內網／VPN 通了再跑這支。")
    ok, msg = signed_in()
    if not ok:
        sys.exit("❌ 網路通了但 AFFiNE 登入失敗：" + msg +
                 "\n   先檢查 ~/.config/affine-mcp/config——這台要走帳密，"
                 "若有 AFFINE_COOKIE 那一行請刪掉再跑。")
    ids = doc_ids()
    step_images()
    step_pages(ids)
    step_hubs(ids)
    step_verify(ids)
    print("\n完成。")
