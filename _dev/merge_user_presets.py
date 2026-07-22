# SPDX-License-Identifier: GPL-3.0-or-later
"""把阿哲調好的使用者預設合併回內建預設，並用他自己做的封面取代縮圖。

跑法：
  python _dev/merge_user_presets.py           # 預覽
  python _dev/merge_user_presets.py --write   # 寫入（會先備份內建預設）

合併規則：**燈光數值以使用者版本為準，文字欄位以內建版本為準**。
使用者版本的 name/desc/tip 是空的（文案還沒寫），直接蓋過去會把教學文案洗掉。
"""

import json
import os
import shutil
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILTIN = os.path.join(ROOT, "CharacterLighting12", "presets")
THUMBS = os.path.join(ROOT, "CharacterLighting12", "thumbnails")
COVERS = os.path.join(ROOT, "封面圖")
USER = os.path.expandvars(
    r"%APPDATA%\Blender Foundation\Blender\5.2\config"
    r"\character_lighting_12\presets")

# 阿哲的封面檔名 → 預設 id。檔名有兩個錯字（未来感、簡單光版），
# 照他的檔名寫，不改他的檔案。
COVER_MAP = {
    "簡單光版": "simple_panel",
    "一般棚燈": "studio",
    "天使光": "angel_light",
    "網美": "beauty_ring",
    "網紅": "influencer",
    "憂鬱": "melancholy",
    "靈異": "eerie",
    "百葉窗": "blinds",
    "夕陽氛圍": "sunset_mood",
    "未来感": "futuristic",
    "漸層": "gradient",
    "復古": "retro",
}

THUMB_SIZE = 256

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def merge_presets(write):
    files = sorted(name for name in os.listdir(BUILTIN)
                   if name.endswith(".json") and not name.startswith("_"))
    if write:
        backup = os.path.join(ROOT, "_dev",
                              "presets_backup_%s" % time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(backup, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(BUILTIN, name), os.path.join(backup, name))
        print("內建預設已備份到 %s\n" % os.path.basename(backup))

    merged = 0
    for name in files:
        builtin_path = os.path.join(BUILTIN, name)
        user_path = os.path.join(USER, name)
        if not os.path.exists(user_path):
            print("  %-24s 使用者沒有調整過，保持原樣" % name)
            continue

        with open(builtin_path, "r", encoding="utf-8") as handle:
            builtin = json.load(handle)
        with open(user_path, "r", encoding="utf-8") as handle:
            user = json.load(handle)

        # 數值走使用者版本，文字走內建版本。
        builtin["objects"] = user.get("objects", builtin.get("objects"))
        if "world" in user:
            builtin["world"] = user["world"]

        recipes = sorted({(spec.get("material") or {}).get("recipe")
                          for spec in builtin["objects"]
                          if spec["kind"] == "MESH"} - {None})
        print("  %-24s %2d 物件  材質配方: %s"
              % (name, len(builtin["objects"]), "、".join(recipes) or "—"))
        merged += 1

        if write:
            with open(builtin_path, "w", encoding="utf-8") as handle:
                json.dump(builtin, handle, ensure_ascii=False, indent=2)

    print("\n%d 個預設%s合併" % (merged, "已" if write else "會被"))
    return merged


def convert_covers(write):
    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow：pip install pillow")
        return 0

    if not os.path.isdir(COVERS):
        print("找不到封面圖資料夾")
        return 0

    done = 0
    for filename in sorted(os.listdir(COVERS)):
        stem = os.path.splitext(filename)[0]
        preset_id = COVER_MAP.get(stem)
        if preset_id is None:
            print("  !! %s 對不到任何預設，跳過" % filename)
            continue

        source = Image.open(os.path.join(COVERS, filename)).convert("RGB")
        # 封面是直式的，縮圖框是正方形。直接縮會被拉扁，
        # 所以先補成正方形（左右加黑邊）再縮，保住阿哲的構圖。
        side = max(source.size)
        canvas = Image.new("RGB", (side, side), (0, 0, 0))
        canvas.paste(source, ((side - source.width) // 2,
                             (side - source.height) // 2))
        canvas = canvas.resize((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)

        target = os.path.join(THUMBS, "%s.png" % preset_id)
        print("  %-16s → %s.png  (%dx%d → %d²)"
              % (stem, preset_id, source.width, source.height, THUMB_SIZE))
        if write:
            canvas.save(target)
        done += 1

    missing = set(COVER_MAP.values()) - {
        COVER_MAP.get(os.path.splitext(f)[0]) for f in os.listdir(COVERS)}
    if missing:
        print("  !! 沒有封面的預設：%s" % "、".join(sorted(missing)))
    return done


def main():
    write = "--write" in sys.argv
    print("=== 合併預設 ===")
    merge_presets(write)
    print("\n=== 轉換封面 ===")
    count = convert_covers(write)
    print("\n%d 張封面%s套用" % (count, "已" if write else "會被"))
    if not write:
        print("\n確認無誤後加上 --write 真的寫入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
