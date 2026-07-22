# SPDX-License-Identifier: GPL-3.0-or-later
"""修復 2026-07-22 那個 tuple 沒拆開造成的壞掉 modifiers 欄位。

症狀：`"modifiers": [[{...}], null]`（應該是 `[{...}]`），套用時崩潰：
      TypeError: list indices must be integers or slices, not str

只動 modifiers 這一個欄位，其他數值一律不碰。動手前整份備份。

跑法：
  python _dev/repair_user_presets.py           # 只檢查，不寫檔
  python _dev/repair_user_presets.py --write   # 備份後修復
"""

import json
import os
import shutil
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def user_dir():
    base = os.path.expandvars(
        r"%APPDATA%\Blender Foundation\Blender\5.2\config"
        r"\character_lighting_12\presets")
    return base


def unwrap(modifiers):
    """把 [[...], null] 還原成 [...]。回傳 (新值, 有沒有改)。"""
    if not isinstance(modifiers, list):
        return modifiers, False
    if all(isinstance(item, dict) for item in modifiers):
        return modifiers, False          # 本來就是好的
    # 壞掉的形狀：第一個元素才是真正的清單，第二個是警告訊息
    if modifiers and isinstance(modifiers[0], list):
        return modifiers[0], True
    return modifiers, False


def main():
    write = "--write" in sys.argv
    directory = user_dir()
    if not os.path.isdir(directory):
        print("找不到資料夾：%s" % directory)
        return 1

    files = sorted(name for name in os.listdir(directory)
                   if name.endswith(".json"))
    if write:
        backup = os.path.join(
            directory, "_backup_%s" % time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(backup, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(directory, name),
                         os.path.join(backup, name))
        print("已備份到 %s\n" % backup)

    total = 0
    for name in files:
        path = os.path.join(directory, name)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        fixed = []
        for spec in data.get("objects", []):
            if "modifiers" not in spec:
                continue
            new_value, changed = unwrap(spec["modifiers"])
            if not changed:
                continue
            if new_value:
                spec["modifiers"] = new_value
            else:
                del spec["modifiers"]     # 本來就沒有修改器
            fixed.append("%s(%d 個修改器)" % (spec.get("name", "?"), len(new_value)))

        if fixed:
            total += 1
            print("%-24s %s" % (name, "、".join(fixed)))
            if write:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
        else:
            print("%-24s 無須修復" % name)

    print("\n%d 個檔案%s修復" % (total, "已" if write else "需要"))
    if not write and total:
        print("確認無誤後加上 --write 真的寫入（會先備份）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
