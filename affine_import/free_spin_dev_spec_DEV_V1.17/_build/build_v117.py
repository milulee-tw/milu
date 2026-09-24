#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 free_spin_dev_spec_DEV_V1.17.html 的 40 個 sec-* 章節轉成 AFFiNE 匯入用 Markdown。
不改寫、不摘要、不補規則：只做 HTML → Markdown 的結構轉換。"""
import os, re, sys
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = "free_spin_dev_spec_DEV_V1.17.html"
OUT = "affine_import/free_spin_dev_spec_DEV_V1.17"

ROLE_TAGS = {"📋 企劃&PM", "🎲 機率組", "🖥 Web 前端", "⚙ 後端",
             "✅ QA", "🎨 美術", "📊 數據組", "🏗 基礎建設"}

CALLOUT_ICON = {"info": "ℹ️", "warn": "⚠️", "danger": "🚫", "success": "✅"}


# ─────────────── inline ───────────────
def inline(node):
    if isinstance(node, NavigableString):
        return re.sub(r"\s+", " ", str(node))
    if not isinstance(node, Tag):
        return ""
    n = node.name
    if n == "br":
        return "\n"
    if n in ("script", "style"):
        return ""
    kids = "".join(inline(c) for c in node.children)
    cls = node.get("class") or []
    if n in ("strong", "b"):
        t = kids.strip()
        return f"**{t}**" if t else ""
    if n in ("em", "i"):
        t = kids.strip()
        return f"*{t}*" if t else ""
    if n == "code" or "mono" in cls:
        t = kids.strip()
        return f"`{t}`" if t else ""
    if "ccy-pill" in cls:
        return f"`{kids.strip()}` "
    if "tag-pill" in cls:
        return f"〔{kids.strip()}〕"
    if "region-td" in cls:
        return f"{kids.strip()} "
    if n == "a":
        href = node.get("href", "")
        txt = kids.strip()
        m = re.match(r"^#sec-([0-9A-Z]+(?:-[0-9A-Z]+)?)$", href)
        if m:                                    # 跨頁：留待建頁後換成 AFFiNE 連結
            return f"[{txt}](affine://{m.group(1)})"
        if href.startswith("#"):                 # 同頁錨點：AFFiNE 無對應，降為純文字
            return txt
        return f"[{txt}]({href})" if href else txt
    return kids


def inline_of(node):
    return re.sub(r"[ \t]+", " ", "".join(inline(c) for c in node.children)).strip()


# ─────────────── blocks ───────────────
def table_md(tbl):
    rows = []
    for tr in tbl.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        rows.append([inline_of(c).replace("\n", "<br>").replace("|", "\\|") or " "
                     for c in cells])
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [" "] * (width - len(r)) for r in rows]
    head_is_th = bool(tbl.find("tr").find("th"))
    out = []
    if head_is_th:
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + "---|" * width)
        body = rows[1:]
    else:
        out.append("| " + " | ".join([" "] * width) + " |")
        out.append("|" + "---|" * width)
        body = rows
    out += ["| " + " | ".join(r) + " |" for r in body]
    return out


def list_md(ul, depth=0):
    out = []
    marker = "1." if ul.name == "ol" else "-"
    pad = "  " * depth
    for li in ul.find_all("li", recursive=False):
        nested = li.find_all(["ul", "ol"], recursive=False)
        for nn in nested:
            nn.extract()
        txt = inline_of(li).replace("\n", " ")
        if txt:
            out.append(f"{pad}{marker} {txt}")
        for nn in nested:
            out += list_md(nn, depth + 1)
    return out


def render(node, out):
    """把一個 block 節點轉成 markdown 行，append 進 out。"""
    if isinstance(node, NavigableString):
        t = re.sub(r"\s+", " ", str(node)).strip()
        if t:
            out.append(t)
        return
    if not isinstance(node, Tag):
        return
    n, cls = node.name, (node.get("class") or [])

    if n in ("script", "style"):
        return

    # ── 不進入 markdown 的骨架（已在 header 另外處理）──
    if {"page-basis", "section-header", "page-tags", "region-index-note",
        "lb-close", "lb-img", "lb-hint"} & set(cls):
        return

    if "one-liner" in cls:
        out += ["", inline_of(node), ""]
        return

    if "sub-title" in cls:
        out += ["", f"## {inline_of(node)}", ""]
        return

    if n == "table":
        out += [""] + table_md(node) + [""]
        return

    if n in ("ul", "ol"):
        out += [""] + list_md(node) + [""]
        return

    if n == "h4":
        func = node.find("span", class_="rd-func")
        ftxt = inline_of(func) if func else ""
        if func:
            func.extract()
        htxt = re.sub(r"^([Ⓐ-Ⓩ][′']?)\s+", r"\1 · ", inline_of(node))
        out += ["", f"### {htxt}", ""]
        if ftxt:
            out += [f"*{ftxt}*", ""]
        return

    if n in ("h1", "h2", "h3", "h5", "h6"):
        out += ["", f"### {inline_of(node)}", ""]
        return

    if "callout" in cls:
        icon = next((CALLOUT_ICON[k] for k in CALLOUT_ICON if k in cls), "ℹ️")
        has_block = any(isinstance(c, Tag) and c.name in
                        ("div", "table", "ul", "ol", "h4") for c in node.children)
        if has_block:
            inner = []
            for c in node.children:
                render(c, inner)
            body = [l for l in inner if l.strip()]
        else:
            body = [l.strip() for l in inline_of(node).split("\n") if l.strip()]
        out += [""] + [f"> {icon} {l}" if i == 0 else f"> {l}"
                       for i, l in enumerate(body)] + [""]
        return

    if "hypo-block" in cls:
        lab = node.find("div", class_="hypo-label")
        txt = node.find("div", class_="hypo-text")
        out += ["", f"> **{inline_of(lab) if lab else ''}**"]
        if txt:
            for line in inline_of(txt).split("\n"):
                out.append(f"> {line.strip()}")
        out += [""]
        return

    if "shot-frame" in cls:
        out += [""]
        for c in node.children:                 # 依文件順序走，別漏掉圖說以外的說明段
            if not isinstance(c, Tag):
                continue
            ccls = c.get("class") or []
            if "shot-ph" in ccls:               # 「圖片未載入」佔位，只是 HTML 的 fallback
                continue
            if c.name == "img":
                out.append(f"![{(c.get('alt') or '').replace(chr(10), ' ')}]({c.get('src', '')})")
            elif "shot-cap" in ccls:
                out.append(f"*{inline_of(c)}*")
            else:
                render(c, out)
        out += [""]
        return

    if "ccy-pills" in cls:
        out += ["", inline_of(node).strip(), ""]
        return

    if "flow-step" in cls:
        num = node.find("div", class_="flow-step-num")
        ttl = node.find("div", class_="flow-step-title")
        des = node.find("div", class_="flow-step-desc")
        parts = [f"**{inline_of(num)}**" if num else "",
                 f"**{inline_of(ttl)}**" if ttl else "",
                 inline_of(des) if des else ""]
        out.append("- " + " · ".join(p for p in parts if p))
        return

    if "flow-mini" in cls and "flow-mini-step" not in cls and "flow-mini-note" not in cls:
        steps = []
        for st in node.find_all("div", class_="flow-mini-step"):
            steps.append(inline_of(st))
        out += ["", " → ".join(s for s in steps if s), ""]
        return

    if "flow-mini-note" in cls:
        out += ["", f"*{inline_of(node)}*", ""]
        return

    if {"flow-arrow-down", "flow-mini-arrow"} & set(cls):
        return

    if "info-card" in cls:
        icon = node.find("div", class_="info-card-icon")
        ttl = node.find("div", class_="info-card-title")
        des = node.find("div", class_="info-card-desc")
        head = " ".join(x for x in [inline_of(icon) if icon else "",
                                    f"**{inline_of(ttl)}**" if ttl else ""] if x)
        out.append(f"- {head}：{inline_of(des) if des else ''}".rstrip("："))
        return

    if "oq-item" in cls:
        own = node.find("div", class_="oq-owner")
        q = node.find("div", class_="oq-q")
        out.append(f"- 〔{inline_of(own)}〕{inline_of(q) if q else ''}"
                   if own else f"- {inline_of(q) if q else ''}")
        return

    if "log-item" in cls:
        ev = node.find("span", class_="log-event")
        de = node.find("span", class_="log-desc")
        out.append(f"- `{inline_of(ev)}` — {inline_of(de) if de else ''}"
                   if ev else f"- {inline_of(node)}")
        return

    if "rd-label" in cls:
        out += ["", f"**{inline_of(node)}**", ""]
        return

    if n == "button" or "tab-btn" in cls:
        return

    if "tab-content" in cls:
        tid = node.get("id", "")
        out += ["", f"**分頁：{tid.replace('tab-', '').upper()}**", ""]
        for c in node.children:
            render(c, out)
        return

    # ── 容器：遞迴 ──
    if n in ("div", "section", "main", "tbody", "thead", "span", "details", "summary"):
        has_block = any(isinstance(c, Tag) and (
            c.name in ("div", "table", "ul", "ol", "h4", "section", "details")
        ) for c in node.children)
        if has_block:
            for c in node.children:
                render(c, out)
        else:
            t = inline_of(node)
            if t:
                out += ["", t, ""]
        return

    if n == "p":
        t = inline_of(node)
        if t:
            out += ["", t, ""]
        return

    t = inline_of(node)
    if t:
        out += ["", t, ""]


# ─────────────── 主流程 ───────────────
def clean(lines):
    res, blank = [], 0
    for l in lines:
        l = l.rstrip()
        if not l.strip():
            blank += 1
            if blank > 1 or not res:
                continue
            res.append("")
        else:
            blank = 0
            res.append(l)
    while res and not res[-1].strip():
        res.pop()
    return res


def main():
    html = open(SRC, encoding="utf-8").read()
    soup = BeautifulSoup(html, "html.parser")
    os.makedirs(OUT, exist_ok=True)

    pages = {}
    for sec in soup.find_all("section", class_="section"):
        sid = sec.get("id", "")
        if not sid.startswith("sec-"):
            continue
        code = sid[4:]

        basis = sec.find("div", class_="page-basis")
        basis_txt = inline_of(basis) if basis else ""

        hdr = sec.find("div", class_="section-header")
        num = hdr.find("span", class_="section-num")
        ttl = hdr.find("span", class_="section-title")
        num_txt, ttl_txt = inline_of(num), inline_of(ttl)
        m = re.match(r"^([^\sA-Za-z0-9]+)\s*(.*)$", ttl_txt)
        emoji, name = (m.group(1), m.group(2)) if m else ("📋", ttl_txt)
        title = f"{emoji} {num_txt} · {name}"

        tags = sec.find("div", class_="page-tags")
        roles = []
        if tags:
            for tp in tags.find_all("span", class_="tag-pill"):
                t = inline_of(tp).strip("〔〕")
                if t in ROLE_TAGS:
                    roles.append(t)

        body = []
        for c in sec.children:
            render(c, body)
        body = clean(body)

        head = [f"# {title}", "",
                f"> 依據：規格 DEV V1.17（產品規則沿用 DEV V1.15）",
                f"> 來源：{basis_txt.replace('來源：', '')}" if basis_txt else None,
                f"> 職能：{' · '.join(roles)}" if roles else None]
        head = [h for h in head if h is not None]
        pages[code] = {"title": title, "emoji": emoji, "name": name,
                       "roles": roles, "lines": head + [""] + body}

    for code, p in pages.items():
        with open(os.path.join(OUT, f"{code}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(p["lines"]) + "\n")

    print(f"寫出 {len(pages)} 頁 → {OUT}")
    for c in sorted(pages):
        print(f"  {c:6s} {pages[c]['title']}  ({sum(len(l) for l in pages[c]['lines'])} 字)")


if __name__ == "__main__":
    main()
