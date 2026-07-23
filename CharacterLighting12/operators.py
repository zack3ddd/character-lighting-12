# SPDX-License-Identifier: GPL-3.0-or-later
"""所有按鈕。"""

import json
import math
import os

import bpy
from bpy.props import StringProperty
from mathutils import Vector

from . import (builder, domain as domain_mod, extract, presets, previews,
               properties, tags)

_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_BLEND = os.path.join(_ADDON_DIR, "assets", "example_subject.blend")
EXAMPLE_COLLECTION = "CL12 Example"

_ORIGINAL_WORLD = "cl12_original_world"


# ---------------------------------------------------------------- 光域

class CL12_OT_create_domain(bpy.types.Operator):
    bl_idname = "cl12.create_domain"
    bl_label = "選取主體並建立光域"
    bl_description = "量出選取物件的範圍，建立決定燈光範圍的空物體"
    bl_options = {"REGISTER", "UNDO"}

    from_example: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return bool(domain_mod.subject_candidates(context))

    def execute(self, context):
        subjects = domain_mod.subject_candidates(context)
        if not subjects:
            self.report({"ERROR"}, "請先選取要打光的主體")
            return {"CANCELLED"}

        result = domain_mod.evaluated_bbox(context, subjects)
        if result is None:
            self.report({"ERROR"}, "選取的物件量不到幾何範圍（是不是只選到空物體或骨架？）")
            return {"CANCELLED"}

        center, _size, ref, lo, hi = result
        if ref <= 1e-6:
            self.report({"ERROR"}, "主體尺寸接近零，無法建立光域")
            return {"CANCELLED"}

        # 範例一律用自己獨立的光域，絕不動使用者原本那顆——
        # 否則移除範例之後就回不去了。
        existing = None if self.from_example else tags.find_domain(context)
        if existing is not None:
            domain_mod.clear_domain_lights(existing)
            existing.location = center
            existing.rotation_euler = (0.0, 0.0, 0.0)
            domain_mod.resize_domain(existing, ref)
            existing[tags.DOMAIN_SUBJECT] = [obj.name for obj in subjects]
            new_domain = existing
            self.report({"INFO"}, "已更新既有光域（尺寸 %.2f）" % ref)
        else:
            new_domain = domain_mod.create_domain(
                context, center, ref, [obj.name for obj in subjects],
                from_example=self.from_example,
            )
            self.report({"INFO"}, "光域已建立（尺寸 %.2f）" % ref)

        domain_mod.store_subject_bounds(new_domain, lo, hi)

        for obj in context.selected_objects:
            obj.select_set(False)
        new_domain.select_set(True)
        context.view_layer.objects.active = new_domain
        return {"FINISHED"}


# ---------------------------------------------------------------- 套用預設

def _set_world(context, world_data):
    scene = context.scene
    if _ORIGINAL_WORLD not in scene and scene.world is not None:
        scene[_ORIGINAL_WORLD] = scene.world.name

    world = bpy.data.worlds.get("CL12 World")
    if world is None:
        world = bpy.data.worlds.new("CL12 World")
    world.use_nodes = True

    background = None
    for node in world.node_tree.nodes:
        if node.bl_idname == "ShaderNodeBackground":
            background = node
            break
    if background is None:
        background = world.node_tree.nodes.new("ShaderNodeBackground")
        output = world.node_tree.nodes.new("ShaderNodeOutputWorld")
        world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])

    background.inputs["Color"].default_value = tuple(world_data.get("color", (0, 0, 0))) + (1.0,)
    background.inputs["Strength"].default_value = float(world_data.get("strength", 1.0))
    scene.world = world


def _restore_world(context):
    scene = context.scene
    name = scene.get(_ORIGINAL_WORLD)
    if name:
        original = bpy.data.worlds.get(name)
        if original is not None:
            scene.world = original
        del scene[_ORIGINAL_WORLD]


class CL12_OT_apply_preset(bpy.types.Operator):
    bl_idname = "cl12.apply_preset"
    bl_label = "套用這組燈光"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty()

    @staticmethod
    def _reset_sliders(settings, domain):
        """滑桿歸位。

        用 `settings["key"]` 直接寫底層屬性、繞過 update callback——
        callback 是「算差額套上去」的，這裡不能觸發，否則會在剛生成的燈上
        再套一次舊倍率。旋轉刻意不重置：它就是光域的實際角度，
        歸零等於把使用者轉好的方向轉回去。
        """
        for key, value, applied in (
            ("intensity", 1.0, tags.APPLIED_INTENSITY),
            ("temperature", 6500.0, tags.APPLIED_TEMPERATURE),
            ("distance", 1.0, tags.APPLIED_DISTANCE),
        ):
            settings[key] = value
            domain[applied] = value
        settings["rotation"] = domain.rotation_euler.z

    def execute(self, context):
        settings = context.scene.cl12
        preset_id = self.preset_id or settings.active_preset
        data = presets.get(preset_id)
        if data is None:
            self.report({"ERROR"}, "找不到預設：%s" % preset_id)
            return {"CANCELLED"}

        target = tags.find_domain(context)
        if target is None:
            self.report({"ERROR"}, "請先建立光域（步驟一）")
            return {"CANCELLED"}

        domain_mod.clear_domain_lights(target)

        k = float(target.get(tags.DOMAIN_REF) or 1.0)
        created = []
        for spec in data.get("objects", []):
            try:
                if spec["kind"] == "LIGHT":
                    obj = builder.build_light(spec, k, preset_id)
                else:
                    obj = builder.build_mesh(spec, k, preset_id)
            except (KeyError, ValueError) as error:
                self.report({"WARNING"}, "「%s」建立失敗：%s" % (spec.get("name", "?"), error))
                continue
            created.append(obj)

        domain_mod.link_to_domain(context, target, created)

        # dimensions 要等物件進了 depsgraph 才讀得到正確的基礎尺寸。
        context.view_layer.update()
        for obj in created:
            if obj.type == "MESH":
                builder.apply_mesh_dimensions(obj, k)

        # 把切穿主體的輔助物件推出去。預設是圍著高瘦角色擺的，
        # 換成寬扁角色時貼得近的板子會插進身體裡。
        subject_lo, subject_hi = domain_mod.subject_bounds(target)
        moved = builder.push_out_of_subject(context, created, subject_lo, subject_hi)

        _set_world(context, data.get("world", {}))
        context.scene.render.film_transparent = settings.film_transparent
        properties.apply_wire_helpers(context)
        # 隱藏原有燈光預設是開的，所以套用時要主動執行一次，
        # 不能只靠勾選框的 update callback。
        properties.apply_visibility(context)

        target[tags.PRESET] = preset_id
        settings.active_preset = preset_id
        self._reset_sliders(settings, target)

        message = "已套用，共 %d 個物件" % len(created)
        if moved:
            message += "（%d 個輔助物件已避開主體）" % len(moved)
        self.report({"INFO"}, message)
        return {"FINISHED"}


class CL12_OT_clear_lights(bpy.types.Operator):
    bl_idname = "cl12.clear_lights"
    bl_label = "清除燈光"
    bl_description = "刪掉本外掛生成的燈光，光域保留"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        target = tags.find_domain(context)
        if target is None:
            self.report({"ERROR"}, "找不到光域")
            return {"CANCELLED"}
        removed = domain_mod.clear_domain_lights(target)
        # 藏起來的東西要放回去，否則使用者清掉燈光之後場景是空的，
        # 會以為外掛把他的東西刪了。
        properties.restore_all_hidden(context)
        _restore_world(context)
        context.scene.cl12.active_preset = ""
        if tags.PRESET in target:
            del target[tags.PRESET]
        self.report({"INFO"}, "已清除 %d 個物件" % removed)
        return {"FINISHED"}


# ---------------------------------------------------------------- 回寫

class CL12_OT_save_preset(bpy.types.Operator):
    bl_idname = "cl12.save_preset"
    bl_label = "更新這個預設"
    bl_description = "把目前場景裡調整過的燈光存回預設（不會動到內建檔）"

    def execute(self, context):
        target = tags.find_domain(context)
        if target is None:
            self.report({"ERROR"}, "找不到光域")
            return {"CANCELLED"}

        preset_id = context.scene.cl12.active_preset or target.get(tags.PRESET, "")
        base = presets.get(preset_id)
        if base is None:
            self.report({"ERROR"}, "目前沒有套用中的預設，不知道要存到哪一組")
            return {"CANCELLED"}

        data, warnings = extract.extract(context, target, base)
        data["base_id"] = preset_id
        path = presets.save_user(data)

        for warning in warnings:
            self.report({"WARNING"}, warning)
        self.report({"INFO"}, "已存到 %s" % os.path.basename(path))
        return {"FINISHED"}


class CL12_OT_revert_preset(bpy.types.Operator):
    bl_idname = "cl12.revert_preset"
    bl_label = "還原成內建版本"
    bl_description = "刪掉自己改過的版本，回到外掛出廠的設定"

    preset_id: StringProperty()

    def execute(self, context):
        preset_id = self.preset_id or context.scene.cl12.active_preset
        if presets.revert_user(preset_id):
            self.report({"INFO"}, "已還原成內建版本")
            return {"FINISHED"}
        self.report({"WARNING"}, "這組沒有自訂版本可以還原")
        return {"CANCELLED"}


class CL12_OT_open_preset_folder(bpy.types.Operator):
    bl_idname = "cl12.open_preset_folder"
    bl_label = "開啟燈光預設資料夾"
    bl_description = "打開存放自訂預設的資料夾"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=presets.user_dir())
        return {"FINISHED"}


# ---------------------------------------------------------------- 範例

class CL12_OT_load_example(bpy.types.Operator):
    bl_idname = "cl12.load_example"
    bl_label = "載入範例"
    bl_description = "載入一個範例角色與對應的相機，並自動建立光域"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        # 場景裡只留一顆光域。既有的會被刪掉，所以先問過再動手——
        # 使用者調了半天卻沒存成預設的東西，刪掉就回不來了。
        if tags.find_domain(context) is not None:
            return context.window_manager.invoke_props_dialog(self, width=360)
        return self.execute(context)

    def draw(self, context):
        column = self.layout.column(align=True)
        column.label(text="這會刪掉目前的光域，", icon="ERROR")
        column.label(text="以及底下所有已套用的燈光。")
        column.separator()
        column.label(text="你調整過但還沒按「更新這個預設」的設定")
        column.label(text="會一起消失。")

    def execute(self, context):
        if not os.path.exists(EXAMPLE_BLEND):
            self.report({"ERROR"}, "找不到範例檔案：%s" % EXAMPLE_BLEND)
            return {"CANCELLED"}

        existing = [obj for obj in context.scene.objects if tags.EXAMPLE in obj]
        if existing:
            self.report({"WARNING"}, "範例已經在場景裡了")
            return {"CANCELLED"}

        # 場景中永遠只有一顆光域：舊的連同它的燈一起收掉。
        for old in [obj for obj in context.scene.objects if tags.DOMAIN in obj]:
            domain_mod.clear_domain_lights(old)
            bpy.data.objects.remove(old, do_unlink=True)
        properties.restore_all_hidden(context)
        _restore_world(context)
        context.scene.cl12.active_preset = ""

        with bpy.data.libraries.load(EXAMPLE_BLEND, link=False) as (source, target):
            target.objects = list(source.objects)

        collection = tags.collection_for(context, EXAMPLE_COLLECTION)
        loaded = []
        for obj in target.objects:
            if obj is None:
                continue
            obj[tags.EXAMPLE] = True
            collection.objects.link(obj)
            loaded.append(obj)

        if not loaded:
            self.report({"ERROR"}, "範例檔案裡沒有可載入的物件")
            return {"CANCELLED"}

        meshes = [obj for obj in loaded if obj.type == "MESH"]
        camera = next((obj for obj in loaded if obj.type == "CAMERA"), None)
        if camera is not None and context.scene.camera is None:
            context.scene.camera = camera

        context.view_layer.update()
        if meshes:
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in meshes:
                obj.select_set(True)
            context.view_layer.objects.active = meshes[0]
            bpy.ops.cl12.create_domain(from_example=True)

            # 載入範例的目的就是「乾淨地看這 12 組光」，所以兩個隔離開關
            # 都打開。用屬性指派而不是直接改底層，才會觸發實際的隱藏動作。
            context.scene.cl12.hide_other_lights = True
            context.scene.cl12.hide_other_objects = True

        self.report({"INFO"}, "範例已載入（%d 個物件）" % len(loaded))
        return {"FINISHED"}


class CL12_OT_remove_example(bpy.types.Operator):
    bl_idname = "cl12.remove_example"
    bl_label = "移除範例"
    bl_description = "把範例角色與相機從場景移除"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        doomed = [obj for obj in context.scene.objects if tags.EXAMPLE in obj]
        for obj in doomed:
            bpy.data.objects.remove(obj, do_unlink=True)

        # 範例自己的光域跟著範例走：連同它底下的燈一起收掉。
        # 使用者自己建的光域完全不碰——載入範例時就沒動過它，所以還在原位。
        example_domains = [obj for obj in context.scene.objects
                           if tags.DOMAIN_FROM_EXAMPLE in obj]
        for domain in example_domains:
            domain_mod.clear_domain_lights(domain)
            bpy.data.objects.remove(domain, do_unlink=True)

        collection = bpy.data.collections.get(EXAMPLE_COLLECTION)
        if collection is not None and not collection.objects:
            bpy.data.collections.remove(collection)

        properties.restore_all_hidden(context)
        _restore_world(context)
        context.scene.cl12.active_preset = ""
        self.report({"INFO"}, "已移除 %d 個範例物件與範例光域" % len(doomed))
        return {"FINISHED"}


class CL12_OT_view_example_camera(bpy.types.Operator):
    bl_idname = "cl12.view_example_camera"
    bl_label = "切到範例視角"
    bl_description = "把視窗切到範例相機的角度，看到的畫面才會跟預設縮圖一致"

    def execute(self, context):
        camera = next(
            (obj for obj in context.scene.objects
             if obj.type == "CAMERA" and tags.EXAMPLE in obj),
            None,
        )
        if camera is None:
            self.report({"WARNING"}, "場景裡沒有範例相機")
            return {"CANCELLED"}
        context.scene.camera = camera
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].region_3d.view_perspective = "CAMERA"
                break
        return {"FINISHED"}


class CL12_OT_switch_to_cycles(bpy.types.Operator):
    bl_idname = "cl12.switch_to_cycles"
    bl_label = "切換到 Cycles"
    bl_description = "本外掛的數值是照 Cycles 校過的"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.render.engine = "CYCLES"
        return {"FINISHED"}


# ---------------------------------------------------------------- 預覽相機

# 沿用原始教學檔的 1000mm 長焦（那個平面、少透視的味道就來自它），
# 但取景改成「把主體整個框進去並置中」。
#
# ⚠️ 不能照抄原檔的相機距離比例。原檔那個構圖刻意只框到胸口——分母是全身高，
# 畫面卻只涵蓋 0.85 倍，對高瘦角色是好看的半身像，對球體或寬扁的主體就變成
# 上下被切掉、而且原檔相機略高於中心，看起來還會偏。
PREVIEW_LENS = 1000.0
PREVIEW_SENSOR = 36.0
PREVIEW_MARGIN = 1.15        # 完整框住時四周留的空隙
PREVIEW_PORTRAIT = 1.55      # 半身構圖：畫面高 ≈ 主體寬 × 這個值
PREVIEW_HEADROOM = 0.05      # 裁切時頭頂留的空間（佔畫面比例）
PREVIEW_MIN_COVER = 0.5      # 再瘦長也至少要涵蓋一半高度，不要只剩一顆頭


def preview_framing(lo, hi):
    """算出畫面高度與相機的垂直位置。回傳 (frame, camera_z, cropped)。

    這條規則是從阿哲原檔的相機反推的：畫面高度約等於**主體寬度的 1.55 倍**，
    並且對齊頭頂留一點空間——不是「固定比例」，而是「以寬度決定、往上對齊」。

    高瘦的角色因此自然裁掉下半身，得到半身像；方正或寬扁的主體（球體、
    寬扁角色）框得下，就完整置中不裁。同一條規則兩種結果，不用分開處理。
    """
    width = max(hi.x - lo.x, 1e-6)
    height = max(hi.z - lo.z, 1e-6)

    full = max(width, height) * PREVIEW_MARGIN      # 完整框住需要的高度
    portrait = width * PREVIEW_PORTRAIT             # 半身構圖的高度
    frame = max(min(full, portrait), full * PREVIEW_MIN_COVER)

    if frame < height:
        # 框不下 → 對齊頭頂，裁掉下面（這就是原檔那個半身構圖）
        camera_z = hi.z + frame * PREVIEW_HEADROOM - frame * 0.5
        cropped = True
    else:
        # 框得下 → 置中，上下留白對稱
        camera_z = (lo.z + hi.z) * 0.5
        cropped = False
    return frame, camera_z, cropped


def make_preview_camera(context, domain):
    """建一台取景與內建縮圖同風格的相機並回傳。

    呼叫端負責收掉——縮圖算完就該消失，使用者的場景不該因為存了一張圖
    就多出一台相機。
    """
    lo, hi = domain_mod.subject_bounds(domain)
    centre = (lo + hi) * 0.5

    frame, camera_z, _cropped = preview_framing(lo, hi)
    if frame <= 1e-6:
        frame = float(domain.get(tags.DOMAIN_REF) or 1.0)
    distance = frame * (PREVIEW_LENS / PREVIEW_SENSOR)

    data = bpy.data.cameras.new("CL12 Preview Camera")
    camera = bpy.data.objects.new("CL12 Preview Camera", data)
    camera[tags.PREVIEW_CAMERA] = True

    data.lens = PREVIEW_LENS
    data.sensor_width = PREVIEW_SENSOR
    data.sensor_fit = "AUTO"
    # 長焦代表相機站得很遠，預設的裁切距離會什麼都看不到。
    data.clip_start = max(0.01, distance - frame)
    data.clip_end = distance + frame * 10.0

    context.scene.collection.objects.link(camera)
    camera.location = (centre.x, centre.y - distance, camera_z)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    context.view_layer.update()
    return camera


def remove_preview_camera(camera):
    data = camera.data
    bpy.data.objects.remove(camera, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.cameras.remove(data)


# ---------------------------------------------------------------- 自訂預設

THUMB_SIZE = 256
THUMB_SAMPLES = 32


def render_thumbnail(context, size=THUMB_SIZE):
    """用臨時的預覽相機算一張方形縮圖，回傳暫存檔路徑。

    相機是現建現拆的：算完就移除、場景原本的相機還原回去。使用者只是存了
    一張縮圖，場景裡不該因此多出一台相機。
    有光域就用與內建縮圖同構圖的機位；沒有就退回場景現有的相機。
    """
    scene = context.scene
    domain = tags.find_domain(context)

    temporary = None
    previous = scene.camera
    if domain is not None:
        temporary = make_preview_camera(context, domain)
        scene.camera = temporary
    elif scene.camera is None:
        return None

    saved = (scene.render.resolution_x, scene.render.resolution_y,
             scene.render.resolution_percentage, scene.render.filepath,
             scene.render.image_settings.file_format)

    # 採樣也要自己指定並還原。不設的話會沿用使用者場景當下的值——
    # 他若把最終算圖調到 2048，存一張縮圖就要等上好幾分鐘。
    cycles = getattr(scene, "cycles", None)
    saved_cycles = None
    if cycles is not None and hasattr(cycles, "samples"):
        saved_cycles = (cycles.samples, getattr(cycles, "use_denoising", None))
        cycles.samples = THUMB_SAMPLES
        if hasattr(cycles, "use_denoising"):
            cycles.use_denoising = True    # 32 取樣要靠降噪才乾淨

    path = os.path.join(bpy.app.tempdir, "cl12_thumb.png")
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError:
        return None
    finally:
        (scene.render.resolution_x, scene.render.resolution_y,
         scene.render.resolution_percentage, scene.render.filepath,
         scene.render.image_settings.file_format) = saved
        if saved_cycles is not None:
            cycles.samples = saved_cycles[0]
            if saved_cycles[1] is not None:
                cycles.use_denoising = saved_cycles[1]
        if temporary is not None:
            scene.camera = previous
            remove_preview_camera(temporary)

    return path if os.path.exists(path) else None


def store_thumbnail(preset_id, image_path):
    """把一張圖設成某組預設的縮圖。回傳 (成功, 訊息)。"""
    data = presets.get(preset_id)
    if data is None:
        return False, "找不到這組預設"

    encoded = presets.encode_thumbnail(image_path)
    if not encoded:
        return False, "讀不到圖片"

    payload = {key: value for key, value in data.items()
               if not key.startswith("_")}
    payload["thumbnail_png"] = encoded
    payload["_filename"] = data.get("_filename")
    presets.save_user(payload)
    previews.refresh()
    return True, "縮圖已更新"


class CL12_OT_replace_thumbnail(bpy.types.Operator):
    bl_idname = "cl12.replace_thumbnail"
    bl_label = "重算縮圖"
    bl_description = "用預覽相機重新算一張縮圖給這組預設（相機是臨時的，算完會移除）"

    preset_id: StringProperty()

    def execute(self, context):
        preset_id = self.preset_id or context.scene.cl12_preview
        settings = context.scene.cl12

        # ⚠️ 縮圖必須拍「這組預設本身」，不是場景當下的樣子。
        # 之前少了這一步：使用者瀏覽 A 但場景套著 B（甚至別組燈），
        # 按重算就把 B 的畫面存成 A 的縮圖（阿哲遇過復古被存成綠圖）。
        # 所以目標不是當前套用中的組時，先乾淨套用它再拍。
        if settings.active_preset != preset_id and tags.find_domain(context):
            try:
                bpy.ops.cl12.apply_preset(preset_id=preset_id)
            except RuntimeError as error:
                self.report({"ERROR"}, "無法套用「%s」：%s" % (preset_id, error))
                return {"CANCELLED"}

        image = render_thumbnail(context)
        if image is None:
            self.report({"ERROR"}, "算圖失敗（場景裡沒有光域也沒有相機？）")
            return {"CANCELLED"}
        ok, message = store_thumbnail(preset_id, image)
        self.report({"INFO"} if ok else {"ERROR"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class CL12_OT_load_thumbnail(bpy.types.Operator):
    bl_idname = "cl12.load_thumbnail"
    bl_label = "載入縮圖"
    bl_description = "用你自己準備的圖片當這組預設的縮圖"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg", options={"HIDDEN"})
    preset_id: StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        self.preset_id = self.preset_id or context.scene.cl12_preview
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath or not os.path.exists(self.filepath):
            self.report({"ERROR"}, "找不到這個檔案")
            return {"CANCELLED"}
        ok, message = store_thumbnail(self.preset_id, self.filepath)
        self.report({"INFO"} if ok else {"ERROR"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class CL12_OT_new_preset(bpy.types.Operator):
    bl_idname = "cl12.new_preset"
    bl_label = "新增燈光預設"
    bl_description = "把目前光域裡的燈光存成一組新的預設"

    preset_name: StringProperty(name="名稱", default="")
    thumb_source: bpy.props.EnumProperty(
        name="縮圖",
        items=(
            ("RENDER", "自動算縮圖", "用與內建縮圖同構圖的臨時相機算一張，算完自動移除"),
            ("FILE", "選擇圖片檔", "使用你自己準備好的圖片"),
            ("NONE", "先不要縮圖", "之後再補"),
        ),
        default="RENDER",
    )
    thumb_file: StringProperty(name="圖片", default="", subtype="FILE_PATH")

    def invoke(self, context, event):
        if tags.find_domain(context) is None:
            self.report({"ERROR"}, "請先建立光域")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        column.prop(self, "preset_name")
        column.prop(self, "thumb_source")
        if self.thumb_source == "FILE":
            column.prop(self, "thumb_file")
        elif self.thumb_source == "RENDER":
            # 按下確定就開始算圖，畫面會卡住。先講，不然使用者會以為當掉。
            note = column.column(align=True)
            note.scale_y = 0.85
            note.label(text="按下確定後會算一張圖，", icon="INFO")
            note.label(text="場景越複雜等越久，期間畫面會沒有反應。")

    def execute(self, context):
        target = tags.find_domain(context)
        if target is None:
            self.report({"ERROR"}, "請先建立光域")
            return {"CANCELLED"}

        display = self.preset_name.strip()
        if not display:
            self.report({"ERROR"}, "請輸入名稱")
            return {"CANCELLED"}

        preset_id = presets.make_id(display, set(presets.load_all().keys()))
        base = {
            "schema": presets.SCHEMA,
            "id": preset_id,
            "name": {"en": display, "zh": display},
            "desc": {"en": "", "zh": ""},
            "tip": {"en": "", "zh": ""},
            "engine_note": None,
            "_filename": "zz_%s.json" % preset_id,   # 排在內建 12 組後面
        }

        data, warnings = extract.extract(context, target, base)

        # 光域裡什麼都沒有就別存——存出來會是一組套用後毫無反應的空預設，
        # 縮圖牆上多一格，使用者卻找不出哪裡壞了。
        if not data.get("objects"):
            self.report({"ERROR"},
                        "光域裡沒有燈光，先套用一組或自己加幾盞再存")
            return {"CANCELLED"}

        thumbnail = None
        if self.thumb_source == "RENDER":
            thumbnail = render_thumbnail(context)
            if thumbnail is None:
                warnings.append("算圖失敗，這組先沒有縮圖")
        elif self.thumb_source == "FILE":
            candidate = bpy.path.abspath(self.thumb_file)
            if candidate and os.path.exists(candidate):
                thumbnail = candidate
            else:
                warnings.append("找不到指定的圖片，這組先沒有縮圖")

        if thumbnail:
            encoded = presets.encode_thumbnail(thumbnail)
            if encoded:
                data["thumbnail_png"] = encoded

        presets.save_user(data)
        previews.refresh()
        context.scene.cl12.active_preset = preset_id
        context.scene.cl12_preview = preset_id

        for warning in warnings:
            self.report({"WARNING"}, warning)
        self.report({"INFO"}, "已新增預設「%s」" % display)
        return {"FINISHED"}


class CL12_OT_delete_preset(bpy.types.Operator):
    bl_idname = "cl12.delete_preset"
    bl_label = "刪除燈光預設"
    bl_description = "刪掉自訂預設。內建的 12 組刪不掉"

    preset_id: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preset_id = self.preset_id or context.scene.cl12.active_preset
        data = presets.get(preset_id)
        if data is None or not data.get("_is_user") or data.get("_overrides_builtin"):
            self.report({"WARNING"}, "這是內建預設，刪不掉")
            return {"CANCELLED"}

        if presets.delete_user(preset_id):
            previews.refresh()
            remaining = presets.ordered()
            if remaining:
                context.scene.cl12_preview = remaining[0]["id"]
            self.report({"INFO"}, "已刪除")
            return {"FINISHED"}
        self.report({"ERROR"}, "刪除失敗")
        return {"CANCELLED"}


class CL12_OT_export_preset(bpy.types.Operator):
    bl_idname = "cl12.export_preset"
    bl_label = "匯出燈光預設"
    bl_description = "把這組預設存成一個檔案，可以備份或分享給別人"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    preset_id: StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        preset_id = self.preset_id or context.scene.cl12_preview
        data = presets.get(preset_id)
        if data is None:
            self.report({"ERROR"}, "找不到這組預設")
            return {"CANCELLED"}
        self.preset_id = preset_id
        self.filepath = "%s.json" % preset_id
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        data = presets.get(self.preset_id)
        if data is None:
            self.report({"ERROR"}, "找不到這組預設")
            return {"CANCELLED"}

        payload = {key: value for key, value in data.items()
                   if not key.startswith("_")}
        # 縮圖一併塞進同一個檔案，帶走就不會掉圖。
        if "thumbnail_png" not in payload:
            source = presets.thumbnail_path(data)
            if source:
                encoded = presets.encode_thumbnail(source)
                if encoded:
                    payload["thumbnail_png"] = encoded

        path = self.filepath
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as error:
            self.report({"ERROR"}, "寫入失敗：%s" % error)
            return {"CANCELLED"}

        self.report({"INFO"}, "已匯出 %s" % os.path.basename(path))
        return {"FINISHED"}


class CL12_OT_import_preset(bpy.types.Operator):
    bl_idname = "cl12.import_preset"
    bl_label = "匯入燈光預設"
    bl_description = "讀入別人分享或自己備份的預設檔"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            with open(self.filepath, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, "讀不了這個檔案：%s" % error)
            return {"CANCELLED"}

        if data.get("schema") != presets.SCHEMA or "objects" not in data:
            self.report({"ERROR"}, "這不是本外掛的預設檔")
            return {"CANCELLED"}

        # 匯入的 id 若跟現有的撞名，改一個新的，不要蓋掉使用者原本的東西。
        existing = set(presets.load_all().keys())
        original = data.get("id", "imported")
        if original in existing:
            data["id"] = presets.make_id(original, existing)
        data["_filename"] = "zz_%s.json" % data["id"]

        path = presets.save_user(data)
        previews.refresh()
        context.scene.cl12_preview = data["id"]
        renamed = "（改名為 %s）" % data["id"] if data["id"] != original else ""
        self.report({"INFO"}, "已匯入 %s%s" % (os.path.basename(path), renamed))
        return {"FINISHED"}


classes = (
    CL12_OT_create_domain,
    CL12_OT_apply_preset,
    CL12_OT_clear_lights,
    CL12_OT_save_preset,
    CL12_OT_revert_preset,
    CL12_OT_open_preset_folder,
    CL12_OT_load_example,
    CL12_OT_remove_example,
    CL12_OT_view_example_camera,
    CL12_OT_switch_to_cycles,
    CL12_OT_replace_thumbnail,
    CL12_OT_load_thumbnail,
    CL12_OT_new_preset,
    CL12_OT_delete_preset,
    CL12_OT_export_preset,
    CL12_OT_import_preset,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
