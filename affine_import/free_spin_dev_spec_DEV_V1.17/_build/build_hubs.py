#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 V1.16 的 7 份 Hub 產出 V1.17 版：只動依據行、索引表（移除 0N-W 列）與結構描述句。
不新增規則、不改子頁一句話。"""
import os, re

SRC = "affine_import/free_spin_dev_spec_DEV_V1.16"
DST = "affine_import/free_spin_dev_spec_DEV_V1.17"

BASIS = ("> 依據：規格 DEV V1.17（產品規則沿用 DEV V1.15）"
         "／ 後台原型 2026-08-25 實拍 ／ 背包原型 2026-09-14 新版線框")

# V1.17 把操作流程內嵌回功能頁，對照表（來自 HTML 的 inline-walkthrough 區塊）
FLOW = {
    "01": ["- DEV V1.17 未內嵌本模組的操作流程；原 01-W 的兩條流程"
           "（型錄複用、建卡到啟用）隨 01-W 一併移除，尚未有替代頁面。"],
    "02": ["- 背包選卡與進場 → 見 02-C 選卡與進入遊戲（橫式版面）",
           "- 封頂後提前結算 → 見 02-D 提前結算與獎金上限（MAX / SETTLE NOW）"],
    "03": ["- 進場到整卡結算 → 見 03-A 進場提示彈窗"],
    "04": ["- History 五層查詢 → 見 04-A 職責切分與入口規則"],
    "05": ["- 本模組無操作流程導覽。"],
    "09": ["- 本模組無操作流程導覽。"],
    "00": None,
}

# 00 Hub「三、條列規則」的結構描述句：V1.17 已改結構，逐條換掉
RULE_REPLACE = [
    (r"^[-*] 每一頁固定三段.*$",
     "- 每一頁的開頭是**一句話**（這頁在講什麼），接著直接進入該頁的畫面規格與條文；"
     "DEV V1.17 已取消「摘要＋原文」兩層寫法。"),
    (r"^[-*] 原本的長段落.*$",
     "- 全文只有一套規格：規則就寫在該頁本文裡，沒有另存一份原文折疊區。"),
    (r"^[-*] 每個模組固定三件套.*$",
     "- 每個模組固定兩件套：規格子頁（0N-A、0N-B…）＋ **0N-T 本模組驗收與錯誤處理**；"
     "必要的操作流程內嵌在所屬功能頁。"),
    (r"^[-*] 規格語義與 DEV V1\.15 完全一致.*$",
     "- 產品規則沿用 DEV V1.15，DEV V1.17 只動文件結構與可讀性。"),
]


def strip_w_rows(lines):
    """移除索引表中代碼為 0N-W 的列。"""
    out, dropped = [], []
    for l in lines:
        if re.match(r"^\|\s*0\d-W\s*\|", l) or re.match(r"^\|\s*🖼?\s*0\d-W\b", l):
            dropped.append(l.strip())
            continue
        out.append(l)
    return out, dropped


def process(code):
    src = os.path.join(SRC, f"{code}.md")
    lines = open(src, encoding="utf-8").read().split("\n")
    report = []

    # 1) 依據行
    for i, l in enumerate(lines):
        if l.startswith("> 依據："):
            report.append(f"依據行：{l.strip()}  →  {BASIS}")
            lines[i] = BASIS
            break

    # 2) 索引表移除 0N-W
    lines, dropped = strip_w_rows(lines)
    for d in dropped:
        report.append(f"移除索引列：{d[:70]}")

    # 3)「三、畫布入口」→「三、操作流程」
    if FLOW.get(code):
        s = e = None
        for i, l in enumerate(lines):
            if l.startswith("## 三、畫布入口"):
                s = i
            elif s is not None and l.startswith("## ") and i > s:
                e = i
                break
        if s is not None:
            e = e if e is not None else len(lines)
            lines[s:e] = ["## 三、操作流程", ""] + FLOW[code] + [""]
            report.append("「三、畫布入口」→「三、操作流程」（改為指向內嵌流程所在頁）")

    # 4) 00 Hub 的結構描述句
    if code == "00":
        for pat, new in RULE_REPLACE:
            for i, l in enumerate(lines):
                if re.match(pat, l):
                    report.append(f"條列規則：{l.strip()[:48]}…  →  {new[:48]}…")
                    lines[i] = new
                    break

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"
    open(os.path.join(DST, f"{code}.md"), "w", encoding="utf-8").write(text)
    return report


def main():
    os.makedirs(DST, exist_ok=True)
    for code in ["00", "01", "02", "03", "04", "05", "09"]:
        rep = process(code)
        print(f"\n===== {code}.md =====")
        for r in rep:
            print("  ·", r)


if __name__ == "__main__":
    main()
