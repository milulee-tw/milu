# 抽寶箱 v1 音效生成 · 操作說明

依 `treasure_box_dev_spec_v1.0.html`（DEV V1.11）§05〈音樂音效需求表〉產出。
本次範圍＝**11 條核心 SFX，每條 3 版（共 33 個檔案）**；不含 BGM、不含語音 VO。

> **prompt 不是照規格書文字直譯的。** 我用 Playwright 把原型 v2 完整玩過一遍，掛動畫監聽器錄下時間軸、
> 解 CSS 關鍵幀算出每條音效的「重音落點」，再據此改寫。例如洗牌實際是**金幣旋渦**不是撲克牌、
> 翻格的換面瞬間在 **170ms** 不在 0ms、最終大獎的光爆點在 **1.05s**。細節見 `sfx_prompts.json` 的
> `proto_measured` 與 `proto_note` 欄位，或直接開試聽對照表看。

---

## 為什麼要你自己在電腦上跑

Claude 的雲端環境與 Mac 上的 Cowork 工作區**都連不到 `api.elevenlabs.io`**（網路白名單擋掉）。
所以改成把腳本交給你，在你自己的終端機執行——**API 金鑰完全不會離開你的電腦**，也不用貼到聊天視窗。

---

## 三步驟

### 1. 拿一把 API 金鑰

到 <https://elevenlabs.io> → 右上頭像 → **API Keys** → Create。
建立時**務必勾選 `sound_generation` 權限**，否則腳本會回 401。

### 2. 執行

打開「終端機」，把下面四行**逐行**貼上（第一行的路徑就是這些檔案放的位置）：

```bash
cd '/Users/milulee/Library/CloudStorage/GoogleDrive-milulee.tw@gmail.com/共用雲端硬碟/Force相關(藍玥)/github.milu/treasure_box_sfx'
export ELEVENLABS_API_KEY="把你的金鑰貼在這裡"
python3 generate_sfx.py --dry-run    # 先空跑看清單，不花額度
python3 generate_sfx.py              # 確認後正式生成
```

跑完會多出一個 `sfx_out/` 資料夾，裡面是 33 個檔案，檔名已照規格書命名規則：

```
theme_treasure_box_sfx_unlock_v1.mp3
theme_treasure_box_sfx_unlock_v2.mp3
theme_treasure_box_sfx_unlock_v3.mp3
...（共 11 條 × 3 版 ＝ 33 個）
sfx_out/trimmed/    ← 若電腦有 ffmpeg，會多這層：裁切到規格秒數＋尾端淡出
manifest.json       ← 生成紀錄
```

### 3. 挑版本

用瀏覽器打開 **`音效試聽對照表.html`**，11 條 × A/B/C 並排試聽，每條按「選這版」定稿，
最後按「匯出定稿清單」→ 直接貼給音效外包或放進規格書修改紀錄。

---

## 常用指令

| 情境 | 指令 |
|---|---|
| 只有某幾條不滿意，單獨重生 | `python3 generate_sfx.py --only flip,locked` |
| 高光音效想多生幾版來挑 | `python3 generate_sfx.py --only final_reveal --variants 8` |
| 不想做 ffmpeg 裁切 | `python3 generate_sfx.py --no-trim` |
| 先看會送出什麼、不花額度 | `python3 generate_sfx.py --dry-run` |

想調音色，直接改 `sfx_prompts.json` 裡該條的 `prompt` 文字再重跑該條即可。
`prompt_influence` 越高越貼近文字描述、越低則 AI 自由發揮空間越大（0～1）。

### 選用：安裝 ffmpeg（做裁切對齊）

規格書裡 `panel_close`、`locked` 要求 0.3 秒，但 ElevenLabs 最短只能生 0.5 秒。
腳本會先生 0.5 秒，再用 ffmpeg 裁到目標長度並加 60ms 淡出（避免尾端爆音）。

```bash
brew install ffmpeg
```

沒裝也能跑，只是不會產出 `trimmed/` 那層。

---

## 額度概估

Sound Effects 大約以「每秒 100 credits」計費，11 條 × 3 版約 **4,100 credits**。
免費方案每月 10,000 credits，跑一輪綽綽有餘。實際扣款以官方帳單為準。

---

## 已知取捨（給音效外包看的）

| 項目 | 說明 |
|---|---|
| AI 生成 vs 外包 | 這批是**選型用的參考音（scratch audio）**，用途是讓前端先接上時間軸、讓大家聽到方向對不對。要不要直接當正式素材，取決於 ElevenLabs 授權條款與你們對音質的要求。 |
| 0.3 秒條目 | API 下限 0.5 秒，靠 ffmpeg 裁切。裁切版聽起來若太突兀，正式素材建議請外包重錄。 |
| 獎階分三階 | 2026-08-17 決議推翻 V1.10「獎階通用一條」：改為 `prize_s／_m／_l` 三條。第四階 `final` **不另做**——原型中 `data-prize="final"` 的格子點擊後直接進全螢幕演出，由 `final_reveal` 承接。三條要屬同一組音色家族（同樣的金幣質感），只在份量上排層次，且 `prize_l` **不可搶過** `final_reveal`。 |
| locked 待前端補 | 音效確定要做，但原型 v2 點鎖定格**目前無任何回饋**（`cursor: default`）。前端須補互動（建議沿用原型已有的 `chestShake` 0.6s）音效才有地方掛。 |
| daily_done 待原型補 | P7 每日結算卡確定要做，但原型 v2 未實作。音效先照規格書 1~1.5 秒生成，結算卡動畫做出來後回頭校秒數。 |
| BGM 未生成 | `theme_treasure_box_bgm_panel`（30~60s 無縫 loop）本次未做。無縫 loop 用一般 AI 音效工具做不出來——建議走 ElevenLabs Music 或 Suno，並在交付時明確要求「循環點無爆音」。 |
| 語音 VO 未生成 | 依 DEV V1.10 決策「語音牽動 13 語系成本，v1 不做」。 |
