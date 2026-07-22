# SPDX-License-Identifier: GPL-3.0-or-later
"""場景屬性與四個全域滑桿。

滑桿的作法是「算差額套上去」，不是「從基準值重算」——
這樣阿哲手動把某盞燈拖遠、調暗之後再動滑桿，他的手動調整不會被洗掉。
代價是浮點會有極微小的累積誤差，對燈光來說完全無感。
"""

import bpy
from mathutils import Vector

from . import tags

# ---------------------------------------------------------------- 色溫

def kelvin_to_rgb(kelvin):
    """Tanner Helland 的近似式。用來做色溫滑桿的相對位移，不追求物理精確。"""
    temperature = max(1000.0, min(15000.0, float(kelvin))) / 100.0

    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * _log(temperature) - 161.1195681661
    else:
        red = 329.698727446 * ((temperature - 60.0) ** -0.1332047592)
        green = 288.1221695283 * ((temperature - 60.0) ** -0.0755148492)

    if temperature >= 66.0:
        blue = 255.0
    elif temperature <= 19.0:
        blue = 0.0
    else:
        blue = 138.5177312231 * _log(temperature - 10.0) - 305.0447927307

    return tuple(max(0.0, min(1.0, channel / 255.0)) for channel in (red, green, blue))


def _log(value):
    import math
    return math.log(max(value, 1e-6))


# ---------------------------------------------------------------- 滑桿實作

def _lights_and_emitters(domain):
    lights, emitters = [], []
    for obj in domain.children_recursive:
        if obj.type == "LIGHT":
            lights.append(obj)
        elif obj.type == "MESH" and obj.data and obj.data.materials:
            material = obj.data.materials[0]
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    if node.bl_idname == "ShaderNodeEmission":
                        emitters.append(node)
    return lights, emitters


def _update_intensity(self, context):
    domain = tags.find_domain(context)
    if domain is None:
        return
    previous = float(domain.get(tags.APPLIED_INTENSITY) or 1.0)
    current = max(0.001, float(self.intensity))
    ratio = current / max(previous, 1e-6)
    if abs(ratio - 1.0) < 1e-9:
        return

    lights, emitters = _lights_and_emitters(domain)
    for obj in lights:
        obj.data.energy *= ratio
    # 「漸層」那組沒有燈光物件，全靠發光面——強度滑桿必須也管到它，否則拉了沒反應。
    for node in emitters:
        node.inputs["Strength"].default_value *= ratio

    domain[tags.APPLIED_INTENSITY] = current


def _update_temperature(self, context):
    domain = tags.find_domain(context)
    if domain is None:
        return
    previous = float(domain.get(tags.APPLIED_TEMPERATURE) or 6500.0)
    current = float(self.temperature)
    if abs(current - previous) < 1.0:
        return

    old_rgb = kelvin_to_rgb(previous)
    new_rgb = kelvin_to_rgb(current)
    # 夾住比值，避免某個通道趨近 0 時把顏色永久壓死。
    ratio = tuple(
        max(0.05, min(20.0, new / max(old, 1e-4)))
        for new, old in zip(new_rgb, old_rgb)
    )

    lights, emitters = _lights_and_emitters(domain)
    for obj in lights:
        obj.data.color = tuple(
            max(0.0, min(1.0, channel * factor))
            for channel, factor in zip(obj.data.color, ratio)
        )
    for node in emitters:
        colour = node.inputs["Color"].default_value
        for index in range(3):
            colour[index] = max(0.0, min(1.0, colour[index] * ratio[index]))

    domain[tags.APPLIED_TEMPERATURE] = current


def _update_distance(self, context):
    domain = tags.find_domain(context)
    if domain is None:
        return
    previous = float(domain.get(tags.APPLIED_DISTANCE) or 1.0)
    current = max(0.05, float(self.distance))
    ratio = current / max(previous, 1e-6)
    if abs(ratio - 1.0) < 1e-9:
        return

    for obj in domain.children_recursive:
        if tags.DOMAIN in obj:
            continue
        obj.location = Vector(obj.location) * ratio
        # 燈拉遠了要補光，照度 ∝ 功率/距離²。SUN 是平行光，不受距離影響。
        if obj.type == "LIGHT" and obj.data.type != "SUN":
            obj.data.energy *= ratio ** 2

    domain[tags.APPLIED_DISTANCE] = current


def _update_rotation(self, context):
    domain = tags.find_domain(context)
    if domain is None:
        return
    # 旋轉直接就是光域自己的變換，沒有差額問題。
    domain.rotation_euler.z = self.rotation


# ---------------------------------------------------------------- GPU

# NVIDIA 走 CUDA 而不是 OptiX——阿哲的判斷：這類場景相對單純，
# 他偏好 CUDA。使用者若自己在偏好設定裡改成 OptiX，外掛不會再去動它。
BACKEND_ORDER = ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL")


def cycles_preferences():
    addon = bpy.context.preferences.addons.get("cycles")
    return addon.preferences if addon else None


_backend_cache = None


def available_backends():
    """回傳這台機器上真的有裝置可用的運算後端。

    有快取：面板每次重繪都會問一次，而顯示卡不會在使用中途插拔。
    不快取的話等於每個 redraw 都去查詢五種後端，面板會變鈍。
    """
    global _backend_cache
    if _backend_cache is not None:
        return _backend_cache

    prefs = cycles_preferences()
    if prefs is None:
        return []          # Cycles 沒啟用，不快取，之後啟用了要能重查

    found = []
    for backend in BACKEND_ORDER:
        try:
            devices = prefs.get_devices_for_type(backend)
        except (TypeError, RuntimeError):
            continue
        if devices:
            found.append(backend)

    _backend_cache = found
    return _backend_cache


def gpu_available():
    return bool(available_backends())


def _get_use_gpu(self):
    scene = bpy.context.scene
    cycles = getattr(scene, "cycles", None)
    return bool(cycles and cycles.device == "GPU")


def _set_use_gpu(self, value):
    scene = bpy.context.scene
    cycles = getattr(scene, "cycles", None)
    if cycles is None:
        return

    if not value:
        cycles.device = "CPU"
        return

    prefs = cycles_preferences()
    backends = available_backends()
    if prefs is not None and backends:
        # 只有在完全沒配置過的時候才出手配置一次；
        # 使用者已經選好後端就尊重他的選擇，不覆蓋。
        if prefs.compute_device_type not in backends:
            prefs.compute_device_type = backends[0]
            for device in prefs.get_devices_for_type(backends[0]):
                device.use = True
    cycles.device = "GPU"


def describe_gpu():
    """回傳 (後端, 裝置名稱清單)，給狀態列訊息用。"""
    prefs = cycles_preferences()
    if prefs is None:
        return None, []
    backend = prefs.compute_device_type
    if not backend or backend == "NONE":
        return None, []
    try:
        devices = prefs.get_devices_for_type(backend)
    except (TypeError, RuntimeError):
        return backend, []
    return backend, [d.name for d in devices if d.use]


# ---------------------------------------------------------------- 其他燈光

def _domain_members(context):
    """光域自己與它底下的所有物件。"""
    domain = tags.find_domain(context)
    if domain is None:
        return set()
    return {domain.name} | {obj.name for obj in domain.children_recursive}


def other_lights(context):
    """場景裡不屬於光域的燈光物件。

    只算燈光物件——自發光材質關不掉，也沒有立場替使用者判斷
    哪些發光物是「照明」哪些是「造型」。
    """
    ours = _domain_members(context)
    return [obj for obj in context.scene.objects
            if obj.type == "LIGHT" and obj.name not in ours]


def other_objects(context):
    """主體與光域以外的物件。

    主體要留著（不然就沒東西可以打光了），相機也留著
    （藏起來不影響算圖，只會讓使用者找不到取景框）。
    """
    ours = _domain_members(context)
    domain = tags.find_domain(context)
    subjects = set(domain.get(tags.DOMAIN_SUBJECT) or []) if domain else set()
    return [obj for obj in context.scene.objects
            if obj.type not in {"LIGHT", "CAMERA"}
            and obj.name not in ours
            and obj.name not in subjects]


def _hide(objects, marker):
    for obj in objects:
        if obj.hide_render and obj.hide_viewport:
            continue  # 本來就是關的，別碰，還原時才不會誤開
        obj[marker] = True
        obj.hide_render = True
        obj.hide_viewport = True


def _restore(context, marker):
    for obj in context.scene.objects:
        if marker in obj:
            obj.hide_render = False
            obj.hide_viewport = False
            del obj[marker]


def apply_visibility(context):
    """依目前的兩個開關，重新套用隱藏狀態。套用預設之後會呼叫。"""
    settings = context.scene.cl12
    if settings.hide_other_lights:
        _hide(other_lights(context), tags.HIDDEN_BY_US)
    else:
        _restore(context, tags.HIDDEN_BY_US)

    if settings.hide_other_objects:
        _hide(other_objects(context), tags.OBJECT_HIDDEN_BY_US)
    else:
        _restore(context, tags.OBJECT_HIDDEN_BY_US)


def restore_all_hidden(context):
    """清除燈光時把藏起來的東西全部放回來。"""
    _restore(context, tags.HIDDEN_BY_US)
    _restore(context, tags.OBJECT_HIDDEN_BY_US)


def _update_hide_other_lights(self, context):
    if self.hide_other_lights:
        _hide(other_lights(context), tags.HIDDEN_BY_US)
    else:
        _restore(context, tags.HIDDEN_BY_US)


def _update_hide_other_objects(self, context):
    if self.hide_other_objects:
        _hide(other_objects(context), tags.OBJECT_HIDDEN_BY_US)
    else:
        _restore(context, tags.OBJECT_HIDDEN_BY_US)


def _update_film_transparent(self, context):
    context.scene.render.film_transparent = self.film_transparent


def apply_wire_helpers(context):
    """把輔助 mesh 切成線框／實體。燈光物件本來就不擋視線，不用動。"""
    domain = tags.find_domain(context)
    if domain is None:
        return
    wanted = "WIRE" if context.scene.cl12.wire_helpers else "TEXTURED"
    for obj in domain.children_recursive:
        if obj.type == "MESH":
            obj.display_type = wanted


def _update_wire_helpers(self, context):
    apply_wire_helpers(context)


class CL12Settings(bpy.types.PropertyGroup):
    active_preset: bpy.props.StringProperty(
        name="Preset",
        default="",
    )
    intensity: bpy.props.FloatProperty(
        name="強度 Intensity",
        description="整組燈光的亮度倍率",
        default=1.0, min=0.0, max=5.0, soft_max=3.0,
        subtype="FACTOR",
        update=_update_intensity,
    )
    temperature: bpy.props.FloatProperty(
        name="色溫 Temperature",
        description="整組燈光的色溫（6500K 為不改變）",
        default=6500.0, min=1500.0, max=15000.0,
        update=_update_temperature,
    )
    distance: bpy.props.FloatProperty(
        name="距離 Distance",
        description="燈光離主體的距離倍率，強度會自動補償",
        default=1.0, min=0.1, max=4.0, soft_max=2.5,
        subtype="FACTOR",
        update=_update_distance,
    )
    rotation: bpy.props.FloatProperty(
        name="旋轉 Rotation",
        description="整組燈光繞主體旋轉",
        default=0.0, subtype="ANGLE",
        update=_update_rotation,
    )

    film_transparent: bpy.props.BoolProperty(
        name="背景透明",
        description="輸出帶透明通道",
        default=False,
        update=_update_film_transparent,
    )
    use_gpu: bpy.props.BoolProperty(
        name="GPU",
        description="用顯示卡算圖。若 Blender 尚未設定過運算裝置，"
                    "勾選時會自動幫你配置一次",
        get=_get_use_gpu,
        set=_set_use_gpu,
    )
    hide_other_lights: bpy.props.BoolProperty(
        name="隱藏原燈光",
        description="將不屬於光域的燈光隱藏",
        default=True,
        update=_update_hide_other_lights,
    )
    hide_other_objects: bpy.props.BoolProperty(
        name="隱藏原物件",
        description="將主體與光域以外的物件隱藏",
        default=False,
        update=_update_hide_other_objects,
    )
    wire_helpers: bpy.props.BoolProperty(
        name="輔助物件線框顯示",
        description="將反光板、牆、光板之類輔助物體，在 3D 視圖中改為線框，"
                    "且不影響算圖",
        default=True,
        update=_update_wire_helpers,
    )


classes = (CL12Settings,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cl12 = bpy.props.PointerProperty(type=CL12Settings)


def unregister():
    global _backend_cache
    _backend_cache = None
    del bpy.types.Scene.cl12
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
