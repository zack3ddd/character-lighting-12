# SPDX-License-Identifier: GPL-3.0-or-later
"""打包成可安裝的 zip。

跑法（不需要 Blender）：
  python _dev/build_zip.py

產出 CharacterLighting12.zip 放在專案根目錄。
打包後會自己驗一次內容——曾經漏掉 LICENSE 過，靠 zip 大小異常才發現，
所以這裡改成明確檢查必要檔案，不靠肉眼。
"""

import os
import shutil
import sys
import zipfile

# Windows 終端機預設不是 UTF-8，不處理的話中文訊息會變亂碼。
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGE = "CharacterLighting12"
PACKAGE_DIR = os.path.join(ROOT, PACKAGE)
ZIP_PATH = os.path.join(ROOT, "%s.zip" % PACKAGE)

EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".blend1", ".DS_Store")

# 少了任何一項就不該出貨。
REQUIRED = [
    "%s/__init__.py" % PACKAGE,
    "%s/LICENSE" % PACKAGE,
    "%s/builder.py" % PACKAGE,
    "%s/presets.py" % PACKAGE,
    "%s/extract.py" % PACKAGE,
    "%s/ui.py" % PACKAGE,
]
REQUIRED_PRESETS = 12
REQUIRED_THUMBS = 12


def clean_pycache():
    removed = 0
    for current, dirs, _files in os.walk(PACKAGE_DIR):
        for name in list(dirs):
            if name in EXCLUDE_DIRS:
                shutil.rmtree(os.path.join(current, name), ignore_errors=True)
                dirs.remove(name)
                removed += 1
    return removed


def build():
    # LICENSE 放在專案根目錄，但安裝後使用者看到的是套件資料夾，所以複製一份進去。
    root_license = os.path.join(ROOT, "LICENSE")
    if os.path.exists(root_license):
        shutil.copy2(root_license, os.path.join(PACKAGE_DIR, "LICENSE"))

    cleaned = clean_pycache()
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    written = []
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for current, dirs, files in os.walk(PACKAGE_DIR):
            dirs[:] = [name for name in dirs if name not in EXCLUDE_DIRS]
            for filename in sorted(files):
                if filename.endswith(EXCLUDE_SUFFIX):
                    continue
                full = os.path.join(current, filename)
                arcname = os.path.relpath(full, ROOT).replace(os.sep, "/")
                archive.write(full, arcname)
                written.append(arcname)

    return cleaned, written


def verify(written):
    problems = []

    for required in REQUIRED:
        if required not in written:
            problems.append("缺少 %s" % required)

    presets = [name for name in written
               if name.startswith("%s/presets/" % PACKAGE) and name.endswith(".json")]
    presets = [name for name in presets if not os.path.basename(name).startswith("_")]
    if len(presets) != REQUIRED_PRESETS:
        problems.append("預設檔有 %d 個，應為 %d 個" % (len(presets), REQUIRED_PRESETS))

    thumbs = [name for name in written
              if name.startswith("%s/thumbnails/" % PACKAGE) and name.endswith(".png")]
    if len(thumbs) != REQUIRED_THUMBS:
        problems.append("縮圖有 %d 張，應為 %d 張" % (len(thumbs), REQUIRED_THUMBS))

    # 每個預設都要有對應檔名的縮圖，不然面板會出現空白格。
    thumb_ids = {os.path.splitext(os.path.basename(name))[0] for name in thumbs}
    for preset in presets:
        preset_id = os.path.splitext(os.path.basename(preset))[0]
        # 檔名是 NN_id.json，去掉數字前綴才是 id
        if "_" in preset_id and preset_id.split("_", 1)[0].isdigit():
            preset_id = preset_id.split("_", 1)[1]
        if preset_id not in thumb_ids:
            problems.append("預設 %s 找不到對應縮圖 %s.png" % (preset_id, preset_id))

    example = "%s/assets/example_subject.blend" % PACKAGE
    if example not in written:
        problems.append("缺少範例資產（載入範例按鈕會失效）")

    return problems


def main():
    cleaned, written = build()
    size = os.path.getsize(ZIP_PATH) / 1024.0 / 1024.0

    print("已打包：%s" % ZIP_PATH)
    print("  檔案數 %d，大小 %.2f MB，清掉 %d 個 __pycache__" % (len(written), size, cleaned))

    problems = verify(written)
    if problems:
        print("\n打包內容有問題，不要拿去發佈：")
        for problem in problems:
            print("  - %s" % problem)
        return 1

    print("  內容檢查通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
