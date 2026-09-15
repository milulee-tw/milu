#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽寶箱 v1 音效一鍵生成腳本（ElevenLabs Sound Effects API）
================================================================
只用 Python 3 標準函式庫，macOS 內建的 python3 就能跑，不需要 pip install。

用法（在這個檔案所在的資料夾開終端機）：
    export ELEVENLABS_API_KEY="你的金鑰"
    python3 generate_sfx.py

常用參數：
    --only unlock,flip        只生指定幾條（用 event 名稱，逗號分隔）
    --variants 5              每條生幾版（預設 3）
    --outdir sfx_out          輸出資料夾（預設 sfx_out）
    --no-trim                 不做 ffmpeg 裁切／淡出後製
    --dry-run                 只印出會做什麼、不真的呼叫 API（不花額度）
    --yes                     跳過開始前的確認

產出：
    sfx_out/theme_treasure_box_sfx_<event>_v1.mp3   （API 原始輸出）
    sfx_out/trimmed/theme_treasure_box_sfx_<event>_v1.mp3  （裁切至規格秒數＋尾端淡出，需 ffmpeg）
    sfx_out/manifest.json                           （生成紀錄，給試聽表用）
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_BASE = "https://api.elevenlabs.io"
ENDPOINT = "/v1/sound-generation"
OUTPUT_FORMAT = "mp3_44100_128"
HERE = os.path.dirname(os.path.abspath(__file__))


def die(msg):
    print("\n[錯誤] " + msg + "\n", file=sys.stderr)
    sys.exit(1)


def http_json(path, api_key):
    req = urllib.request.Request(API_BASE + path, headers={"xi-api-key": api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def check_key(api_key):
    """驗證金鑰並回傳剩餘額度字串。"""
    if api_key and not api_key.startswith("sk_"):
        die("你貼的不是金鑰，是「API key 的 ID」。\n"
            "  真正的金鑰以 sk_ 開頭，只在建立或 rotate 的當下顯示一次。\n"
            "  拿法：elevenlabs.io → 右上頭像 → API Keys → 該 key 右側「⋮」→ Rotate\n"
            "        （或直接 Create new key），跳出的 sk_... 立刻複製。\n"
            "  建立時記得勾選 sound_generation 權限。")
    try:
        sub = http_json("/v1/user/subscription", api_key)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        if "api_key_id_used_as_api_key" in raw:
            die("你貼的不是金鑰，是「API key 的 ID」。\n"
                "  真正的金鑰以 sk_ 開頭，只在建立或 rotate 的當下顯示一次。\n"
                "  拿法：elevenlabs.io → 右上頭像 → API Keys → 該 key 右側「⋮」→ Rotate\n"
                "        （或直接 Create new key），跳出的 sk_... 立刻複製。")
        if "missing_permissions" in raw or "sound_generation" in raw:
            die("金鑰有效，但缺少 sound_generation 權限。\n"
                "  請到 API Keys 編輯該金鑰、勾選 Sound Generation 後再試。")
        if e.code == 401:
            die("金鑰無效或權限不足（401）。請確認 ELEVENLABS_API_KEY 是否貼對，"
                "且該金鑰有勾選 sound_generation 權限。")
        die("查詢帳號資訊失敗：HTTP %s\n%s" % (e.code, raw[:500]))
    except urllib.error.URLError as e:
        die("連不到 ElevenLabs：%s\n（請確認這台電腦可以正常上網、沒有被 VPN 或防火牆擋住）" % e.reason)

    used = sub.get("character_count")
    limit = sub.get("character_limit")
    tier = sub.get("tier", "unknown")
    if used is not None and limit is not None:
        return "方案 %s ／ 已用 %s ／ 上限 %s ／ 剩餘 %s credits" % (
            tier, f"{used:,}", f"{limit:,}", f"{limit - used:,}")
    return "方案 %s（額度資訊未提供）" % tier


def generate_one(api_key, text, duration, influence, out_path, retries=3):
    body = json.dumps({
        "text": text,
        "duration_seconds": duration,
        "prompt_influence": influence,
        "loop": False,
    }).encode("utf-8")
    url = API_BASE + ENDPOINT + "?output_format=" + OUTPUT_FORMAT
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                audio = r.read()
            if len(audio) < 512:
                raise RuntimeError("回傳音檔過小（%d bytes），可能生成失敗" % len(audio))
            with open(out_path, "wb") as f:
                f.write(audio)
            return True, len(audio)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            last_err = "HTTP %s：%s" % (e.code, detail)
            if e.code in (401, 403):
                die("金鑰被拒（%s）。請確認金鑰權限含 sound_generation。\n%s" % (e.code, detail))
            if e.code == 429:
                wait = 10 * attempt
                print("      · 觸發速率限制，等待 %ds 後重試…" % wait)
                time.sleep(wait)
                continue
            if 500 <= e.code < 600:
                time.sleep(4 * attempt)
                continue
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            time.sleep(3 * attempt)
    return False, last_err


def trim_with_ffmpeg(src, dst, target_seconds):
    """裁切至目標秒數並在尾端做 60ms 淡出，避免爆音。"""
    fade_start = max(0.0, target_seconds - 0.06)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", src,
        "-t", "%.3f" % target_seconds,
        "-af", "afade=t=out:st=%.3f:d=0.06" % fade_start,
        "-c:a", "libmp3lame", "-b:a", "128k", dst,
    ]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default=os.path.join(HERE, "sfx_prompts.json"))
    ap.add_argument("--outdir", default=os.path.join(HERE, "sfx_out"))
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.prompts):
        die("找不到 prompt 檔：%s" % args.prompts)
    with open(args.prompts, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]

    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        unknown = wanted - {i["event"] for i in items}
        if unknown:
            die("--only 有不存在的 event：%s" % ", ".join(sorted(unknown)))
        items = [i for i in items if i["event"] in wanted]

    total = len(items) * args.variants
    est_credits = sum(int(max(i["duration_seconds"], 1) * 100) for i in items) * args.variants

    print("=" * 62)
    print(" 抽寶箱 v1 音效生成 · ElevenLabs Sound Effects")
    print("=" * 62)
    print(" 條目數     ： %d 條 SFX" % len(items))
    print(" 每條版本數 ： %d 版" % args.variants)
    print(" 總生成次數 ： %d 次（約 %s credits，實際以官方計費為準）" % (total, f"{est_credits:,}"))
    print(" 輸出資料夾 ： %s" % args.outdir)

    if args.dry_run:
        print("\n[dry-run] 以下為將送出的內容，未呼叫 API：\n")
        for i in items:
            print("  %-46s %.1fs  influence=%.2f" % (i["filename"], i["duration_seconds"], i["prompt_influence"]))
            print("      %s\n" % i["prompt"])
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        die('沒有讀到金鑰。請先執行：\n    export ELEVENLABS_API_KEY="你的金鑰"')

    print(" 帳號狀態   ： %s" % check_key(api_key))
    print("=" * 62)

    if not args.yes:
        try:
            if input("\n確認開始生成？(y/N) ").strip().lower() not in ("y", "yes"):
                print("已取消。")
                return
        except EOFError:
            die("非互動環境請加上 --yes")

    os.makedirs(args.outdir, exist_ok=True)
    has_ffmpeg = shutil.which("ffmpeg") is not None
    do_trim = has_ffmpeg and not args.no_trim
    trim_dir = os.path.join(args.outdir, "trimmed")
    if do_trim:
        os.makedirs(trim_dir, exist_ok=True)
    elif not args.no_trim:
        print("\n[提醒] 找不到 ffmpeg，略過裁切後製。要啟用請先安裝：brew install ffmpeg\n")

    manifest, ok_count, fail = [], 0, []
    n = 0
    for item in items:
        print("\n▶ %s（%s）" % (item["filename"], item["spec_desc"]))
        for v in range(1, args.variants + 1):
            n += 1
            name = "%s_v%d.mp3" % (item["filename"], v)
            out_path = os.path.join(args.outdir, name)
            print("  [%d/%d] %s …" % (n, total, name), end=" ", flush=True)
            ok, info = generate_one(api_key, item["prompt"], item["duration_seconds"],
                                    item["prompt_influence"], out_path)
            rec = {
                "event": item["event"], "variant": v, "file": name,
                "spec_timing": item["spec_timing"], "spec_desc": item["spec_desc"],
                "spec_seconds": item["spec_seconds"], "target_seconds": item["target_seconds"],
                "duration_seconds": item["duration_seconds"], "prompt": item["prompt"],
                "ok": ok,
            }
            if ok:
                ok_count += 1
                print("OK（%.0f KB）" % (info / 1024))
                if do_trim:
                    t_out = os.path.join(trim_dir, name)
                    rec["trimmed"] = trim_with_ffmpeg(out_path, t_out, item["target_seconds"])
            else:
                fail.append((name, info))
                rec["error"] = str(info)
                print("失敗 → %s" % info)
            manifest.append(rec)
            time.sleep(1.2)  # 保守間隔，避免觸發速率限制

    with open(os.path.join(args.outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "variants": args.variants, "items": manifest}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 62)
    print(" 完成：成功 %d／%d" % (ok_count, total))
    if fail:
        print(" 失敗清單：")
        for name, err in fail:
            print("   · %s → %s" % (name, err))
        print(" 可用 --only <event> 單獨重生失敗的條目。")
    print(" 檔案位置：%s" % args.outdir)
    if do_trim:
        print(" 裁切版本：%s（已對齊規格秒數）" % trim_dir)
    print(" 下一步：把 音效試聽對照表.html 放到同一層，用瀏覽器開啟即可 A/B/C 試聽。")
    print("=" * 62)


if __name__ == "__main__":
    main()
