<!-- 封面圖：在 GitHub 網頁編輯此檔，把封面圖拖到這一行上方，會自動上傳並產生 <img> 連結 -->

# CharacterLighting12

**English** · [繁體中文](#繁體中文)

12 lighting setups for characters. Pick the character you want to light, press once, and the lights place themselves — distance, size and power all scale to how big your subject is.

For anyone building characters in Blender who doesn't want to rig lights from scratch every time, and who wants to see how each setup is put together.

> Made by Zack3D (with AI assistance).

## Every preset comes with a note

Each one carries a short description of what the light is and what technique it uses, plus one thing you can try changing.

The presets are plain JSON. Open `presets/` and you can read them. The beauty-ring setup, for instance, is a glowing torus and two lamps.

The ideas behind these twelve — key/fill/rim, using glowing objects as light sources, bounce boards and blockers — are covered in this tutorial: [Blender 打光教學](https://www.youtube.com/watch?v=dP_LDNFjT3k) (Mandarin).

## The Light Domain

Select your character and press **Build Light Domain**. The add-on measures it and creates an empty; every light is parented to that empty.

Rotate the empty and the whole rig orbits the character. Move the Distance slider and the lights pull back, with power compensating by inverse-square at the same time.

Values are stored relative to subject size, so one preset works on a 1.8-unit character and a 20-unit one.

## The twelve

| | | |
|---|---|---|
| Simple Panel | Studio | Angel Light |
| Beauty Ring | Influencer | Melancholy |
| Eerie | Venetian Blinds | Sunset Mood |
| Futuristic | Gradient | Retro |

They're ordered from simple to involved, so the first ones are the easiest to read.

## What it does

- 12 presets that scale to your subject
- The Light Domain: one empty controls the whole rig
- Four sliders: intensity, colour temperature, distance, rotation. Move a single light by hand first and the sliders work on top of that, they don't wipe it
- Isolate the subject: hide the scene's existing lights and other objects with one press
- Save your own version of a preset. The built-in ones stay intact and you can revert
- Add your own presets, with the thumbnail rendered for you or supplied as an image
- Export and import: one preset is one file, thumbnail included
- The interface follows Blender's language setting

## Cycles only

The values were set in Cycles. Retro uses volumetric fog, and Sunset Mood and Gradient use procedural textures, which behave differently in EEVEE. The panel says so when the engine isn't Cycles and offers to switch.

## Installation

1. Download the latest `.zip` from **Releases** on the right (no need to unzip)
2. Open Blender → **Edit › Preferences**
3. **Add-ons** on the left → **Install from Disk…** (top-right)
4. Select the `.zip` → install
5. Tick the checkbox next to "Character Lighting 12"

## How to use it

1. N-panel → **Lighting** tab
2. Select your character → **Build Light Domain**. To look around first, press **Load Example** instead
3. Flip through the thumbnails, read the note, press **Apply Light**
4. Adjust with the sliders, or move any light yourself
5. **Overwrite** saves over the current preset, **New Preset** saves a new one

## Tutorial

[![YouTube](https://img.youtube.com/vi/NFd1vk8QFXU/maxresdefault.jpg)](https://www.youtube.com/watch?v=NFd1vk8QFXU)

## Compatibility

- Blender 3.6 / 4.5 / 5.0 / 5.2 LTS (all tested)
- Cycles only

## License

Released under the **GNU GPL**. Author: Zack3D.

---

# 繁體中文

[English](#characterlighting12) · **繁體中文**

12 組角色打光預設。選好要打光的角色，按一下就套用，燈光的距離、大小、強度會依照角色的尺寸自動調整。

給用 Blender 做角色的人。省掉每次從零架燈的時間，也可以直接打開來看每一組燈是怎麼搭的。

> 由 Zack3D 製作（有 AI 協助）。

## 每組預設都附說明

每一組都有一段說明，講這是什麼光、用了什麼手法，另外一句是可以動手試的變化。

預設本身是 JSON，打開 `presets/` 就讀得到。像網美那組，其實就是一個發光的環形物體加兩盞燈。

這 12 組背後的觀念，包括主光／輔光／輪廓光、用發光物體當光源、反光板與遮擋物，在這支影片裡有講：[Blender 打光教學](https://www.youtube.com/watch?v=dP_LDNFjT3k)

## 光域

選取角色後按「建立光域」。外掛會量出角色的範圍，建立一個空物體，所有燈光都掛在它底下。

旋轉這個空物體，整組燈會繞著角色轉。拉動距離滑桿，燈會往外移動，強度同時照平方反比補償。

所有數值都是相對於角色尺寸存的，所以同一組預設用在 1.8 單位或 20 單位的角色上都成立。

## 12 組燈光

| | | |
|---|---|---|
| 簡單光板 | 一般棚燈 | 天使光 |
| 網美 | 網紅 | 憂鬱 |
| 靈異 | 百葉窗 | 夕陽氛圍 |
| 未來感 | 漸層 | 復古 |

順序由淺入深，前面幾組最好讀。

## 功能

- 12 組預設，依角色尺寸自動縮放
- 光域：一個空物體控制整組燈
- 四個滑桿：強度、色溫、距離、旋轉。先手動調過某一盞燈，滑桿會疊在你的調整之上，不會蓋掉
- 隔離主體：一鍵隱藏場景原有的燈光與其他物件
- 存成自己的版本，內建預設不會被蓋掉，可以還原
- 新增自己的預設，縮圖可以自動算，也可以用自己準備的圖
- 匯出與匯入：一組預設就是一個檔案，縮圖含在裡面
- 介面跟隨 Blender 的語言設定

## 需要 Cycles

數值是在 Cycles 底下調的。復古用了體積霧，夕陽氛圍與漸層用了程序紋理，這些在 EEVEE 下表現不同。面板會在引擎不是 Cycles 時提醒，並提供切換。

## 安裝

1. 從右邊的 **Releases** 下載最新的 `.zip`（不用解壓縮）
2. 打開 Blender → **編輯 › 偏好設定**
3. 點左側 **附加元件** → 右上角 **從磁碟安裝…**
4. 選擇剛下載的 `.zip` → 安裝
5. 勾選「Character Lighting 12」

## 使用方式

1. N 面板 → **打光** 分頁
2. 選取角色 → 按 **建立光域**。想先看看的話，直接按 **載入範例**
3. 翻縮圖、讀說明、按 **套用燈光**
4. 用滑桿調整，或直接抓某一盞燈自己移
5. **覆蓋** 存回目前這組，**新增燈光預設** 另存一組

## 教學

[![YouTube](https://img.youtube.com/vi/NFd1vk8QFXU/maxresdefault.jpg)](https://www.youtube.com/watch?v=NFd1vk8QFXU)

## 相容性

- Blender 3.6 / 4.5 / 5.0 / 5.2 LTS（皆已測試）
- 僅支援 Cycles

## 授權

以 **GNU GPL** 釋出。作者：Zack3D。
