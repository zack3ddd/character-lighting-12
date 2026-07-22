# SPDX-License-Identifier: GPL-3.0-or-later
"""把場景裡調整過的燈光讀回預設格式。

builder.py 的逆運算。阿哲在 Blender 裡把燈拖到滿意之後，按「更新這個預設」
就會走到這裡——所以這兩個模組的縮放規則必須永遠對稱，改一邊要改另一邊。
"""

import math

import bpy
from mathutils import Vector

from . import tags

SUPPORTED_PRIMITIVES = ("PLANE", "CUBE", "CYLINDER", "UV_SPHERE", "TORUS",
                        "QUAD", "MESH")


def _degrees(euler):
    return [round(math.degrees(value), 4) for value in euler]


def _round_vector(vector, digits=6):
    return [round(value, digits) for value in vector]


# ---------------------------------------------------------------- 材質回讀

def _find_node(node_tree, bl_idname):
    for node in node_tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return None


def tree_socket(node, name):
    """節點的接點名稱會隨 Blender 版本改（例如 Transmission → Transmission Weight），
    取不到就回 None，由呼叫端用預設值，不要讓整個存檔失敗。"""
    for candidate in (name if isinstance(name, tuple) else (name,)):
        socket = node.inputs.get(candidate)
        if socket is not None:
            return socket
    return None


def _read_ramp(node):
    return {
        "interpolation": node.color_ramp.interpolation,
        "stops": [
            {"pos": round(element.position, 6),
             "color": [round(component, 6) for component in element.color]}
            for element in node.color_ramp.elements
        ],
    }


def _read_mapping(node_tree):
    node = _find_node(node_tree, "ShaderNodeMapping")
    if node is None:
        return {"loc": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1],
                "vector_type": "POINT", "coord": "Generated"}

    # 找出 Mapping 的 Vector 輸入實際接的是 Texture Coordinate 的哪個輸出。
    coord = "Generated"
    for link in node_tree.links:
        if link.to_node == node and link.to_socket.name == "Vector":
            if link.from_node.bl_idname == "ShaderNodeTexCoord":
                coord = link.from_socket.name
            break

    # NORMAL / VECTOR 模式下用不到的接點會從 inputs 消失，取值要防呆。
    def socket(name, fallback):
        item = node.inputs.get(name)
        return item.default_value if item is not None else fallback

    return {
        "loc": _round_vector(socket("Location", (0.0, 0.0, 0.0))),
        "rot": _degrees(socket("Rotation", (0.0, 0.0, 0.0))),
        "scale": _round_vector(socket("Scale", (1.0, 1.0, 1.0))),
        "vector_type": node.vector_type,
        "coord": coord,
    }


def _read_bright_contrast(node_tree):
    node = _find_node(node_tree, "ShaderNodeBrightContrast")
    if node is None:
        return None
    return {
        "brightness": round(node.inputs["Bright"].default_value, 6),
        "contrast": round(node.inputs["Contrast"].default_value, 6),
    }


def read_material(obj, k):
    """回傳 (material_dict, warning_or_None)。"""
    if not obj.data or not obj.data.materials or obj.data.materials[0] is None:
        return {"recipe": "none"}, None

    material = obj.data.materials[0]
    if not material.use_nodes:
        return {"recipe": "none"}, None

    tree = material.node_tree
    volume = _find_node(tree, "ShaderNodeVolumePrincipled")
    if volume is not None:
        # density 是每單位長度，抽取時要把 k 乘回去（builder 除掉的）。
        return {
            "recipe": "volume",
            "color": _round_vector(volume.inputs["Color"].default_value[:3]),
            "density": round(volume.inputs["Density"].default_value * k, 8),
        }, None

    emission = _find_node(tree, "ShaderNodeEmission")
    if emission is None:
        bsdf = _find_node(tree, "ShaderNodeBsdfPrincipled")
        if bsdf is not None:
            data = {"recipe": "principled"}
            for key, field, default in (
                ("Base Color", "base_color", (0.8, 0.8, 0.8)),
                ("Metallic", "metallic", 0.0),
                ("Roughness", "roughness", 0.5),
                ("Alpha", "alpha", 1.0),
                (("Transmission Weight", "Transmission"), "transmission", 0.0),
                ("IOR", "ior", 1.5),
            ):
                socket = tree_socket(bsdf, key)
                value = default if socket is None else socket.default_value
                if field == "base_color":
                    data[field] = _round_vector(tuple(value)[:3])
                else:
                    data[field] = round(float(value), 6)
            if hasattr(material, "blend_method"):
                data["blend_method"] = material.blend_method

            extra = [node.bl_idname for node in tree.nodes
                     if node.bl_idname not in ("ShaderNodeBsdfPrincipled",
                                               "ShaderNodeOutputMaterial")]
            warning = None
            if extra:
                warning = ("%s 的材質除了 Principled 之外還接了其他節點，"
                           "只會存下 Principled 本身的數值" % obj.name)
            return data, warning

        return {"recipe": "UNSUPPORTED"}, (
            "%s 的材質不是本外掛支援的類型，存不進預設" % obj.name
        )

    strength = round(emission.inputs["Strength"].default_value, 6)
    ramp = _find_node(tree, "ShaderNodeValToRGB")

    if ramp is None:
        return {
            "recipe": "emission",
            "color": _round_vector(emission.inputs["Color"].default_value[:3]),
            "strength": strength,
        }, None

    bright_contrast = _read_bright_contrast(tree)

    gradient = _find_node(tree, "ShaderNodeTexGradient")
    if gradient is not None:
        data = {
            "recipe": "gradient_emission",
            "gradient_type": gradient.gradient_type,
            "mapping": _read_mapping(tree),
            "ramp": _read_ramp(ramp),
            "strength": strength,
        }
        if bright_contrast:
            data["bright_contrast"] = bright_contrast
        return data, None

    magic = _find_node(tree, "ShaderNodeTexMagic")
    if magic is not None:
        data = {
            "recipe": "magic_emission",
            "magic": {
                "depth": magic.turbulence_depth,
                "scale": round(magic.inputs["Scale"].default_value, 6),
                "distortion": round(magic.inputs["Distortion"].default_value, 6),
            },
            "mapping": _read_mapping(tree),
            "ramp": _read_ramp(ramp),
            "strength": strength,
        }
        if bright_contrast:
            data["bright_contrast"] = bright_contrast
        return data, None

    return {"recipe": "UNSUPPORTED"}, (
        "%s 用了本外掛不支援的節點組合（有 ColorRamp 但沒有 Gradient/Magic 貼圖）" % obj.name
    )


# ---------------------------------------------------------------- 物件回讀

def _read_modifiers(obj):
    """回傳 (modifiers, warning)。目前只支援 Array，其餘出警告不靜默略過。"""
    modifiers = []
    warning = None
    for modifier in obj.modifiers:
        if modifier.type == "ARRAY":
            modifiers.append({
                "type": "ARRAY",
                "count": modifier.count,
                "relative_offset": _round_vector(modifier.relative_offset_displace),
            })
        else:
            warning = warning or (
                "%s 上的「%s」修改器存不進預設，套用時不會出現" % (obj.name, modifier.type)
            )
    return modifiers, warning


def _read_visibility(obj):
    """只記錄「關掉」的項目，全開就不寫，讓 JSON 保持乾淨。"""
    visibility = {}
    for key, attribute in (
        ("camera", "visible_camera"),
        ("diffuse", "visible_diffuse"),
        ("glossy", "visible_glossy"),
        ("transmission", "visible_transmission"),
        ("volume_scatter", "visible_volume_scatter"),
        ("shadow", "visible_shadow"),
    ):
        if hasattr(obj, attribute) and not getattr(obj, attribute):
            visibility[key] = False
    return visibility


def _dimensions_without_modifiers(obj):
    """量物件的局部尺寸，但先把修改器關掉。

    `obj.dimensions` 讀的是套用修改器之後的包圍盒——有 Array 的物件量到的是
    整排的總長，不是單片的尺寸。builder 那邊也是這樣量的，兩邊要一致。
    """
    hidden = [modifier for modifier in obj.modifiers if modifier.show_viewport]
    for modifier in hidden:
        modifier.show_viewport = False
    if hidden:
        bpy.context.view_layer.update()
    try:
        return obj.dimensions.copy()
    finally:
        for modifier in hidden:
            modifier.show_viewport = True


MAX_CUSTOM_VERTS = 4000


def _guess_primitive(obj):
    """判斷這個 mesh 要用哪種方式存。

    外掛自己生的物件有標記，直接用。使用者自己加的東西——自製的燈罩、
    地板、道具——一律走 `MESH`（照抄頂點與面），這樣他在 Blender 裡做什麼
    都存得回預設，不必遷就那幾種基本形。
    """
    recorded = obj.get(tags.PRIMITIVE)
    if recorded in SUPPORTED_PRIMITIVES:
        return recorded
    if obj.type != "MESH" or not obj.data.vertices:
        return None
    if len(obj.data.vertices) > MAX_CUSTOM_VERTS:
        return None  # 太重了，存進 JSON 會把預設檔撐爆
    return "MESH"


def read_light(obj, domain, k):
    data = obj.data
    local = domain.matrix_world.inverted() @ obj.matrix_world

    spec = {
        "kind": "LIGHT",
        "role": obj.get(tags.ROLE, ""),
        "name": obj.name,
        "light_type": data.type,
        "pos": _round_vector(local.translation / k),
        "rot": _degrees(local.to_euler()),
        "color": _round_vector(data.color),
        "energy": round(data.energy if data.type == "SUN" else data.energy / (k ** 2), 6),
    }

    shape = {}
    if data.type == "AREA":
        shape["area_shape"] = data.shape
        shape["size"] = round(data.size / k, 6)
        if data.shape in {"RECTANGLE", "ELLIPSE"}:
            shape["size_y"] = round(data.size_y / k, 6)
    elif data.type == "SPOT":
        shape["size"] = round(data.shadow_soft_size / k, 6)
        shape["spot_size"] = round(math.degrees(data.spot_size), 4)
        shape["spot_blend"] = round(data.spot_blend, 4)
    elif data.type == "POINT":
        shape["size"] = round(data.shadow_soft_size / k, 6)
    elif data.type == "SUN":
        shape["sun_angle"] = round(math.degrees(data.angle), 4)
    spec["shape"] = shape
    return spec, None


def read_mesh(obj, domain, k):
    primitive = _guess_primitive(obj)
    if primitive is None:
        if obj.type == "MESH" and len(obj.data.vertices) > MAX_CUSTOM_VERTS:
            return None, (
                "%s 有 %d 個頂點，超過 %d 存不進預設（請先減面）"
                % (obj.name, len(obj.data.vertices), MAX_CUSTOM_VERTS)
            )
        return None, ("%s 沒有可用的網格，沒有存進預設" % obj.name)

    local = domain.matrix_world.inverted() @ obj.matrix_world
    material, warning = read_material(obj, k)

    if primitive in ("QUAD", "MESH"):
        # 直接存頂點與面（含物件 scale），不走 dims 那條路。
        spec = {
            "kind": "MESH",
            "role": obj.get(tags.ROLE, ""),
            "name": obj.name,
            "primitive": primitive,
            "pos": _round_vector(local.translation / k),
            "rot": _degrees(local.to_euler()),
            "verts": [
                _round_vector(Vector(
                    (v.co.x * obj.scale.x, v.co.y * obj.scale.y, v.co.z * obj.scale.z)
                ) / k, 9)
                for v in obj.data.vertices
            ],
            "material": material,
        }
        if primitive == "MESH":
            spec["faces"] = [list(polygon.vertices) for polygon in obj.data.polygons]

        # ⚠️ _read_modifiers 回傳的是 (清單, 警告) 兩個值，一定要拆開。
        # 忘了拆的話會把整個 tuple 寫進 JSON 變成 [[...], null]，
        # 而且 tuple 永遠有兩個元素、永遠為真，連「沒有修改器」的物件也會中招。
        # 套用時就會拿 list 當 dict 用而崩潰。
        modifiers, modifier_warning = _read_modifiers(obj)
        if modifiers:
            spec["modifiers"] = modifiers
        warning = warning or modifier_warning

        visibility = _read_visibility(obj)
        if visibility:
            spec["visibility"] = visibility
        return spec, warning

    # dims 的定義是「關掉修改器之後的局部尺寸 ÷ ref」，見 PRESET_SPEC 第 3.2 節。
    # 外掛自己生的物件直接讀建立時記下的值；使用者手動加的才現場量。
    dims = obj.get(tags.BASE_DIMS)
    if dims:
        dims = [round(value, 6) for value in dims]
    else:
        dims = _round_vector(Vector(_dimensions_without_modifiers(obj)) / k)

    spec = {
        "kind": "MESH",
        "role": obj.get(tags.ROLE, ""),
        "name": obj.name,
        "primitive": primitive,
        "pos": _round_vector(local.translation / k),
        "rot": _degrees(local.to_euler()),
        "dims": dims,
        "material": material,
    }

    modifiers, modifier_warning = _read_modifiers(obj)
    if modifiers:
        spec["modifiers"] = modifiers
    warning = warning or modifier_warning

    visibility = _read_visibility(obj)
    if visibility:
        spec["visibility"] = visibility

    return spec, warning


def extract(context, domain, base_preset):
    """讀出光域目前的狀態，回傳 (preset_dict, warnings)。

    base_preset 提供 id/name/desc/tip 這些不在場景裡的欄位。
    """
    k = float(domain.get(tags.DOMAIN_REF) or 1.0)
    if k <= 0:
        k = 1.0

    warnings = []
    objects = []

    # 收光域底下所有東西，不只有標記過的——使用者自己加的燈也要收。
    for obj in sorted(domain.children_recursive, key=lambda item: item.name):
        if tags.DOMAIN in obj:
            continue
        if obj.type == "LIGHT":
            spec, warning = read_light(obj, domain, k)
        elif obj.type == "MESH":
            spec, warning = read_mesh(obj, domain, k)
        else:
            spec, warning = None, (
                "%s 是 %s，不是燈光或基本形，沒有存進預設" % (obj.name, obj.type)
            )
        if warning:
            warnings.append(warning)
        if spec:
            objects.append(spec)

    world = context.scene.world
    world_data = {"color": [0.0, 0.0, 0.0], "strength": 1.0}
    if world and world.use_nodes:
        background = _find_node(world.node_tree, "ShaderNodeBackground")
        if background is not None:
            world_data = {
                "color": _round_vector(background.inputs["Color"].default_value[:3]),
                "strength": round(background.inputs["Strength"].default_value, 6),
            }

    preset = dict(base_preset)
    preset["objects"] = objects
    preset["world"] = world_data
    return preset, warnings
