# SPDX-License-Identifier: GPL-3.0-or-later
"""靜態檢查：抓出「跑起來才會炸」的名稱錯誤。

跑法（不需要 Blender）：
  python _dev/lint.py

**為什麼需要這支**：面板的 `draw()` 只有在 Blender 真的畫介面時才會執行，
headless 測試從頭到尾不會碰它。所以 draw 裡面打錯的變數名，
單元測試、安裝測試、驗收測試**全部抓不到**——只有阿哲打開面板才會看到紅字。
2026-07-22 就是這樣漏掉一個 `_draw_step_adjust` 少收 context 參數的錯。

pyflakes 會把 Blender 的屬性宣告（`name: bpy.props.StringProperty(...)`）
誤判成型別註解，對中文字串狂噴假警報。這裡用 AST 找出那些宣告的行號範圍，
把落在範圍內的訊息濾掉，只留真正的問題。
"""

import ast
import os
import re
import subprocess
import sys

PACKAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "CharacterLighting12")

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

MESSAGE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<text>.+)$")

# 這些是 Blender 慣例造成的假警報，不是問題。
IGNORE_TEXT = (
    "imported but unused",
    "unable to detect undefined names",
)


def annotation_ranges(path):
    """回傳所有 `x: bpy.props.Foo(...)` 宣告佔用的行號集合。"""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        text = ast.get_source_segment(source, node) or ""
        # 兩種寫法都要認：`bpy.props.StringProperty(...)`，
        # 以及 `from bpy.props import StringProperty` 之後的 `StringProperty(...)`。
        if "bpy.props." not in text and not re.search(r"\b\w+Property\s*\(", text):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        lines.update(range(node.lineno, end + 1))
    return lines


def main():
    try:
        import pyflakes  # noqa: F401
    except ImportError:
        print("需要 pyflakes：pip install pyflakes")
        return 2

    # 路徑一律正規化——pyflakes 回報的字串要拿來當 key 比對，
    # 含 ".." 的相對路徑跟絕對路徑對不上，過濾就會整個失效。
    files = sorted(
        os.path.normcase(os.path.abspath(os.path.join(PACKAGE, name)))
        for name in os.listdir(PACKAGE) if name.endswith(".py")
    )
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes"] + files,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    # ⚠️ 用**檔名**當 key，不要用完整路徑。專案路徑含中文，而 pyflakes
    # 的輸出走系統編碼（Windows 是 cp950），解成 utf-8 後路徑會變亂碼，
    # 拿去比對永遠對不上，過濾就整個失效。檔名是純 ASCII，不受影響。
    skip = {os.path.basename(path): annotation_ranges(path) for path in files}
    problems = []

    for line in (result.stdout or "").splitlines():
        match = MESSAGE.match(line)
        if not match:
            continue
        text = match.group("text")
        if any(token in text for token in IGNORE_TEXT):
            continue
        name = os.path.basename(match.group("path").replace("\\", "/"))
        number = int(match.group("line"))
        if number in skip.get(name, set()):
            continue          # Blender 屬性宣告造成的假警報
        problems.append("%s:%d  %s" % (name, number, text))

    if problems:
        print("靜態檢查發現 %d 個問題：" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1

    print("靜態檢查通過（%d 個檔案）" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
