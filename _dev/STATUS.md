# 現況與交接

> 更新：2026-07-22 凌晨。若對話中斷，從這裡接。

## 一句話

**外掛功能完成、全部測試通過、zip 打包好了。** 剩下的都是要阿哲決定的事（文案、校色）。

## 完成度

| 項目 | 狀態 |
|---|---|
| 外掛程式碼（11 個 .py） | ✅ 完成 |
| 12 個預設 JSON | ✅ 完成（百葉窗已改 QUAD 並算圖驗證） |
| 12 張縮圖 | ✅ 完成（檔名已對上 preset id） |
| 範例資產 example_subject.blend | ✅ 14.8MB，已獨立驗證去識別化 |
| README（雙語）／LICENSE／.gitignore | ✅ 完成 |
| `smoke_test.py` | ✅ 64 項，3.6/4.5/5.0/5.2 皆綠 |
| `acceptance.py` | ✅ 47 項全過，12 組都算得出圖 |
| `install_test.py`（真實安裝流程） | ✅ 17 項，四版本皆綠 |
| `CharacterLighting12.zip` | ✅ 15.54 MB，內容檢查通過 |
| desc/tip 文案 | ⬜ 草稿在 `文案草稿.md`，等阿哲改 |
| GitHub repo／Release | ⬜ 等阿哲確認命名後再開 |

## 給阿哲的驗收物

- **接觸表**：`_dev/acceptance_out/_contact_sheet.png`（AgX 底下的 12 組，4×3）
  順序（字母序）：天使光·網美·百葉窗·靈異／未來感·漸層·網紅·憂鬱／復古·簡單光板·一般棚燈·夕陽氛圍
- 單張大圖同資料夾，檔名就是 preset id
- **百葉窗對照組**：`D:\Temp\claude\...\scratchpad\ref_blinds.png`（從原檔直接算的真值）

## 怎麼跑各項工具

```bash
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
P="D:/Dropbox/Zack/03_品牌經營/名單磁鐵/免費插件/Character Lighting 12"

"$BL" --background --factory-startup --python "$P/_dev/smoke_test.py"    # 單元測試
"$BL" --background --factory-startup --python "$P/_dev/acceptance.py"    # 驗收＋接觸表
python "$P/_dev/build_zip.py"                                            # 打包
python "$P/_dev/merge_copy.py"                                           # 灌文案（--write 才寫入）
```

## 重要脈絡（不要重新推導）

- **正規化基準** `ref_src = 11.538258`、`center_src = (0.29852, 0.119775, -3.095265)`，
  用全身包圍盒。相機**從來沒被移動過**，構圖也確實吻合目錄圖（已算圖比對確認）。
- **原始資料** `D:\Temp\claude\...\scratchpad\cl12\raw_52.json` ＋ `normalize.py`，
  換基準或改 role 可即時重跑，不用再開 Blender 抽一次。
- 其餘決策與踩過的坑見 `PRESET_SPEC.md` 與 memory `project_character_lighting_12.md`。
