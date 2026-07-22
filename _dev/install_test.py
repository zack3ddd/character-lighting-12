# SPDX-License-Identifier: GPL-3.0-or-later
"""用 Blender 真正的外掛安裝流程測一次。

前面的 smoke_test 是把套件加到 sys.path 直接 import，那跟 Blender 自己的
外掛載入器不是同一條路——bl_info 解析、相對匯入、previews 註冊時機都可能只在
真安裝時才出問題。這支從 zip 安裝、啟用、跑一次、再停用。

跑法（由 run_install_test.sh 帶環境變數呼叫，不要直接跑）：
  blender --background --factory-startup --python _dev/install_test.py
"""

import os
import sys
import traceback

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZIP_PATH = os.path.join(ROOT, "CharacterLighting12.zip")
MODULE = "CharacterLighting12"

FAILURES = []
CHECKS = [0]


def check(label, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        FAILURES.append("%s %s" % (label, detail))


def main():
    print("=== 從 zip 安裝 ===")
    check("zip 存在", os.path.exists(ZIP_PATH), ZIP_PATH)
    if not os.path.exists(ZIP_PATH):
        return

    bpy.ops.preferences.addon_install(filepath=ZIP_PATH, overwrite=True)
    check("addon_install 沒有丟例外", True)

    print("\n=== 啟用 ===")
    bpy.ops.preferences.addon_enable(module=MODULE)
    enabled = MODULE in bpy.context.preferences.addons
    check("外掛已啟用", enabled)
    if not enabled:
        return

    check("Scene.cl12 存在", hasattr(bpy.types.Scene, "cl12"))
    check("Scene.cl12_preview 存在", hasattr(bpy.types.Scene, "cl12_preview"))

    print("\n=== 面板有註冊 ===")
    panels = [cls.__name__ for cls in bpy.types.Panel.__subclasses__()
              if cls.__name__.startswith("CL12_PT")]
    check("N 面板有註冊", bool(panels), str(panels))

    print("\n=== 預設與縮圖讀得到 ===")
    module = sys.modules.get(MODULE)
    presets = getattr(module, "presets", None)
    check("presets 模組載入", presets is not None)
    if presets:
        loaded = presets.load_all(force=True)
        check("讀到 12 組預設", len(loaded) == 12, "實得 %d" % len(loaded))
        empty_copy = [
            data["id"] for data in loaded.values()
            if not presets.localized(data, "desc", "zh")
        ]
        # 文案還沒填是預期的，只是提醒，不算失敗。
        print("  註：尚未填文案的預設 %d 組" % len(empty_copy))

    # 動態 EnumProperty 的 enum_items 是空的（要跑 callback 才有內容），
    # 所以直接呼叫 callback 本人來驗。
    previews = getattr(module, "previews", None)
    check("previews 模組載入", previews is not None)
    if previews:
        items = previews.preset_items(None, bpy.context)
        check("縮圖列舉有 12 項", len(items) == 12, "實得 %d" % len(items))

        # 縮圖 PNG 有沒有真的隨 zip 裝到位——這是 headless 驗得了的部分。
        thumb_dir = os.path.join(os.path.dirname(module.__file__), "thumbnails")
        missing = [item[0] for item in items
                   if not os.path.exists(os.path.join(thumb_dir, "%s.png" % item[0]))]
        check("12 張縮圖檔都有裝到位", not missing,
              "缺：%s（找的位置 %s）" % (", ".join(missing), thumb_dir))

        # ⚠️ icon_id 在 --background 下一定是 0（沒有 UI 就不產生預覽圖示），
        # 所以這裡只印出來當參考，不當作失敗。要確認縮圖牆真的有圖，
        # 只能開 GUI 看 N 面板。
        no_icon = [item[0] for item in items if item[3] == 0]
        print("  註：icon_id 為 0 的有 %d 項（background 模式下屬正常）" % len(no_icon))

    print("\n=== 跑一次完整流程 ===")
    bpy.ops.mesh.primitive_monkey_add(size=2.0, location=(0, 0, 0))
    subject = bpy.context.object
    subject.select_set(True)
    bpy.context.view_layer.objects.active = subject

    result = bpy.ops.cl12.create_domain()
    check("建立光域", result == {"FINISHED"})

    applied = 0
    for preset_id in sorted(presets.load_all().keys()):
        try:
            if bpy.ops.cl12.apply_preset(preset_id=preset_id) == {"FINISHED"}:
                applied += 1
        except RuntimeError as error:
            check("套用 %s" % preset_id, False, str(error))
    check("12 組都套用成功", applied == 12, "實得 %d" % applied)

    result = bpy.ops.cl12.save_preset()
    check("回寫成功", result == {"FINISHED"})

    result = bpy.ops.cl12.clear_lights()
    check("清除成功", result == {"FINISHED"})

    print("\n=== 停用 ===")
    bpy.ops.preferences.addon_disable(module=MODULE)
    check("停用沒有丟例外", MODULE not in bpy.context.preferences.addons)
    check("停用後屬性有清乾淨", not hasattr(bpy.types.Scene, "cl12"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        FAILURES.append("未捕捉的例外（見上方 traceback）")

    print("\n" + "=" * 56)
    print("共 %d 項檢查，失敗 %d 項" % (CHECKS[0], len(FAILURES)))
    for failure in FAILURES:
        print("  - %s" % failure)
    print("=" * 56)
    sys.exit(1 if FAILURES else 0)
