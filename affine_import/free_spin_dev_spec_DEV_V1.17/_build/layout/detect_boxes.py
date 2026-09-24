#!/usr/bin/env python3
"""偵測原型截圖上的紅色標號框，回傳每個標號（Ⓐ…）對應的矩形。

作法：
1. 取紅色遮罩。
2. 找實心圓標號（距離轉換的局部極大值）——圓心＝該框的左上角。
3. 找水平／垂直邊線線段（長度夠長的紅色連續段，並把相鄰列合併）。
4. 依「上下兩條水平線 ＋ 左右兩條垂直線」湊成矩形。
5. 把每個矩形配給離它左上角最近的標號圓。
"""
import sys
import json
import numpy as np
from PIL import Image
from scipy import ndimage

LETTERS = "ABCDEFGHIJKLMN"


def red_mask(im):
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 140) & (r - g > 55) & (r - b > 55)


def find_labels(mask):
    """標號圓＝紅色實心圓裡挖著白色字母。
    所以「紅色遮罩補洞後多出來的小面積破洞」就是字母，其重心即標號位置。
    框線的內部也是破洞，但面積大好幾個數量級，用面積切開即可。
    回傳 [(y, x)]，依閱讀順序排序。"""
    filled = ndimage.binary_fill_holes(mask)
    holes = filled & ~mask
    lab, n = ndimage.label(holes)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        area = ys.size
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        if not (80 <= area <= 6000):        # 字母級大小；框內部大好幾個數量級
            continue
        if h > 120 or w > 120:
            continue
        out.append((float(ys.mean()), float(xs.mean())))
    out.sort(key=lambda t: (round(t[0] / 120), t[1]))
    return out


def runs(row_mask, min_len):
    """一維遮罩裡長度 >= min_len 的連續段，回傳 [(start, end)]。"""
    idx = np.flatnonzero(row_mask)
    if idx.size == 0:
        return []
    splits = np.flatnonzero(np.diff(idx) > 6) + 1      # 容許標號圓造成的小缺口
    out = []
    for part in np.split(idx, splits):
        if part[-1] - part[0] + 1 >= min_len:
            out.append((int(part[0]), int(part[-1])))
    return out


def lines(mask, axis, min_len):
    """沿 axis 掃描出線段並合併相鄰掃描列。回傳 [(pos, start, end)]。"""
    n = mask.shape[0] if axis == 0 else mask.shape[1]
    found = []
    for p in range(n):
        row = mask[p, :] if axis == 0 else mask[:, p]
        for s, e in runs(row, min_len):
            found.append((p, s, e))
    merged = []
    for p, s, e in found:
        for m in merged:
            if abs(m[0] - p) <= 8 and not (e < m[1] - 20 or s > m[2] + 20):
                m[0] = p
                m[1] = min(m[1], s)
                m[2] = max(m[2], e)
                break
        else:
            merged.append([p, s, e])
    return [tuple(m) for m in merged]


def rectangles(mask, min_len=160):
    hs = lines(mask, 0, min_len)
    vs = lines(mask, 1, min_len)
    rects = []
    for i, (y1, x1a, x1b) in enumerate(hs):
        for (y2, x2a, x2b) in hs[i + 1:]:
            if y2 - y1 < 60:
                continue
            xa, xb = max(x1a, x2a), min(x1b, x2b)
            if xb - xa < min_len:
                continue
            if abs(x1a - x2a) > 40 or abs(x1b - x2b) > 40:
                continue
            left = [v for v in vs if abs(v[0] - xa) <= 25 and v[1] <= y1 + 40 and v[2] >= y2 - 40]
            right = [v for v in vs if abs(v[0] - xb) <= 25 and v[1] <= y1 + 40 and v[2] >= y2 - 40]
            if left and right:
                rects.append((xa, y1, xb, y2))
    # 去掉幾乎重複的矩形
    uniq = []
    for r in sorted(rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True):
        if not any(abs(r[0] - u[0]) < 25 and abs(r[1] - u[1]) < 25
                   and abs(r[2] - u[2]) < 25 and abs(r[3] - u[3]) < 25 for u in uniq):
            uniq.append(r)
    return uniq


def detect(path):
    im = Image.open(path)
    mask = red_mask(im)
    labels = find_labels(mask)
    rects = rectangles(mask)
    pairs = []
    for i, (ly, lx) in enumerate(labels):
        for j, (x0, y0, x1, y1) in enumerate(rects):
            d = ((y0 - ly) ** 2 + (x0 - lx) ** 2) ** 0.5
            if d <= 160:
                pairs.append((d, (x1 - x0) * (y1 - y0), i, j))
    pairs.sort()
    taken_l, taken_r, assign = set(), set(), {}
    for d, area, i, j in pairs:
        if i in taken_l or j in taken_r:
            continue
        taken_l.add(i); taken_r.add(j); assign[i] = j
    return im.size, [{"letter": LETTERS[i],
                      "rect": list(rects[assign[i]]) if i in assign else None}
                     for i in range(len(labels))]


if __name__ == "__main__":
    for p in sys.argv[1:]:
        size, res = detect(p)
        print(json.dumps({"file": p.split("/")[-1], "size": size, "regions": res},
                         ensure_ascii=False))
