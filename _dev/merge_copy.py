# SPDX-License-Identifier: GPL-3.0-or-later
"""把 文案草稿.md 裡的 desc / tip 灌進 12 個預設檔。

跑法（不需要 Blender）：
  python _dev/merge_copy.py            # 預覽會改什麼，不寫檔
  python _dev/merge_copy.py --write    # 真的寫入

阿哲改完 文案草稿.md 之後跑這支，不要手動一個一個貼——
手貼 48 段字一定會貼錯，而且改了之後又要再貼一次。
草稿檔的格式就是唯一來源，預設檔的 desc/tip 由它產生。
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRAFT = os.path.join(ROOT, "_dev", "文案草稿.md")
PRESET_DIR = os.path.join(ROOT, "CharacterLighting12", "presets")

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

# 章節標題長這樣：## 04 網美 Beauty Ring
HEADING = re.compile(r"^##\s+(\d{2})\s+(\S+)\s+(.+?)\s*$")
FIELDS = {
    "**desc**": ("desc", "zh"),
    "**tip**": ("tip", "zh"),
    "*en desc*": ("desc", "en"),
    "*en tip*": ("tip", "en"),
}


def parse_draft():
    """回傳 {order: {"zh_name":..., "en_name":..., "desc":{...}, "tip":{...}}}"""
    sections = {}
    current = None

    with open(DRAFT, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            heading = HEADING.match(line)
            if heading:
                order, zh_name, en_name = heading.groups()
                current = {
                    "zh_name": zh_name, "en_name": en_name,
                    "desc": {}, "tip": {},
                }
                sections[order] = current
                continue

            if current is None or ":" not in line and "：" not in line:
                continue

            for marker, (field, language) in FIELDS.items():
                if line.startswith(marker):
                    text = line[len(marker):].lstrip("：: ").strip()
                    if text:
                        current[field][language] = text
                    break

    return sections


def main():
    write = "--write" in sys.argv

    if not os.path.exists(DRAFT):
        print("找不到草稿檔：%s" % DRAFT)
        return 1

    sections = parse_draft()
    print("草稿讀到 %d 組" % len(sections))

    files = sorted(
        name for name in os.listdir(PRESET_DIR)
        if name.endswith(".json") and not name.startswith("_")
    )
    if not files:
        print("presets/ 裡沒有預設檔，先把 12 組抽出來再跑這支。")
        return 1

    changed = 0
    problems = []

    for filename in files:
        order = filename.split("_", 1)[0]
        section = sections.get(order)
        path = os.path.join(PRESET_DIR, filename)

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        if section is None:
            problems.append("%s 在草稿裡找不到對應的 %s 章節" % (filename, order))
            continue

        # 順手核對名稱有沒有對錯——草稿的順序跟檔名對不上是很容易犯的錯。
        existing_zh = (data.get("name") or {}).get("zh", "")
        if existing_zh and existing_zh != section["zh_name"]:
            problems.append(
                "%s 的名稱是「%s」，草稿第 %s 節寫的是「%s」——順序可能對錯了"
                % (filename, existing_zh, order, section["zh_name"])
            )
            continue

        before = json.dumps(data.get("desc")) + json.dumps(data.get("tip"))
        for field in ("desc", "tip"):
            text = section[field]
            if text.get("zh") or text.get("en"):
                data[field] = {"en": text.get("en", ""), "zh": text.get("zh", "")}
        after = json.dumps(data.get("desc")) + json.dumps(data.get("tip"))

        if before != after:
            changed += 1
            print("  %s ← %s" % (filename, section["zh_name"]))
            if write:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)

    print("\n%d 個檔案%s更新" % (changed, "已" if write else "會被"))
    for problem in problems:
        print("  ⚠ %s" % problem)
    if not write and changed:
        print("確認無誤後加上 --write 真的寫入。")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
