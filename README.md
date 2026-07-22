<!-- 封面圖：在 GitHub 網頁編輯此檔，把封面圖拖到這一行上方，會自動上傳並產生 <img> 連結 -->

# CharacterLighting12

**English** · [繁體中文](#繁體中文)

Twelve character lighting setups, one click each. Pick your subject, and every light **scales itself** to fit — distance, size and power all follow the size of what you're lighting.

> Made by Zack3D (with AI assistance).

## This is a lesson, not just a preset pack

Most lighting add-ons hand you a result. This one tells you what you're looking at: every preset carries a short note on **what the light is, when to use it**, and one thing to try changing. The presets themselves are plain, readable JSON — open `presets/` and you can see that the beauty-ring look is literally a glowing torus and two lamps.

**Want the theory behind these setups?** Zack's lighting tutorial covers the ideas these
presets are built on — key/fill/rim, using glowing objects as lights, bounce boards and
blockers: **[Blender 打光教學](https://www.youtube.com/watch?v=dP_LDNFjT3k)** (Mandarin)

## The Light Domain

Select your character and press one button. The add-on measures it and builds a **Light Domain** — an empty that defines the lighting volume.

- **Rotate the domain** → the whole rig orbits your subject
- **Scale the distance** → lights move out, and their power compensates automatically (inverse-square)
- Every light is parented to it, so nothing drifts out of alignment

Because everything is stored relative to subject size, the same preset works on a 1.8-unit character and a 20-unit one.

## The 12 lights

| | | |
|---|---|---|
| Simple Panel | Studio | Angel |
| Beauty Ring | Influencer | Moody |
| Horror | Blinds | Sunset |
| Futuristic | Gradient | Retro |

Ordered by how much there is to learn from them, not alphabetically — start at the top.

## Features

- **12 presets**, each scaled to your subject automatically
- **Light Domain**: one empty controls the whole rig — rotate, scale, reposition
- **Four global controls**: intensity, colour temperature, distance, rotation. Hand-tweak any individual light afterwards; the sliders work on top of your changes rather than wiping them
- **Save your own version**: adjust the lights in the viewport, press save. Built-in presets are never overwritten, and there's a one-click revert
- **Load Example**: brings in a sample character and a matching camera, so you can see each light the way it was designed. Press again to remove it — nothing is left in your scene unless you ask for it
- **Bilingual UI**: follows Blender's own language setting

## Requires Cycles

The values were calibrated in Cycles. Several presets rely on volumetric fog and procedural textures that behave differently in EEVEE — the panel will tell you when you're in the wrong engine and offer to switch. EEVEE support may come later.

## Installation

1. Download the latest `.zip` from **Releases** on the right (no need to unzip)
2. Open Blender → top menu **Edit › Preferences**
3. Click **Add-ons** on the left → **Install from Disk…** (top-right)
4. Select the `.zip` you downloaded → install
5. Tick the checkbox next to "Character Lighting 12" to enable it

## Usage

1. Open the N-panel → **Lighting** tab
2. Select your character → press **Set Subject & Build Domain**
   (or press **Load Example** if you just want to look around first)
3. Flip through the thumbnails, read the note, press **Apply This Light**
4. Adjust with the four sliders, or grab any light and move it yourself
5. Happy with it? **Update This Preset** saves your version

## Compatibility

- Blender 3.6 / 4.5 / 5.0 / 5.2 LTS (all tested)
- Cycles only

## License

Released under the **GNU GPL**. Author: Zack3D.

---

# 繁體中文

[English](#characterlighting12) · **繁體中文**

12 種角色打光，一種一個按鈕。選好主體，燈光會**自己縮放**——距離、尺寸、強度全部跟著你要打的東西走。

> 由 Zack3D 製作（有 AI 協助）。

## 這是一堂課，不只是預設包

大部分打光外掛給你的是結果。這個會告訴你你在看什麼：每組預設都附一段短說明，講**這是什麼光、什麼場合用**，再給一個可以立刻動手試的變化。

預設本身是看得懂的 JSON。打開 `presets/` 你會發現，網美光其實就是一個發光的甜甜圈加兩盞燈。

**想知道這些光是怎麼想出來的？** 這 12 組背後的觀念——主光／輔光／輪廓光、用發光物體當光源、
反光板與遮擋物——都在這支影片裡：**[Blender 打光教學](https://www.youtube.com/watch?v=dP_LDNFjT3k)**

## 光域

選好角色，按一個按鈕。外掛會量出它的大小，建立一個**光域**——決定打光範圍的空物體。

- **旋轉光域** → 整組燈繞著主體轉
- **調整距離** → 燈往外拉，強度自動補償（照平方反比）
- 所有燈都掛在它底下，不會有東西跑掉

因為所有數值都是相對於主體尺寸存的，同一組預設在 1.8 單位的角色和 20 單位的角色上都成立。

## 12 種燈光

| | | |
|---|---|---|
| 簡單光板 | 一般棚燈 | 天使光 |
| 網美 | 網紅 | 憂鬱 |
| 靈異 | 百葉窗 | 夕陽氛圍 |
| 未來感 | 漸層 | 復古 |

順序是照「能學到多少」排的，不是照筆劃——從第一個開始看。

## 功能

- **12 組預設**，全部自動縮放到你的主體
- **光域**：一個空物體控制整組燈——轉它、縮它、移它
- **四個全域控制**：強度、色溫、距離、旋轉。你可以先手動微調某一盞燈，滑桿是**疊在你的調整之上**，不會把你的手動修改洗掉
- **存成自己的版本**：在視窗裡把燈調到滿意，按存檔。內建預設永遠不會被蓋掉，而且可以一鍵還原
- **載入範例**：帶進一個範例角色與對應的相機，讓你用設計時的視角看每一種光。再按一次就移除——你不叫它，它不會出現在你的場景裡
- **雙語介面**：跟隨 Blender 自己的語言設定

## 需要 Cycles

這些數值是在 Cycles 底下校過的。有幾組用到體積霧與程序紋理，在 EEVEE 下表現會不一樣——面板會在你用錯引擎時提醒，並提供一鍵切換。EEVEE 支援可能之後再做。

## 安裝

1. 從右邊的 **Releases** 下載最新的 `.zip`（不用解壓縮）
2. 打開 Blender → 上方選單 **編輯 › 偏好設定**
3. 點左側 **附加元件** → 右上角 **從磁碟安裝…**
4. 選擇剛下載的 `.zip` → 安裝
5. 勾選「Character Lighting 12」旁邊的核取方塊來啟用

## 使用方式

1. 打開 N 面板 → **打光** 分頁
2. 選取你的角色 → 按 **選取主體並建立光域**
   （想先隨便看看的話，直接按 **載入範例**）
3. 翻縮圖、讀說明、按 **套用這組燈光**
4. 用四個滑桿調整，或直接抓某一盞燈自己移
5. 滿意了就按 **更新這個預設**，存成你自己的版本

## 相容性

- Blender 3.6 / 4.5 / 5.0 / 5.2 LTS（皆已測試）
- 僅支援 Cycles

## 授權

以 **GNU GPL** 釋出。作者：Zack3D。
