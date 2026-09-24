#!/usr/bin/env python3
"""抽寶箱 AFFiNE「第 26 章｜S24 投注資料查詢」逐塊更新到 DEV V1.37（不整頁覆蓋）。"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from affine_cli import MCP, workspace_id

DOC = "Ieafa0Hl10"
live = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tb_s24.json")))
B = live["blocks"]
TAG = "〔DEV V1.37〕"


def deltas(md):
    """**粗體** → delta；其餘原樣。"""
    out = []
    for i, part in enumerate(re.split(r'\*\*', md)):
        if part:
            out.append({"insert": part, "attributes": {"bold": True}} if i % 2 else {"insert": part})
    return out


def find(pred, label):
    hit = [b for b in B if pred(b)]
    assert len(hit) == 1, f"[{label}] 找到 {len(hit)} 個"
    return hit[0]


def text_block(startswith, label):
    return find(lambda b: (b.get("text") or "").startswith(startswith), label)


def table_block(bid):
    return find(lambda b: b["id"] == bid, bid)


m = MCP(); m.start(); ws = workspace_id()
log = []


def call(tool, args, label):
    args = dict(args, docId=DOC, workspaceId=ws)
    out = m.call(tool, args)
    ok = out.lstrip().startswith("{") and '"error"' not in out[:200]
    log.append(f"  {'✓' if ok else '✗'} {label}" + ("" if ok else f"  → {out[:160]}"))
    return json.loads(out) if ok else None


try:
    # ① 頁首標註本頁已含 DEV V1.37 變更
    q = text_block("負責端：遊戲後台", "頁首引用")
    call("append_block", {"type": "callout", "placement": {"afterBlockId": q["id"]},
         "text": deltas("**DEV V1.37（2026-09-23）更新本頁**：篩「活動獎勵」時新增 **ref_free_voucher_id** 欄；"
                        "獎勵類型值域加入 **FREE SPIN 卡**。")}, "頁首加 V1.37 更新說明")

    # ② 元件表：⑦ 值域更新、新增 ⑨（表格加列需重建）
    t = table_block("kM1KusXV8K")
    rows = [list(r) for r in t["tableData"]]
    assert rows[7][0] == "⑦"
    rows[7][2] = "僅在注單類型＝活動獎勵時出現；值＝現金獎／FREE SPIN 卡（DEV V1.37 起）"
    rows.append(["⑨", "ref_free_voucher_id 欄（DEV V1.37 新增）",
                 "僅在注單類型＝活動獎勵時出現；FREE SPIN 卡相關的獎勵才有值，現金獎為空（原型截圖尚未含此欄）",
                 "沿用列表既有行為"])
    r = call("append_block", {"type": "table", "rows": len(rows), "columns": 4, "tableData": rows,
             "placement": {"afterBlockId": t["id"]}}, "元件表重建（⑦ 更新＋新增 ⑨）")
    if r:
        call("delete_block", {"blockId": t["id"]}, "刪除舊元件表")

    # ③ 3.3 標題與內文
    h = text_block("3.3 篩「活動獎勵」時的額外欄位", "3.3 標題")
    call("update_block", {"blockId": h["id"], "text": "3.3 篩「活動獎勵」時的額外欄位（元件 ⑥⑦⑨）"}, "3.3 標題加 ⑨")
    li = text_block("注單類型＝活動獎勵時，列表額外呈現", "3.3 欄位句")
    call("update_block", {"blockId": li["id"], "text": deltas(
        "注單類型＝活動獎勵時，列表額外呈現「CAMPAIGN ID」「獎勵類型」「**ref_free_voucher_id**」**三欄**。" + TAG)},
        "3.3 兩欄改三欄")
    call("append_block", {"type": "list", "style": "bulleted", "placement": {"afterBlockId": li["id"]},
         "text": deltas("**ref_free_voucher_id**＝該筆獎勵對應的 **FREE SPIN 卡卡序號**（即 FREE SPIN 規格書的 reference_id），"
                        "營運用它回查「這筆錢是哪一張卡給的」；**現金獎沒有對應的卡，此欄為空**。" + TAG)},
         "3.3 新增 ref_free_voucher_id 說明")

    # ④ 3.4 值域表
    call("update_table_cell", {"blockId": "QU4JrAW6Mp", "row": 1, "column": 0, "text": "DEV V1.36 以前"}, "值域表 r1 版本")
    call("update_table_cell", {"blockId": "QU4JrAW6Mp", "row": 2, "column": 0, "text": "DEV V1.37 起"}, "值域表 r2 版本")
    call("update_table_cell", {"blockId": "QU4JrAW6Mp", "row": 2, "column": 1,
         "text": "現金獎、FREE SPIN 卡（玩家在抽寶箱抽中 FREE SPIN 卡時標示為「FREE SPIN 卡」；併入同一欄位，不另開欄位）"},
         "值域表 r2 值域")

    # ⑤ 4. 條件限制
    for start, new, lab in [
        ("額外欄位只有 CAMPAIGN ID 與獎勵類型兩欄",
         "額外欄位為 CAMPAIGN ID、獎勵類型、ref_free_voucher_id 三欄，且只在篩活動獎勵時出現；其餘欄位沿用既有。" + TAG, "條件限制·三欄"),
        ("v1 獎勵類型只有現金獎",
         "獎勵類型值域＝現金獎／FREE SPIN 卡（DEV V1.37 起；原為 v1 只有現金獎）。", "條件限制·值域"),
        ("v2 不做：FREE SPIN 卡併入獎勵類型值域",
         "v2 不做：後台打開已刪模板檢視設定（見附錄 A1）。（原列的「FREE SPIN 卡併入獎勵類型值域」已於 DEV V1.37 納入）", "條件限制·v2 項"),
    ]:
        b = text_block(start, lab)
        call("update_block", {"blockId": b["id"], "text": new}, lab)

    # ⑥ i18n 表：加兩列（重建）
    t = table_block("dXrLRqf7ia")
    rows = [list(r) for r in t["tableData"]]
    rows.insert(7, ["未定義", "元件 ⑦ 值（DEV V1.37 起）", "FREE SPIN 卡", "未定義"])
    rows.append(["未定義", "元件 ⑨ 欄位標題", "ref_free_voucher_id", "ref_free_voucher_id"])
    r = call("append_block", {"type": "table", "rows": len(rows), "columns": 4, "tableData": rows,
             "placement": {"afterBlockId": t["id"]}}, "i18n 表重建（加 2 列）")
    if r:
        call("delete_block", {"blockId": t["id"]}, "刪除舊 i18n 表")
    b = text_block("後台術語規則：CAMPAIGN ID", "術語規則")
    call("update_block", {"blockId": b["id"], "text":
         "後台術語規則：CAMPAIGN ID 與 ref_free_voucher_id 屬代碼與識別碼，不翻譯、維持原內容（DEV §06 後台 i18n）。"},
         "術語規則加 ref_free_voucher_id")

    # ⑦ BDD「預設維持既有行為」
    b = text_block("預設維持既有行為", "BDD 預設行為")
    t2 = b["text"].replace("不出現 CAMPAIGN ID 與獎勵類型欄。", "不出現 CAMPAIGN ID、獎勵類型與 ref_free_voucher_id 欄。")
    assert t2 != b["text"]
    call("update_block", {"blockId": b["id"], "text": t2}, "BDD 預設行為加第三欄")
finally:
    m.close()
print("\n".join(log))
print("\n失敗：", sum(1 for x in log if x.lstrip().startswith("✗")))
