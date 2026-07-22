# SPDX-License-Identifier: GPL-3.0-or-later
"""外掛煙霧測試：註冊 → 建光域 → 套用 → 回寫 → 比對。

跑法：
  "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" \
      --background --factory-startup --python _dev/smoke_test.py

不依賴真正的 12 個預設檔（那些還在產出中），改用一份合成預設，
但**涵蓋所有五種材質配方、四種燈型、Array modifier 與 ray visibility**——
真正的預設用到的功能都在這裡面了。
"""

import json
import os
import sys
import traceback

import bpy

ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ADDON_ROOT)

FAILURES = []
CHECKS = [0]


def check(label, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        FAILURES.append("%s %s" % (label, detail))


def close(label, actual, expected, tolerance=1e-4):
    if hasattr(actual, "__len__") and hasattr(expected, "__len__"):
        worst = max(abs(a - b) for a, b in zip(actual, expected))
    else:
        worst = abs(actual - expected)
    check(label, worst <= tolerance, "差 %.6g（容差 %.6g）" % (worst, tolerance))


SYNTHETIC = {
    "schema": 1,
    "id": "smoke_test",
    "name": {"en": "Smoke", "zh": "煙霧測試"},
    "desc": {"en": "", "zh": ""},
    "tip": {"en": "", "zh": ""},
    "engine_note": "volume",
    "world": {"color": [0.0, 0.0, 0.0], "strength": 1.0},
    "objects": [
        {"kind": "LIGHT", "role": "key", "name": "key_area", "light_type": "AREA",
         "pos": [0.8, -1.2, 0.5], "rot": [60.0, 0.0, 30.0],
         "color": [1.0, 0.9, 0.8], "energy": 12.5,
         "shape": {"area_shape": "RECTANGLE", "size": 0.4, "size_y": 0.25}},
        {"kind": "LIGHT", "role": "rim", "name": "rim_spot", "light_type": "SPOT",
         "pos": [-1.0, 1.4, 0.9], "rot": [-40.0, 10.0, 0.0],
         "color": [0.6, 0.7, 1.0], "energy": 30.0,
         "shape": {"size": 0.1, "spot_size": 45.0, "spot_blend": 0.2}},
        {"kind": "LIGHT", "role": "fill", "name": "fill_point", "light_type": "POINT",
         "pos": [1.5, 0.2, -0.3], "rot": [0.0, 0.0, 0.0],
         "color": [1.0, 1.0, 1.0], "energy": 4.0,
         "shape": {"size": 0.2}},
        {"kind": "LIGHT", "role": "practical", "name": "sun", "light_type": "SUN",
         "pos": [0.0, 0.0, 3.0], "rot": [50.0, 0.0, 120.0],
         "color": [1.0, 0.95, 0.9], "energy": 3.0,
         "shape": {"sun_angle": 1.5}},

        {"kind": "MESH", "role": "bounce", "name": "plain_plane", "primitive": "PLANE",
         "pos": [0.0, 1.0, 0.0], "rot": [90.0, 0.0, 0.0], "dims": [2.0, 2.0, 0.0],
         "material": {"recipe": "none"}},
        {"kind": "MESH", "role": "key", "name": "emit_torus", "primitive": "TORUS",
         "pos": [0.0, -1.5, 0.2], "rot": [90.0, 0.0, 0.0], "dims": [1.6, 0.3, 1.6],
         "primitive_args": {"major_ratio": 0.2},
         "material": {"recipe": "emission", "color": [1.0, 0.95, 0.9], "strength": 8.85}},
        {"kind": "MESH", "role": "practical", "name": "fog", "primitive": "CUBE",
         "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "dims": [3.0, 3.0, 3.0],
         "material": {"recipe": "volume", "color": [1.0, 1.0, 1.0], "density": 0.002}},
        {"kind": "MESH", "role": "key", "name": "grad_panel", "primitive": "PLANE",
         "pos": [0.0, -2.5, 0.0], "rot": [90.0, 0.0, 0.0], "dims": [8.0, 8.0, 0.0],
         "material": {"recipe": "gradient_emission", "gradient_type": "EASING",
                      "mapping": {"loc": [0, 0, 0], "rot": [0, 0, 45.0], "scale": [1, 1, 1],
                                  "vector_type": "NORMAL", "coord": "Object"},
                      "ramp": {"interpolation": "EASE",
                               "stops": [{"pos": 0.0, "color": [1.0, 0.4, 0.1, 1.0]},
                                         {"pos": 0.5, "color": [0.5, 0.3, 0.6, 1.0]},
                                         {"pos": 1.0, "color": [0.1, 0.1, 0.4, 1.0]}]},
                      "strength": 10.0}},
        {"kind": "MESH", "role": "bounce", "name": "magic_dome", "primitive": "UV_SPHERE",
         "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "dims": [9.0, 9.0, 4.5],
         "visibility": {"diffuse": False, "camera": False, "glossy": True},
         "material": {"recipe": "magic_emission",
                      "magic": {"depth": 3, "scale": 4.5, "distortion": 1.2},
                      "mapping": {"loc": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
                      "ramp": {"interpolation": "LINEAR",
                               "stops": [{"pos": 0.1, "color": [1.0, 0.6, 0.2, 1.0]},
                                         {"pos": 0.9, "color": [0.2, 0.3, 0.8, 1.0]}]},
                      "bright_contrast": {"brightness": 0.0, "contrast": 0.2},
                      "strength": 3.0}},
        # 百葉窗的葉片必須是有厚度的薄立方體，不能是平面——
        # Array 的 relative_offset 是拿該軸的尺寸當單位，平面的厚度是 0，
        # 50 片會全部疊在同一點且不報錯。這組專門在測那個坑。
        {"kind": "MESH", "role": "practical", "name": "blinds", "primitive": "CUBE",
         "pos": [0.0, 2.0, 0.0], "rot": [90.0, 0.0, -19.6], "dims": [0.4, 2.0, 0.02],
         "modifiers": [{"type": "ARRAY", "count": 12,
                        "relative_offset": [0.0, 0.0, -2.55]}],
         "material": {"recipe": "emission", "color": [0.0, 0.0, 0.0], "strength": 0.0}},
    ],
}


REAL_PRESETS = None
BEFORE = {}


def real_snapshot(directory):
    """{檔名: (大小, 修改時間)}。用來確認測試沒有動到使用者的真實資料。"""
    if not directory or not os.path.isdir(directory):
        return {}
    snapshot = {}
    for name in os.listdir(directory):
        if not name.endswith(".json"):
            continue
        full = os.path.join(directory, name)
        info = os.stat(full)
        snapshot[name] = (info.st_size, info.st_mtime_ns)
    return snapshot


def isolate_user_data(presets):
    """把測試的讀寫全部導到暫存區。

    ⚠️ **這一段是為了保護使用者的資料，不是可有可無的整潔。**
    `presets.user_dir()` 走的是 `bpy.utils.user_resource("CONFIG")`，
    就算加了 `--factory-startup` 也還是指向真實的 AppData 設定夾。
    2026-07-22 因此出過事：測試把合成燈光存成了阿哲的「簡單光板」使用者版本，
    他打開 Blender 看到的是測試資料。

    用環境變數隔離不夠可靠——那要記得每次都加。直接改掉函式，
    不管誰用什麼方式啟動測試都碰不到真實資料。
    """
    sandbox = os.path.join(bpy.app.tempdir, "cl12_test_config")
    presets_dir = os.path.join(sandbox, "presets")
    cache_dir = os.path.join(sandbox, "thumb_cache")
    for path in (presets_dir, cache_dir):
        os.makedirs(path, exist_ok=True)
        for stale in os.listdir(path):
            try:
                os.remove(os.path.join(path, stale))
            except OSError:
                pass

    presets.user_dir = lambda: presets_dir
    presets.thumb_cache_dir = lambda: cache_dir
    presets.invalidate()
    return presets_dir


def main():
    from CharacterLighting12 import builder, extract, presets, tags  # noqa: F401
    import CharacterLighting12 as addon

    global REAL_PRESETS, BEFORE
    real = bpy.utils.user_resource("CONFIG", path="character_lighting_12")
    REAL_PRESETS = os.path.join(real, "presets")
    BEFORE = real_snapshot(REAL_PRESETS)

    sandbox = isolate_user_data(presets)
    check("測試資料已隔離到暫存區", sandbox.startswith(bpy.app.tempdir), sandbox)
    check("沒有指向真實設定夾", not sandbox.startswith(real), real)

    print("\n=== 1. 註冊 ===")
    addon.register()
    check("register() 沒有丟例外", True)
    check("Scene.cl12 存在", hasattr(bpy.types.Scene, "cl12"))
    check("Scene.cl12_preview 存在", hasattr(bpy.types.Scene, "cl12_preview"))

    print("\n=== 2. 寫入合成預設 ===")
    path = os.path.join(presets.user_dir(), "zz_smoke_test.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(SYNTHETIC, handle, ensure_ascii=False, indent=2)
    presets.invalidate()
    check("合成預設讀得回來", presets.get("smoke_test") is not None)

    print("\n=== 3. 建立光域 ===")
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(1.0, 2.0, 3.0))
    subject = bpy.context.object
    subject.name = "TestSubject"
    subject.scale = (1.0, 1.0, 2.5)          # 讓最大邊長是 Z = 10
    bpy.context.view_layer.update()

    subject.select_set(True)
    bpy.context.view_layer.objects.active = subject
    result = bpy.ops.cl12.create_domain()
    check("create_domain 回傳 FINISHED", result == {"FINISHED"})

    domain = tags.find_domain(bpy.context)
    check("找得到光域", domain is not None)
    ref = float(domain[tags.DOMAIN_REF])
    close("光域 ref = 主體最大邊長", ref, 5.0, 1e-3)
    close("光域中心 = 主體中心", list(domain.location), [1.0, 2.0, 3.0], 1e-3)

    print("\n=== 4. 套用預設 ===")
    result = bpy.ops.cl12.apply_preset(preset_id="smoke_test")
    check("apply_preset 回傳 FINISHED", result == {"FINISHED"})

    children = tags.domain_children(domain)
    check("生成的物件數正確", len(children) == len(SYNTHETIC["objects"]),
          "實得 %d，應為 %d" % (len(children), len(SYNTHETIC["objects"])))

    by_name = {obj.name: obj for obj in children}

    key = by_name.get("key_area")
    if key:
        close("AREA energy 套 ref²", key.data.energy, 12.5 * ref ** 2, 1e-2)
        close("AREA size 套 ref", key.data.size, 0.4 * ref, 1e-3)
        close("AREA size_y 套 ref", key.data.size_y, 0.25 * ref, 1e-3)
        expected = [1.0 + 0.8 * ref, 2.0 + -1.2 * ref, 3.0 + 0.5 * ref]
        close("AREA 世界座標 = 中心 + pos×ref", list(key.matrix_world.translation),
              expected, 1e-3)
    else:
        check("key_area 存在", False)

    sun = by_name.get("sun")
    if sun:
        close("SUN energy 不縮放", sun.data.energy, 3.0, 1e-4)
    else:
        check("sun 存在", False)

    fog = by_name.get("fog")
    if fog:
        node = next((n for n in fog.data.materials[0].node_tree.nodes
                     if n.bl_idname == "ShaderNodeVolumePrincipled"), None)
        check("霧有 Principled Volume", node is not None)
        if node:
            close("volume density 除以 ref", node.inputs["Density"].default_value,
                  0.002 / ref, 1e-9)
    else:
        check("fog 存在", False)

    dome = by_name.get("magic_dome")
    if dome:
        check("dome 對 diffuse 不可見", dome.visible_diffuse is False)
        check("dome 對 glossy 可見", dome.visible_glossy is True)
        check("dome 對相機不可見", dome.visible_camera is False)
    else:
        check("magic_dome 存在", False)

    blinds = by_name.get("blinds")
    if blinds:
        modifier = blinds.modifiers.get("Array")
        check("百葉窗有 Array modifier", modifier is not None)
        if modifier:
            check("Array count 正確", modifier.count == 12)

        # 關鍵回歸測試：葉片必須真的散開。
        # 若基礎形沒有厚度，12 片會疊在同一點——畫面上沒有條紋，但不會報錯。
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = blinds.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        world_z = [(evaluated.matrix_world @ v.co).z for v in mesh.vertices]
        spread = max(world_z) - min(world_z)
        evaluated.to_mesh_clear()

        single = 0.02 * ref          # 單片厚度
        check("百葉窗的葉片有真的散開（不是疊在一起）", spread > single * 10,
              "跨度 %.4f，單片厚度 %.4f" % (spread, single))
        check("葉片數量正確（頂點數 = 12 片 × 8）",
              len(blinds.evaluated_get(
                  bpy.context.evaluated_depsgraph_get()).to_mesh().vertices) == 96)
    else:
        check("blinds 存在", False)

    plane = by_name.get("plain_plane")
    if plane:
        check("扁軸的 scale 沒有被設成 0", all(abs(s) > 1e-9 for s in plane.scale),
              str(list(plane.scale)))

    # dims 的語意是「關掉修改器後的局部尺寸」。斜的物件與有 Array 的物件
    # 是兩個最容易破功的情況，各測一個。
    def local_dims(obj):
        hidden = [m for m in obj.modifiers if m.show_viewport]
        for m in hidden:
            m.show_viewport = False
        bpy.context.view_layer.update()
        try:
            return list(obj.dimensions)
        finally:
            for m in hidden:
                m.show_viewport = True

    for name, expected in (("blinds", [0.4, 2.0, 0.02]),      # 斜的 ＋ 有 Array
                           ("emit_torus", [1.6, 0.3, 1.6]),   # 斜的（rot X 90°）
                           ("fog", [3.0, 3.0, 3.0])):         # 正的，當對照組
        obj = by_name.get(name)
        if obj:
            close("dims 套用正確 %s" % name, local_dims(obj),
                  [v * ref for v in expected], 1e-2)

    print("\n=== 5. 回寫（round-trip） ===")
    bpy.context.scene.cl12.active_preset = "smoke_test"
    result = bpy.ops.cl12.save_preset()
    check("save_preset 回傳 FINISHED", result == {"FINISHED"})

    presets.invalidate()
    saved = presets.get("smoke_test")
    check("存回來的預設讀得到", saved is not None)

    if saved:
        original = {spec["name"]: spec for spec in SYNTHETIC["objects"]}
        restored = {spec["name"]: spec for spec in saved["objects"]}
        check("回寫的物件數一致", len(restored) == len(original),
              "實得 %d，應為 %d" % (len(restored), len(original)))

        for name in ("key_area", "rim_spot", "fill_point", "emit_torus", "fog"):
            source, target = original.get(name), restored.get(name)
            if not source or not target:
                check("round-trip 找得到 %s" % name, False)
                continue
            close("round-trip %s.pos" % name, target["pos"], source["pos"], 1e-3)
            if source["kind"] == "LIGHT":
                close("round-trip %s.energy" % name,
                      target["energy"], source["energy"], 1e-2)
            material = source.get("material", {})
            if material.get("recipe") == "volume":
                close("round-trip %s.density" % name,
                      target["material"]["density"], material["density"], 1e-8)
            elif material.get("recipe") == "emission":
                close("round-trip %s.strength" % name,
                      target["material"]["strength"], material["strength"], 1e-4)

        grad = restored.get("grad_panel", {}).get("material", {})
        check("漸層配方回寫正確", grad.get("recipe") == "gradient_emission",
              str(grad.get("recipe")))
        check("漸層色標數正確", len(grad.get("ramp", {}).get("stops", [])) == 3,
              str(len(grad.get("ramp", {}).get("stops", []))))
        check("gradient_type 回寫正確", grad.get("gradient_type") == "EASING",
              str(grad.get("gradient_type")))
        # 這兩個欄位錯了，「漸層」那組的光會整個跑掉，而它是該組唯一光源。
        check("mapping.vector_type 回寫正確",
              grad.get("mapping", {}).get("vector_type") == "NORMAL",
              str(grad.get("mapping", {}).get("vector_type")))
        check("mapping.coord 回寫正確",
              grad.get("mapping", {}).get("coord") == "Object",
              str(grad.get("mapping", {}).get("coord")))

        magic = restored.get("magic_dome", {}).get("material", {})
        check("Magic 配方回寫正確", magic.get("recipe") == "magic_emission",
              str(magic.get("recipe")))
        if magic.get("magic"):
            check("Magic depth 回寫正確", magic["magic"]["depth"] == 3)
        bright = magic.get("bright_contrast")
        check("bright_contrast 有回寫", bright is not None)
        if bright:
            close("bright_contrast.contrast 正確", bright["contrast"], 0.2, 1e-5)

    print("\n=== 6. 滑桿 ===")
    settings = bpy.context.scene.cl12
    before = by_name["key_area"].data.energy
    settings.intensity = 2.0
    close("強度 ×2 後 energy 加倍", by_name["key_area"].data.energy, before * 2.0, 1e-2)
    settings.intensity = 1.0
    close("強度調回 1.0 後還原", by_name["key_area"].data.energy, before, 1e-2)

    distance_before = list(by_name["key_area"].location)
    energy_before = by_name["key_area"].data.energy
    settings.distance = 2.0
    close("距離 ×2 後位置加倍", list(by_name["key_area"].location),
          [v * 2.0 for v in distance_before], 1e-3)
    close("距離 ×2 後 energy ×4", by_name["key_area"].data.energy,
          energy_before * 4.0, 1e-1)
    sun_energy = by_name["sun"].data.energy
    close("距離改變不影響 SUN", sun_energy, 3.0, 1e-4)
    settings.distance = 1.0

    # 這是整個外掛的核心承諾：轉光域＝整組燈繞著主體轉。
    # 之前 matrix_parent_inverse 設錯時，這裡會靜默失效（燈不動），所以一定要測。
    import math
    from mathutils import Vector as V

    center = V(domain.location)
    before_offset = V(by_name["key_area"].matrix_world.translation) - center
    settings.rotation = math.radians(90.0)
    bpy.context.view_layer.update()
    after_offset = V(by_name["key_area"].matrix_world.translation) - center

    expected = V((-before_offset.y, before_offset.x, before_offset.z))
    close("光域轉 90° 後燈繞著主體轉", list(after_offset), list(expected), 1e-3)
    close("繞轉不改變燈到主體的距離",
          after_offset.length, before_offset.length, 1e-3)
    check("燈確實有移動（不是原地不動）",
          (after_offset - before_offset).length > 1e-3,
          "位移 %.6f" % (after_offset - before_offset).length)
    settings.rotation = 0.0

    print("\n=== 6b. 隱藏場景其他燈光 ===")
    # 阿哲問的正是這個情境：A 開、B/C 關。全部隱藏再還原之後，
    # 必須回到 A 開、B/C 關——而不是三盞全開。
    from CharacterLighting12 import properties as props

    # factory-startup 的預設場景本身就有一盞燈，先記下基準再比。
    baseline = len(props.other_lights(bpy.context))

    made = {}
    for name, visible in (("OtherA", True), ("OtherB", False), ("OtherC", False)):
        data = bpy.data.lights.new(name=name, type="POINT")
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_render = not visible
        obj.hide_viewport = not visible
        made[name] = obj

    others = props.other_lights(bpy.context)
    check("新增的 3 盞都被偵測到", len(others) == baseline + 3,
          "實得 %d，基準 %d" % (len(others), baseline))
    preset_lights = {o.name for o in tags.domain_children(domain)
                     if o.type == "LIGHT"}
    check("光域底下的燈不算「其他燈光」",
          not (preset_lights & {o.name for o in others}),
          str(sorted(preset_lights & {o.name for o in others})))

    settings.hide_other_lights = False   # 預設是開的，先關掉才測得到切換
    settings.hide_other_lights = True
    check("隱藏後 A 關掉了", made["OtherA"].hide_render)
    check("只有 A 被蓋記號（B/C 本來就關，不該碰）",
          tags.HIDDEN_BY_US in made["OtherA"]
          and tags.HIDDEN_BY_US not in made["OtherB"]
          and tags.HIDDEN_BY_US not in made["OtherC"])

    settings.hide_other_lights = False
    check("還原後 A 開回來", not made["OtherA"].hide_render)
    check("還原後 B 仍是關的（沒有被誤開）", made["OtherB"].hide_render)
    check("還原後 C 仍是關的（沒有被誤開）", made["OtherC"].hide_render)
    check("還原後記號已清掉", tags.HIDDEN_BY_US not in made["OtherA"])

    for obj in made.values():
        bpy.data.objects.remove(obj, do_unlink=True)

    print("\n=== 6c. 隱藏其他物件 ===")
    bpy.ops.mesh.primitive_cone_add(location=(8, 0, 0))
    bystander = bpy.context.object
    bystander.name = "Bystander"
    bpy.context.view_layer.update()

    listed = {o.name for o in props.other_objects(bpy.context)}
    check("旁邊的物件被列入", "Bystander" in listed, str(sorted(listed)))
    # 主體被藏起來就沒東西可以打光了，這是最不能錯的一條。
    check("主體不在隱藏名單內", subject.name not in listed, subject.name)
    check("光域自己不在隱藏名單內",
          domain.name not in listed and not (listed & {o.name for o in
                                                       tags.domain_children(domain)}))

    settings.hide_other_objects = True
    check("隱藏後旁邊物件關掉了", bystander.hide_render)
    check("隱藏後主體仍可見", not subject.hide_render)

    settings.hide_other_objects = False
    check("還原後旁邊物件回來了", not bystander.hide_render)
    check("還原後記號已清掉", tags.OBJECT_HIDDEN_BY_US not in bystander)

    bpy.data.objects.remove(bystander, do_unlink=True)

    print("\n=== 6d. 新增／匯出／匯入自訂預設 ===")
    import base64

    # 假裝算好的縮圖（1x1 PNG），驗證它能一路帶到匯入端。
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
        "IQAAAABJRU5ErkJggg==")
    thumb_file = os.path.join(bpy.app.tempdir, "cl12_test_thumb.png")
    with open(thumb_file, "wb") as handle:
        handle.write(tiny_png)

    before = set(presets.load_all().keys())
    result = bpy.ops.cl12.new_preset(
        preset_name="測試組", thumb_source="FILE", thumb_file=thumb_file)
    check("新增預設回傳 FINISHED", result == {"FINISHED"})

    new_ids = set(presets.load_all().keys()) - before
    check("多出一組預設", len(new_ids) == 1, str(sorted(new_ids)))

    if new_ids:
        new_id = new_ids.pop()
        created = presets.get(new_id)
        check("新預設是使用者版本", created.get("_is_user") is True)
        check("名稱有存到", presets.localized(created, "name", "zh") == "測試組")
        check("縮圖有嵌進 JSON", bool(created.get("thumbnail_png")))
        check("物件數與光域一致",
              len(created["objects"]) == len(tags.domain_children(domain)),
              "%d vs %d" % (len(created["objects"]),
                            len(tags.domain_children(domain))))

        cached = presets.thumbnail_path(created)
        check("縮圖能解回檔案", bool(cached) and os.path.exists(cached))

        # 匯出 → 刪掉 → 匯入，資料要完整回來（縮圖不能掉）
        exported = os.path.join(bpy.app.tempdir, "cl12_export.json")
        result = bpy.ops.cl12.export_preset(filepath=exported, preset_id=new_id)
        check("匯出回傳 FINISHED", result == {"FINISHED"})
        check("匯出檔案存在", os.path.exists(exported))

        check("刪除自訂預設成功", presets.delete_user(new_id))
        presets.invalidate()
        check("刪除後找不到了", presets.get(new_id) is None)

        result = bpy.ops.cl12.import_preset(filepath=exported)
        check("匯入回傳 FINISHED", result == {"FINISHED"})
        restored = presets.get(new_id)
        check("匯入後回得來", restored is not None)
        if restored:
            check("匯入後縮圖還在", bool(restored.get("thumbnail_png")))
            check("匯入後名稱正確",
                  presets.localized(restored, "name", "zh") == "測試組")
            check("匯入後物件數不變",
                  len(restored["objects"]) == len(created["objects"]))
            presets.delete_user(new_id)

    # 空光域不該存得出預設——存出來套用之後毫無反應，使用者找不出哪裡壞。
    empty_before = set(presets.load_all().keys())
    domain_mod = sys.modules["CharacterLighting12"].domain
    domain_mod.clear_domain_lights(domain)
    try:
        outcome = bpy.ops.cl12.new_preset(preset_name="空的", thumb_source="NONE")
        blocked = outcome == {"CANCELLED"}
    except RuntimeError:
        blocked = True
    check("空光域不能存成預設", blocked)
    check("空光域也沒有偷偷產生檔案",
          set(presets.load_all().keys()) == empty_before)
    bpy.ops.cl12.apply_preset(preset_id="smoke_test")   # 復原給後面的測試用

    print("\n=== 6e. 預覽相機 ===")
    from CharacterLighting12 import operators as ops

    cameras_before = len([o for o in bpy.context.scene.objects if o.type == "CAMERA"])
    scene_camera_before = bpy.context.scene.camera

    camera = ops.make_preview_camera(bpy.context, domain)
    check("預覽相機建得出來", camera is not None)
    if camera:
        close("鏡頭 1000mm", camera.data.lens, 1000.0, 1e-3)
        offset = V(camera.matrix_world.translation) - V(domain.location)
        close("相機距離 = ref × 23.537", abs(offset.y), ref * 23.537, ref * 0.01)
        close("相機高度 = ref × 0.111", offset.z, ref * 0.111, ref * 0.01)
        # 1000mm 在 23 倍遠處，預設裁切距離會看不到主體。
        check("裁切距離涵蓋得到主體",
              camera.data.clip_end > abs(offset.y) + ref,
              "clip_end=%.1f 距離=%.1f" % (camera.data.clip_end, abs(offset.y)))
        ops.remove_preview_camera(camera)

    # 算縮圖不可以改到使用者場景的算圖設定——他若把採樣調到 2048，
    # 存一張圖要等好幾分鐘；而且改完沒還原，之後正式算圖就變成 32 取樣。
    cycles = getattr(bpy.context.scene, "cycles", None)
    if cycles is not None:
        cycles.samples = 777
        bpy.context.scene.render.resolution_x = 1234
        ops_thumb = ops.render_thumbnail(bpy.context)
        check("縮圖算得出來", ops_thumb is not None and os.path.exists(ops_thumb))
        check("採樣值有還原", cycles.samples == 777, str(cycles.samples))
        check("解析度有還原",
              bpy.context.scene.render.resolution_x == 1234,
              str(bpy.context.scene.render.resolution_x))
        if ops_thumb:
            image = bpy.data.images.load(ops_thumb)
            check("縮圖是 256×256", tuple(image.size) == (256, 256), str(tuple(image.size)))
            bpy.data.images.remove(image)

    # 使用者只是存一張縮圖，場景不該因此多出一台相機、也不該被換掉主相機。
    cameras_after = len([o for o in bpy.context.scene.objects if o.type == "CAMERA"])
    check("臨時相機用完有收乾淨", cameras_after == cameras_before,
          "前 %d 後 %d" % (cameras_before, cameras_after))
    check("場景原本的相機沒有被換掉",
          bpy.context.scene.camera == scene_camera_before)
    check("相機資料塊也一併清掉",
          not any("CL12 Preview" in c.name for c in bpy.data.cameras))

    print("\n=== 6f. 面板文字折行 ===")
    from CharacterLighting12 import ui

    # 模擬 Blender 的字寬：中日韓字約是英文的兩倍。
    def fake_measure(value):
        return sum(2.0 if ord(ch) > 0x2E7F else 1.0 for ch in value) * 6.0

    for label, source in (
        ("中文", presets.get("melancholy")["tip"]["zh"]),
        ("英文", presets.get("melancholy")["tip"]["en"]),
        ("中英混排", "把 Intensity 調到 60%，暗部會吃掉更多細節 detail。"),
    ):
        lines = ui.wrap_text(source, 200.0, fake_measure)
        # 一、不能超寬（超寬就會被 Blender 截成「⋯」，正是阿哲遇到的問題）
        widest = max(fake_measure(line) for line in lines)
        check("%s 每行都不超寬" % label, widest <= 200.0,
              "最寬 %.0f > 200" % widest)
        # 二、不能吃掉字（折行最容易犯、又最難用眼睛發現的錯）
        joined = "".join(lines).replace(" ", "")
        original = source.replace(" ", "")
        check("%s 沒有掉字" % label, joined == original,
              "原 %d 字 → 折後 %d 字" % (len(original), len(joined)))
        check("%s 有真的折成多行" % label, len(lines) > 1, "只有 %d 行" % len(lines))

    # 「覆蓋」的對象必須是已套用的那組，不是縮圖牆上瀏覽的那組。
    # 兩者不同時若存錯目標，使用者會覆蓋掉他沒在看的預設。
    settings.active_preset = "smoke_test"
    bpy.context.scene.cl12_preview = presets.ordered()[0]["id"]
    if bpy.context.scene.cl12_preview != "smoke_test":
        before_text = json.dumps(
            presets.get(bpy.context.scene.cl12_preview)["objects"], sort_keys=True)
        bpy.ops.cl12.save_preset()
        presets.invalidate()
        after_text = json.dumps(
            presets.get(bpy.context.scene.cl12_preview)["objects"], sort_keys=True)
        check("覆蓋不會動到正在瀏覽的另一組", before_text == after_text)
        check("覆蓋確實寫到已套用的那組",
              presets.get("smoke_test").get("_is_user") is True)

    check("極窄寬度不會無限迴圈",
          len(ui.wrap_text("測試文字很長很長", 1.0, fake_measure)) == 8)
    check("空字串不會炸", ui.wrap_text("", 200.0, fake_measure) == [])

    print("\n=== 7. 錯誤路徑 ===")
    # operator 回報 ERROR 時 bpy.ops 會丟 RuntimeError，這是正常行為。
    try:
        result = bpy.ops.cl12.apply_preset(preset_id="does_not_exist")
        outcome = result == {"CANCELLED"}
    except RuntimeError as error:
        outcome = "找不到預設" in str(error)
    check("套用不存在的預設會被擋下", outcome)

    try:
        bpy.ops.object.select_all(action="DESELECT")
        outcome = bpy.ops.cl12.create_domain.poll() is False
    except RuntimeError:
        outcome = True
    check("沒有選取任何主體時，建立光域的按鈕是關的", outcome)

    removed = bpy.ops.cl12.clear_lights()
    check("clear_lights 回傳 FINISHED", removed == {"FINISHED"})
    check("清除後光域底下沒有殘留", len(tags.domain_children(domain)) == 0)
    check("清除後光域本身還在", domain.name in bpy.data.objects)

    print("\n=== 8. 反註冊 ===")
    addon.unregister()
    check("unregister() 沒有丟例外", True)

    # 收尾比對開頭拍的快照。用檔名樣式判斷不行——`zz_` 正是使用者自訂預設的
    # 正常前綴，那樣會把阿哲自己建的預設誤判成外洩。只認這次真的動過的。
    changed = []
    now = real_snapshot(REAL_PRESETS)
    for name, stamp in now.items():
        if BEFORE.get(name) != stamp:
            changed.append(name)
    for name in BEFORE:
        if name not in now:
            changed.append("%s（被刪除）" % name)
    check("沒有動到真實設定夾裡的任何檔案", not changed, "、".join(changed))

    try:
        os.remove(path)
    except OSError:
        pass


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
