#!/usr/bin/env python3
"""把來源 .md 轉成 A＋B＋C 版型的 markdown。

A 區域卡片化：強調引用段落 → GFM 警示框（AFFiNE 會變成 callout）；
              「防呆與錯誤」整段 → WARNING callout；區域之間插分隔線。
B 區域表格化：頁首「區域總覽表」加第三欄，逐字沿用各區的斜體一句話。
C 局部截圖：  在 `### Ⓧ` 標題下插入該區的裁切圖（只有 CROPS 裡有的頁才做）。

規則：不新增、不改寫、不刪除任何規格文字。
"""
import os
import re
import sys

PKG = ("/Users/milulee/Library/CloudStorage/GoogleDrive-milulee.tw@gmail.com/"
       "共用雲端硬碟/Force相關(藍玥)/github.milu/affine_import/free_spin_dev_spec_DEV_V1.17")

ALERT = {"ℹ": "NOTE", "✅": "TIP", "⚠": "WARNING", "\U0001f6ab": "CAUTION"}

# 哪些頁要插區域裁切圖：代碼 → 裁切圖檔名前綴
CROPS = {
    "01-A": "fs_admin_01_issuance_list",
    "01-B": "fs_admin_02_card_form",
    "02-B": "fs_bag_01_backpack",
}

CIRCLED = "ⒶⒷⒸⒹⒺⒻⒼⒽⒾ"   # Ⓐ…Ⓘ
LETTER = {c: chr(ord("A") + i) for i, c in enumerate(CIRCLED)}


def alert_kind(text):
    """引用段落第一個字是強調 emoji 就回傳警示種類，否則 None。"""
    for ch in text[:3]:
        if ch in ALERT:
            return ALERT[ch]
    return None


def region_oneliners(lines):
    """收集每個 `### Ⓧ · …` 區段底下那句斜體一句話（逐字，不改寫）。"""
    out, cur = {}, None
    for ln in lines:
        m = re.match(r'^### ([Ⓐ-Ⓘ])\s*·', ln)
        if m:
            cur = m.group(1)
            continue
        if cur and ln.startswith("*") and ln.endswith("*") and not ln.startswith("**"):
            out.setdefault(cur, ln.strip("*").strip())
            cur = None
    return out


def build(code, src):
    lines = src.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    ones = region_oneliners(lines)
    crop = CROPS.get(code)
    out = []
    i = 0
    first_quote_done = False
    seen_region = False
    n_alert = n_callout = n_div = n_crop = 0

    while i < len(lines):
        ln = lines[i]

        # ── 引用段落 ─────────────────────────────────────────
        if ln.startswith(">"):
            blk = []
            while i < len(lines) and lines[i].startswith(">"):
                blk.append(lines[i])
                i += 1
            body = [re.sub(r'^>\s?', '', b) for b in blk]
            kind = alert_kind(body[0]) if first_quote_done else None
            first_quote_done = True
            if kind:
                out.append(f"> [!{kind}]")
                out.extend("> " + b if b else ">" for b in body)
                n_alert += 1
            else:
                out.extend(blk)
            continue

        # ── 「防呆與錯誤」整段 → WARNING callout ──────────────
        if ln.strip() == "**防呆與錯誤**":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            items = []
            while j < len(lines) and lines[j].startswith("- "):
                items.append(lines[j][2:])
                j += 1
            if items:
                out.append("> [!WARNING]")
                out.append("> **防呆與錯誤**")
                out.extend("> " + it for it in items)
                n_callout += 1
                i = j
                continue

        # ── 標題：插分隔線 ───────────────────────────────────
        if ln.startswith("### ") and re.match(r'^### [Ⓐ-Ⓘ]', ln):
            if seen_region:
                out.append("")
                out.append("---")
                n_div += 1
            seen_region = True
            out.append("")
            out.append(ln)
            i += 1
            if crop:
                letter = LETTER[ln[4]]
                out.append("")
                out.append(f"\u27e6IMG:{crop}_r{letter}.png\u27e7")
                n_crop += 1
            continue

        if ln.startswith("## "):
            if ln.startswith("## 區域詳細說明") or seen_region:
                out.append("")
                out.append("---")
                n_div += 1
            out.append("")
            out.append(ln)
            i += 1
            continue

        # ── 圖片：與圖說之間留空行，讓它們變成兩個區塊 ───────
        if ln.startswith("!["):
            mm = re.match(r'^!\[[^\]]*\]\(([^)]+)\)\s*$', ln)
            if mm:
                out.append("\u27e6IMG:" + os.path.basename(mm.group(1)) + "\u27e7")
                if i + 1 < len(lines) and lines[i + 1].startswith("*"):
                    out.append("")
                i += 1
                continue

        out.append(ln)
        i += 1

    text = "\n".join(out)
    text = add_overview_column(text, ones)
    text = resolve_links(text)
    text = split_long_tables(text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + "\n"
    return text, dict(alert=n_alert, callout=n_callout, divider=n_div, crop=n_crop)


MAX_BODY = 19          # AFFiNE 單表上限 20 列（表頭＋19 列內容）


def split_long_tables(text):
    """超過 20 列的表格切成多張，每張重複表頭——AFFiNE 的硬限制。"""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        if not lines[i].startswith("|"):
            out.append(lines[i]); i += 1; continue
        blk = []
        while i < len(lines) and lines[i].startswith("|"):
            blk.append(lines[i]); i += 1
        if len(blk) < 3 or len(blk) - 2 <= MAX_BODY:
            out.extend(blk); continue
        head, sep, body = blk[0], blk[1], blk[2:]
        for k in range(0, len(body), MAX_BODY):
            if k:
                out.append("")
            out.extend([head, sep] + body[k:k + MAX_BODY])
    return "\n".join(out)


WS = "9203b8ba-5261-4784-910b-6e0fa4a08a0b"
BASE = f"http://10.10.66.10:3010/workspace/{WS}/"


def doc_ids():
    """從 affine-map.md 第一張表讀出 代碼 → docId。"""
    out, seen = {}, set()
    for line in open(os.path.join(PKG, "affine-map.md"), encoding="utf-8"):
        m = re.match(r'\|\s*([0-9]{2}(?:-[A-Z])?)\s*\|\s*[^|]+?\s*\|\s*([A-Za-z0-9_-]{8,})\s*\|', line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out[m.group(1)] = m.group(2)
    return out


IDS = doc_ids()


def resolve_links(text):
    """把 affine://<代碼> 佔位連結換成真實文件網址（上次同步已這樣做，不可退回）。"""
    def sub(m):
        code = m.group(1)
        if code not in IDS:
            raise SystemExit(f"affine://{code} 找不到對應 docId")
        return "](" + BASE + IDS[code] + ")"
    return re.sub(r'\]\(affine://([0-9]{2}(?:-[A-Z])?)\)', sub, text)


def add_overview_column(text, ones):
    """區域總覽表加第三欄：內容逐字沿用該區的斜體一句話。"""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if not re.match(r'^\|\s*區域\s*\|', ln):
            continue
        if ln.count("|") != 3:            # 已經不是兩欄就不動
            continue
        # 先看有沒有內容可填；整欄都空就不加，免得多一欄空白
        j, cells = i + 2, []
        while j < len(lines) and lines[j].startswith("|"):
            # Ⓑ′、Ⓐ′ 這類加撇號的列是另一張截圖的區域，不可沿用 Ⓑ、Ⓐ 的說明
            m = re.match(r'^\|\s*([Ⓐ-Ⓘ])(?!′)', lines[j])
            cells.append(ones.get(m.group(1), "") if m else "")
            j += 1
        if not any(cells):
            break
        lines[i] = ln.rstrip() + " 這區在做什麼 |"
        lines[i + 1] = lines[i + 1].rstrip() + "---|"
        for k, cell in enumerate(cells):
            lines[i + 2 + k] = lines[i + 2 + k].rstrip() + f" {cell} |"
        break
    return "\n".join(lines)


if __name__ == "__main__":
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "built")
    os.makedirs(outdir, exist_ok=True)
    tot = dict(alert=0, callout=0, divider=0, crop=0)
    for code in sys.argv[1:]:
        src = open(os.path.join(PKG, code + ".md"), encoding="utf-8").read()
        text, st = build(code, src)
        open(os.path.join(outdir, code + ".md"), "w", encoding="utf-8").write(text)
        for k in tot:
            tot[k] += st[k]
        print(f"{code:<6} 警示{st['alert']:>2} 防呆callout{st['callout']:>2} "
              f"分隔線{st['divider']:>2} 裁圖{st['crop']:>2}")
    print("\n合計：", tot)
