# SPDX-License-Identifier: GPL-3.0-or-later
"""最終驗收：用真正的 12 組預設，在範例角色上跑完整流程並算圖。

跑法：
  "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" \
      --background --factory-startup --python _dev/acceptance.py

做四件事：
1. 檢查 12 個預設檔符合 PRESET_SPEC 的結構
2. 檢查範例資產已去識別化（不能出現 Linn）
3. 載入範例 → 建光域 → 逐一套用 12 組 → 每組算一張圖
4. 把 12 張圖拼成一張接觸表，給阿哲看 AgX 底下的實際樣子

算圖刻意用低取樣（校色看的是亮度與色調，不是雜訊），要出正式圖再自己拉高。
"""

import json
import os
import sys
import traceback

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGE_DIR = os.path.join(ROOT, "CharacterLighting12")
PRESET_DIR = os.path.join(PACKAGE_DIR, "presets")
OUT_DIR = os.path.join(ROOT, "_dev", "acceptance_out")
sys.path.insert(0, ROOT)

RESOLUTION = 512
SAMPLES = 64

FAILURES = []
CHECKS = [0]

VALID_RECIPES = {"none", "emission", "principled", "volume",
                 "gradient_emission", "magic_emission"}
VALID_PRIMITIVES = {"PLANE", "CUBE", "CYLINDER", "UV_SPHERE", "TORUS", "QUAD", "MESH"}
VALID_LIGHTS = {"POINT", "SUN", "SPOT", "AREA"}


def check(label, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        FAILURES.append("%s %s" % (label, detail))


# ---------------------------------------------------------------- 1. 預設結構

def validate_presets():
    print("\n=== 1. 預設檔結構 ===")
    files = sorted(
        name for name in os.listdir(PRESET_DIR)
        if name.endswith(".json") and not name.startswith("_")
    )
    check("預設檔有 12 個", len(files) == 12, "實得 %d" % len(files))

    seen_ids = set()
    for filename in files:
        with open(os.path.join(PRESET_DIR, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)

        label = filename
        ok = True
        problems = []

        if data.get("schema") != 1:
            ok = False
            problems.append("schema 不是 1")
        preset_id = data.get("id")
        if not preset_id:
            ok = False
            problems.append("沒有 id")
        elif preset_id in seen_ids:
            ok = False
            problems.append("id 重複")
        seen_ids.add(preset_id)

        # name 一定要雙語；desc/tip 允許還沒填（文案是阿哲要寫的），
        # 但只要不是空的就必須是雙語結構。
        name = data.get("name")
        if not isinstance(name, dict) or not name.get("zh") or not name.get("en"):
            ok = False
            problems.append("name 缺 zh 或 en")

        for field in ("desc", "tip"):
            value = data.get(field)
            if value in ("", None):
                continue
            if not isinstance(value, dict) or "zh" not in value or "en" not in value:
                ok = False
                problems.append("%s 有內容但不是 zh/en 結構" % field)

        objects = data.get("objects")
        if not isinstance(objects, list) or not objects:
            # 「漸層」那組沒有燈，但一定有一個發光 mesh，所以還是不能是空的
            ok = False
            problems.append("objects 是空的")
        else:
            for spec in objects:
                kind = spec.get("kind")
                if kind == "LIGHT":
                    if spec.get("light_type") not in VALID_LIGHTS:
                        ok = False
                        problems.append("燈型不合法：%s" % spec.get("light_type"))
                elif kind == "MESH":
                    if spec.get("primitive") not in VALID_PRIMITIVES:
                        ok = False
                        problems.append("基本形不合法：%s" % spec.get("primitive"))
                    recipe = (spec.get("material") or {}).get("recipe")
                    if recipe not in VALID_RECIPES:
                        ok = False
                        problems.append("材質配方不合法：%s" % recipe)
                else:
                    ok = False
                    problems.append("kind 不合法：%s" % kind)

                for field in ("pos", "rot"):
                    if len(spec.get(field) or []) != 3:
                        ok = False
                        problems.append("%s 不是三個數字" % field)

        check("結構合法 %s" % label, ok, "；".join(problems))

    # 縮圖對得上
    thumb_dir = os.path.join(PACKAGE_DIR, "thumbnails")
    thumbs = {os.path.splitext(name)[0] for name in os.listdir(thumb_dir)}
    missing = sorted(seen_ids - thumbs)
    check("每個預設都有對應縮圖", not missing, "缺：%s" % ", ".join(missing))
    return sorted(seen_ids)


# ---------------------------------------------------------------- 2. 去識別化

def validate_example():
    print("\n=== 2. 範例資產去識別化 ===")
    path = os.path.join(PACKAGE_DIR, "assets", "example_subject.blend")
    check("範例檔存在", os.path.exists(path))
    if not os.path.exists(path):
        return

    size = os.path.getsize(path) / 1024.0 / 1024.0
    check("範例檔大小合理（< 25 MB）", size < 25.0, "實際 %.1f MB" % size)

    # ⚠️ libraries.load 會把你指派給 target.objects 的那個 list 就地換成
    # 載入後的 Object 本體，所以名稱要另外抄一份出來，不能共用同一個 list。
    with bpy.data.libraries.load(path, link=False) as (source, target):
        names = [str(name) for name in source.objects]
        target.objects = list(source.objects)

    lowered = " ".join(names).lower()
    check("物件名稱不含 Linn", "linn" not in lowered, str(names))

    # 資料塊名稱也要乾淨（mesh / material / image）
    dirty = []
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                       bpy.data.objects, bpy.data.armatures):
        for item in collection:
            if "linn" in item.name.lower():
                dirty.append(item.name)
    check("資料塊名稱不含 Linn", not dirty, "、".join(sorted(set(dirty))[:6]))

    has_camera = any(obj and obj.type == "CAMERA" for obj in bpy.data.objects)
    has_mesh = any(obj and obj.type == "MESH" for obj in bpy.data.objects)
    check("範例含相機", has_camera)
    check("範例含角色 mesh", has_mesh)

    # 清掉，後面用 operator 正式載入
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


# ---------------------------------------------------------------- 3. 實跑 + 算圖

def render_all(preset_ids):
    print("\n=== 3. 逐組套用並算圖 ===")
    import CharacterLighting12 as addon
    from CharacterLighting12 import tags

    addon.register()
    os.makedirs(OUT_DIR, exist_ok=True)

    result = bpy.ops.cl12.load_example()
    check("載入範例成功", result == {"FINISHED"})

    domain = tags.find_domain(bpy.context)
    check("載入範例後自動建立了光域", domain is not None)
    if domain is None:
        return []

    settings = bpy.context.scene.cl12
    check("載入範例後自動開啟「隱藏原有燈光」", settings.hide_other_lights)
    check("載入範例後自動開啟「隱藏其他物件」", settings.hide_other_objects)
    subject = next((o for o in bpy.context.scene.objects
                    if o.type == "MESH" and tags.EXAMPLE in o), None)
    check("範例角色本身沒有被隱藏", subject is not None and not subject.hide_render)

    print("  光域尺寸 ref = %.4f" % float(domain[tags.DOMAIN_REF]))

    camera = next((obj for obj in bpy.context.scene.objects
                   if obj.type == "CAMERA" and tags.EXAMPLE in obj), None)
    if camera is not None:
        bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    # 這正是阿哲要看的重點：4.x 的預設色彩管理是 AgX，不是原檔的 Filmic。
    scene.view_settings.view_transform = "AgX"

    rendered = []
    for preset_id in preset_ids:
        try:
            result = bpy.ops.cl12.apply_preset(preset_id=preset_id)
        except RuntimeError as error:
            check("套用 %s" % preset_id, False, str(error))
            continue
        check("套用 %s" % preset_id, result == {"FINISHED"})

        path = os.path.join(OUT_DIR, "%s.png" % preset_id)
        scene.render.filepath = path
        try:
            bpy.ops.render.render(write_still=True)
        except RuntimeError as error:
            check("算圖 %s" % preset_id, False, str(error))
            continue
        check("算圖 %s" % preset_id, os.path.exists(path))
        rendered.append((preset_id, path))

    addon.unregister()
    return rendered


# ---------------------------------------------------------------- 4. 接觸表

def contact_sheet(rendered):
    print("\n=== 4. 接觸表 ===")
    if not rendered:
        check("有圖可以拼", False)
        return

    columns = 4
    rows = (len(rendered) + columns - 1) // columns
    width, height = RESOLUTION * columns, RESOLUTION * rows

    sheet = bpy.data.images.new("contact_sheet", width, height, alpha=False)
    canvas = [0.0] * (width * height * 4)

    for index, (preset_id, path) in enumerate(rendered):
        image = bpy.data.images.load(path)
        pixels = list(image.pixels)
        column, row = index % columns, index // columns
        # Blender 的像素原點在左下，所以 row 要反過來排。
        offset_x = column * RESOLUTION
        offset_y = (rows - 1 - row) * RESOLUTION

        for y in range(RESOLUTION):
            source = y * RESOLUTION * 4
            target = ((offset_y + y) * width + offset_x) * 4
            canvas[target:target + RESOLUTION * 4] = \
                pixels[source:source + RESOLUTION * 4]
        bpy.data.images.remove(image)

    sheet.pixels = canvas
    out = os.path.join(OUT_DIR, "_contact_sheet.png")
    sheet.filepath_raw = out
    sheet.file_format = "PNG"
    sheet.save()
    check("接觸表產出", os.path.exists(out))
    print("  → %s" % out)


def main():
    preset_ids = validate_presets()
    validate_example()
    rendered = render_all(preset_ids)
    contact_sheet(rendered)


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
