# 現況與交接

> 更新：2026-07-22。若對話中斷，從這裡接。

## 一句話

**功能完成、全部測試通過、已推上 GitHub（private）。** 剩下的都是發佈流程。

## 完成度

| 項目 | 狀態 |
|---|---|
| 外掛程式碼（11 個 .py，約 3000 行） | ✅ |
| 12 組預設（阿哲調過的數值 ＋ 他寫的文案 ＋ 他做的封面） | ✅ |
| 自訂預設：新增／刪除／匯出／匯入 | ✅ |
| 預覽相機（重現原檔 1000mm 構圖） | ✅ |
| 範例資產（阿哲改過材質的版本，18.4 MB） | ✅ |
| README（雙語）／LICENSE／.gitignore | ✅ |
| `lint.py` 靜態檢查 | ✅ 11 個檔案 |
| `smoke_test.py` | ✅ 114 項 × 3.6/4.5/5.0/5.2 |
| `install_test.py`（真實安裝流程） | ✅ 17 項 × 四版本 |
| `acceptance.py`（12 組實跑＋算圖＋接觸表） | ✅ 50 項 |
| GitHub repo | ✅ zack3ddd/character-lighting-12（**private**） |
| 轉公開 | ⬜ 阿哲決定 |
| README 封面圖 | ⬜ 只能由阿哲在 GitHub 網頁拖檔 |
| Release | ⬜ zip 已備妥 |

## 發佈時要做的

1. **轉公開**：Settings → Danger Zone → Change visibility
2. **封面圖**：在 GitHub 網頁編輯 README.md，拖到第一行註解上方
3. **Release**：`CharacterLighting12.zip`，內文最下面放固定的安裝說明（見 memory
   `feedback-release-note-footer`），只換 README 網址
4. **版本號**：目前 `bl_info` 是 `(0, 1, 0)`。要當正式版發的話改成 `(1, 0, 0)`

## 怎麼跑各項工具

```bash
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
P="D:/Dropbox/Zack/03_品牌經營/名單磁鐵/免費插件/Character Lighting 12"

python "$P/_dev/lint.py"                                                 # 靜態檢查
"$BL" --background --factory-startup --python "$P/_dev/smoke_test.py"    # 單元測試
"$BL" --background --factory-startup --python "$P/_dev/install_test.py"  # 安裝測試
"$BL" --background --factory-startup --python "$P/_dev/acceptance.py"    # 驗收＋接觸表
python "$P/_dev/build_zip.py"                                            # 打包
python "$P/_dev/merge_copy.py" --write                                   # 灌文案
python "$P/_dev/merge_user_presets.py" --write                           # 收阿哲調的預設＋封面
python "$P/_dev/repair_user_presets.py" --write                          # 修壞掉的 modifiers（一次性）
```

安裝到阿哲的 Blender：把 `CharacterLighting12/` 複製到
`%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`，**Blender 要重開**。

## 重要脈絡（不要重新推導）

- **正規化基準** `ref_src = 11.538258`、`center_src = (0.29852, 0.119775, -3.095265)`，
  用全身包圍盒。相機從 2022 到現在**沒有被移動過**（中途一度誤判，已澄清）。
- **原始資料** `scratchpad/cl12/raw_52.json` ＋ `normalize.py`，換基準可即時重跑。
- **`active_preset` 與 `cl12_preview` 是兩件事**：前者是場景裡實際套用的，
  後者是縮圖牆上正在瀏覽的。翻縮圖不可以改到前者，否則「覆蓋」會蓋錯對象。
- 其餘決策與踩過的坑見 `PRESET_SPEC.md` 與 memory `project_character_lighting_12`。

## 已知的小事（不影響使用）

- 折行的內縮像素（34 / 52）與安全邊際（`ui.TEXT_SAFETY = 0.88`）是估的。
  若面板文字被截斷就調小 TEXT_SAFETY，若右邊留白太多就調大。
- 阿哲的封面是 361×490 直式，縮圖框是正方形，目前補黑邊置中不裁切。
