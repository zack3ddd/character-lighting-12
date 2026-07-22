# 預設檔格式規格 v1

外掛與抽取腳本共同遵守的合約。**改這份規格 = 改外掛 = 改抽取腳本**，三者要一起動。

---

## 0. 核心概念：一切都相對於「參考尺寸」

每個預設不存絕對座標，存**相對於主體參考尺寸 `ref` 的比值**。

- 來源場景的 `ref_src` / `center_src` = **角色全身包圍盒**（depsgraph 求值後）的最大邊長與中心。
  以 `Linn_lighting_5.2.blend` 為準：`center_src = (0.2985, 0.1198, -3.0953)`、`ref_src = 11.5383`。
- 套用時的 `ref_dst` = 使用者光域的最大邊長。

> **為什麼用全身，不用相機視錐反推的半身**（2026-07-22 決定，推翻先前規劃）
>
> 原本打算用相機視錐反推「實際入鏡範圍」當分母，因為目錄圖看起來是半身像。
> 實測發現：**存在 5.2 檔裡的相機看到的是接近全身**（98.4% 的角色頂點在畫面內），
> 與目錄圖的半身構圖對不上——相機在當年算完圖之後被移動過。已用三種方法交叉驗證
> （解析 FOV 公式、`camera.angle_x/y`、實際算圖）。前提不成立，這條路作廢。
>
> 改用全身包圍盒，而且這其實更正確：**外掛在使用者那端量的是「選取的整個主體」，
> 抽取端就必須量同一件事，兩邊才對稱。** 使用者選整隻角色、分母就該是整隻角色。
>
> 這個決定可逆——原始 dump 保留在 `scratchpad/cl12/raw_52.json`，換分母重跑正規化即可。

**抽取時（除掉來源尺寸）**
```
normalized_pos    = (world_pos - center_src) / ref_src
normalized_energy = energy / ref_src²          # SUN 除外，見下表
normalized_dims   = dims / ref_src
```

**套用時（乘上目標尺寸）**
```
world_pos = domain_center + normalized_pos × ref_dst
energy    = normalized_energy × ref_dst²
```

> ⚠️ **`ref_src` 已經在抽取時除掉了，所以套用時的乘數就是 `ref_dst` 本身，不是兩者的比值。**
> 下表的 **k 一律代表 `ref_dst`**。（早期草稿寫成 `k = ref_dst / ref_src` 是錯的，會重複除一次。）

---

## 1. 縮放規則表（**這張表是整個外掛的物理核心，錯了就全錯**）

| 屬性 | 縮放方式 | 理由 |
|---|---|---|
| 位置 `pos` | `× k` | 距離等比 |
| 旋轉 `rot` | **不縮放** | 角度無量綱 |
| LIGHT `energy`（POINT/SPOT/AREA） | `× k²` | Blender 的 energy 是總功率(W)，照度 ∝ P/d²，距離放大 k 倍要補 k² |
| LIGHT `energy`（**SUN**） | **不縮放** | SUN 的 energy 是輻照度(W/m²)，與距離無關 |
| SUN 的 `pos` | **不套用**（存了也不用） | 平行光只有角度有意義 |
| LIGHT 形狀尺寸（area size / spot 半徑） | `× k` | 保持光源張角一致 |
| SPOT `spot_size` / `blend`、SUN `angle` | **不縮放** | 都是角度 |
| MESH `dims` | `× k` | 幾何等比 |
| MESH emission `strength` | **不縮放** | strength 是輻射率；面積×k² 與距離²×k² 對消，照度不變 |
| MESH volume `density` | `÷ k` | density 是每單位長度；霧變大 k 倍，光程也變 k 倍，要除掉 |

> 註：`energy × k²` 與 `strength 不變` 看似矛盾，其實一致——
> LIGHT 的 energy 是**總功率**（面積變大時功率要跟著補），
> mesh emission 的 strength 是**單位面積功率**（面積自己會變，不用補）。

---

## 2. 檔案配置

```
presets/
  01_simple_panel.json      # 簡單光板   ← 教學順序，不是原檔順序
  02_studio.json            # 一般棚燈
  ...
  12_retro.json             # 復古
  _order.json               # 顯示順序與分組
```

一個預設一個檔。使用者自訂預設寫到 Blender 使用者設定夾，**不動內建檔**。

---

## 3. 預設檔結構

```jsonc
{
  "schema": 1,
  "id": "beauty_ring",
  "name": { "en": "Beauty Ring", "zh": "網美" },
  "desc": {
    "en": "...",
    "zh": "環形燈正面打，陰影極淡、眼神光是完整的圓 —— 直播與美妝照的標準光。"
  },
  "tip": {
    "en": "...",
    "zh": "想讓臉更立體，把光域往上轉 15°，讓環形燈略高於視線。"
  },
  "engine_note": "volume",        // null | "volume" | "procedural" —— EEVEE 下會走鐘的原因，供面板提示用
  "world": { "color": [0,0,0], "strength": 1.0 },
  "objects": [ /* 見下 */ ]
}
```

### 3.1 LIGHT 物件

```jsonc
{
  "kind": "LIGHT",
  "role": "key",                  // key/fill/rim/bounce/practical —— 純標示，給教學提示用
  "name": "主光",
  "light_type": "AREA",           // POINT | SUN | SPOT | AREA
  "pos": [0.12, -1.34, 0.28],     // 已正規化
  "rot": [82.1, 0.0, 15.4],       // 度
  "color": [1.0, 0.87, 0.72],
  "energy": 145.2,                // 已正規化（= 原始 energy / ref_src²），SUN 則為原值
  "shape": {                      // 依 light_type 只出現對應欄位
    "size": 0.34,                 // AREA/POINT/SPOT 的半徑或邊長，已正規化
    "size_y": 0.12,               // AREA 且 shape=RECTANGLE 才有
    "area_shape": "RECTANGLE",    // SQUARE | RECTANGLE | DISK | ELLIPSE
    "spot_size": 45.0,            // 度，不縮放
    "spot_blend": 0.15,
    "sun_angle": 0.526            // 度，不縮放
  }
}
```

### 3.2 MESH 物件

```jsonc
{
  "kind": "MESH",
  "role": "bounce",
  "name": "面光",
  "primitive": "TORUS",           // PLANE | CUBE | CYLINDER | UV_SPHERE | TORUS
  "pos": [0.0, -0.92, 0.05],
  "rot": [90.0, 0.0, 0.0],
  "dims": [0.81, 0.16, 0.81],     // 見下方「dims 的定義」
  "primitive_args": { "major_ratio": 0.75 },   // TORUS 的環徑比等，選填
  "modifiers": [
    { "type": "ARRAY", "count": 50, "relative_offset": [0, 1.4, 0] }
  ],
  "visibility": {                 // 全部選填，預設 true
    "diffuse": false, "glossy": true, "camera": false,
    "transmission": true, "volume_scatter": true, "shadow": true
  },
  "material": { /* 見 3.3 */ }
}
```

#### `dims` 的定義（2026-07-22 更正，之前寫錯了）

`dims` = **物件的局部尺寸 ÷ ref_src**，也就是 Blender 的 `obj.dimensions`
（＝局部包圍盒 × scale），而且是**關掉所有修改器之後量的**。

**不是**世界空間的包圍盒。原因：

1. **`obj.dimensions` 完全不理會旋轉。** 它是局部包圍盒乘上 scale，不是世界對齊的包圍盒。
   拿世界包圍盒當目標、用逐軸 scale 去湊，只有在旋轉是 0°／180° 的倍數時才會對；
   物件一斜就靜默算錯。原檔 15 個 mesh 裡有 5 個是斜的（簡單光板的主光 46.7°、
   百葉窗的遮擋 −19.6°、漸層光板 3.9°、靈異底光 −19.0°、夕陽漸層球 136.7°）。
2. **修改器會改變 `dimensions` 的讀值。** 百葉窗有 Array ×50，量到的是 50 片的總長，
   拿它去對單片的目標尺寸是循環的。

builder 的 `apply_mesh_dimensions()` 會先關掉修改器再量，兩邊定義一致。

#### 第六種基本形：`QUAD`（明確四頂點）

```jsonc
{ "kind": "MESH", "primitive": "QUAD", "name": "遮擋",
  "pos": [...], "rot": [...],
  "verts": [[x,y,z], [x,y,z], [x,y,z], [x,y,z]],   // 已含原本的 scale，已 ÷ ref_src
  "modifiers": [ ... ] }
```

有 `verts` 就**不要**寫 `dims`（頂點座標已經是最終尺寸，物件 scale 保持 1）。
面的組成順序固定為 `(0, 1, 3, 2)`。

用途：形狀無法用「基本形 ＋ 逐軸縮放」表達的物件。目前只有百葉窗的葉片。

#### 百葉窗的葉片要用 `QUAD`，不能用 `PLANE` 也不能用 `CUBE`

原檔那片葉片是一條**細長薄帶**：4 個頂點，世界尺寸約 66.7 長 × 0.226 寬，
而且斜躺在局部 XY 對角線上。局部 Z 厚度 0.0396，Array 的 `relative_offset`
就是拿這個厚度當單位算間距的（−2.55 × 0.0396 × scale = 每片間隔 0.576）。

兩種錯誤做法都試過、都算圖確認過：

- **`PLANE`**：局部 Z 厚度是 0 → `relative_offset` 算出 0 位移，**50 片全疊在同一點**，
  沒有條紋，而且不報錯。
- **`CUBE`**：間距對了，但實心方塊有 16.9 的「深度」，太陽斜著打進來時葉片互相重疊
  把縫全堵死 → **整張圖幾乎全黑**。真正的薄帶只有 0.226 寬，不會堵。

所以百葉窗的遮擋物用 **`QUAD`**，直接存那 4 個頂點。

### 3.3 材質配方（**只用這六種，不做通用節點序列化**）

限定配方的理由：(a) 原檔 12 組只用到這些；(b) JSON 讀得懂 = 學生學得到；(c) 回寫容易。

```jsonc
// 1. 沒有材質（純幾何反光/遮擋板）
{ "recipe": "none" }

// 1b. Principled BSDF（不發光但要有質感的遮擋板／反光板）
//     百葉窗的葉片靠 alpha 讓一部分光透過去，條紋才不會死黑。
{ "recipe": "principled",
  "base_color": [0.8,0.8,0.8], "metallic": 0.0, "roughness": 0.5,
  "alpha": 0.724771, "transmission": 0.0, "ior": 1.5,
  "blend_method": "HASHED" }

// 2. 純色自發光
{ "recipe": "emission", "color": [1,0.95,0.9], "strength": 8.85 }

// 3. 體積霧
{ "recipe": "volume", "color": [1,1,1], "density": 0.002 }

// 4. 線性漸層自發光（Gradient Texture → ColorRamp →〔Bright/Contrast〕→ Emission）
{ "recipe": "gradient_emission",
  "gradient_type": "EASING",              // 照原檔實際值填，不要假設是 LINEAR
  "mapping": { "loc": [0,0,0], "rot": [0,0,0], "scale": [1,1,1],
               "vector_type": "NORMAL",   // POINT | TEXTURE | VECTOR | NORMAL
               "coord": "Object" },       // Texture Coordinate 的哪個輸出
  "ramp": { "interpolation": "EASE",
            "stops": [ {"pos":0.0,"color":[1,0.4,0.1,1]},
                       {"pos":1.0,"color":[0.1,0.1,0.4,1]} ] },
  "strength": 10.0 }

// 5. Magic Texture 漸層自發光（Magic → ColorRamp →〔Bright/Contrast〕→ Emission）
{ "recipe": "magic_emission",
  "magic": { "depth": 2, "scale": 0.5, "distortion": 1.0 },
  "mapping": { "loc": [0,0,0], "rot": [0,0,0], "scale": [1,1,1],
               "vector_type": "POINT", "coord": "Generated" },
  "ramp": { "interpolation": "LINEAR", "stops": [ ... ] },
  "bright_contrast": { "brightness": 0.0, "contrast": 0.2 },   // 選填
  "strength": 3.0 }
```

**`mapping.vector_type` 與 `mapping.coord` 一定要照原檔填，不能省略。**
原檔「漸層」的光板走的是 Object 座標 ＋ NORMAL 模式；若退回預設的 Generated/POINT，
漸層方向會整個跑掉——而那片板子是該組**唯一**的光源，錯了整組就毀了。

`bright_contrast` 是選填，只有原檔真的有這個節點時才寫（目前已知只有夕陽氛圍的漸層球有）。

**抽取腳本若遇到不符合這五種配方的材質 → 不要硬塞，回報「配方外」並附節點清單**，由人決定怎麼處理。

---

## 4. 使用者自訂預設

同格式，多兩個欄位，寫到使用者設定夾：

```jsonc
{ "schema": 1, "user": true, "base_id": "beauty_ring", ... }
```

外掛讀取順序：內建 → 使用者。同 `id` 時使用者版本蓋過內建版本（面板顯示「已修改」標記，附「還原內建」按鈕）。

---

## 5. 物件標記（回寫的基礎）

外掛生成的每個物件都蓋自訂屬性：

| 屬性 | 值 |
|---|---|
| `cl12_preset` | 預設 id，例如 `"beauty_ring"` |
| `cl12_role` | `role` 欄位的值 |
| `cl12_primitive` | MESH 才有，記錄原始基本形，回寫時不用猜 |

光域 Empty 蓋 `cl12_domain = True`、`cl12_ref`（=ref_dst）、`cl12_preset`。

**回寫規則**：掃光域底下所有帶 `cl12_preset` 的物件 → 反算正規化數值 → 寫 JSON。
使用者新加、沒有標記的物件：**LIGHT 與五種基本形照收**（自動補標記），其他型別跳警告不靜默略過。
