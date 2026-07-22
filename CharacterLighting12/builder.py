# SPDX-License-Identifier: GPL-3.0-or-later
"""依預設資料生成燈光物件。

這個模組是整個外掛的物理核心，縮放規則的依據見 _dev/PRESET_SPEC.md 第 1 節。
改這裡之前先讀那份規格。
"""

import math

import bpy
from mathutils import Vector

from . import tags

# 這兩種不是「基本形 ＋ 縮放」，而是直接照抄頂點與面。
EXPLICIT_PRIMITIVES = {"QUAD", "MESH"}

# ---------------------------------------------------------------- 基本形

_PRIMITIVE_BUILDERS = {
    "PLANE": lambda: bpy.ops.mesh.primitive_plane_add(size=1.0),
    "CUBE": lambda: bpy.ops.mesh.primitive_cube_add(size=1.0),
    "CYLINDER": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1.0),
    "UV_SPHERE": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5),
    "TORUS": None,  # 需要參數，另外處理
}


def _add_explicit_mesh(verts, faces, k):
    """用明確的頂點與面建網格。

    有些形狀用「基本形 ＋ 逐軸縮放」根本表達不出來，硬湊會壞掉：
    百葉窗的葉片是長寬比 300:1 的斜薄帶（用平面會疊在一起、用方塊會堵死光），
    網紅的牆是倒角過的包覆殼，復古的牆是只有四個面的開放盒子——
    後兩者被當成實心方塊會把正面封起來，多出不該有的反光。

    這種一律照抄原始網格。座標已含原本的 scale，所以物件 scale 保持 1。
    使用者自己做的模型掛進光域後，也是走這條路存回預設。
    """
    mesh = bpy.data.meshes.new("CL12_Mesh")
    mesh.from_pydata([tuple(Vector(v) * k) for v in verts], [], [tuple(f) for f in faces])
    mesh.update()
    obj = bpy.data.objects.new("CL12_Mesh", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _add_primitive(primitive, args):
    """生成一個尺寸為 1 的基本形並回傳物件。實際尺寸稍後用 dimensions 設定。"""
    if primitive == "TORUS":
        major = 0.5
        minor = major * float(args.get("major_ratio", 0.25))
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor)
    else:
        builder = _PRIMITIVE_BUILDERS.get(primitive)
        if builder is None:
            raise ValueError("未知的基本形：%s" % primitive)
        builder()
    return bpy.context.object


# ---------------------------------------------------------------- 材質

def _set_socket(node, name, value):
    """有這個接點才設。

    接點會隨節點模式增減，也會隨 Blender 版本改名
    （4.0 把 Principled 的 Transmission 改叫 Transmission Weight），
    所以 name 可以給多個候選，取第一個存在的。
    """
    for candidate in (name if isinstance(name, tuple) else (name,)):
        socket = node.inputs.get(candidate)
        if socket is not None:
            socket.default_value = value
            return


def _new_material(name, use_nodes=True):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = use_nodes
    if use_nodes:
        mat.node_tree.nodes.clear()
    return mat


def _build_ramp(node_tree, ramp_data):
    ramp = node_tree.nodes.new("ShaderNodeValToRGB")
    stops = ramp_data.get("stops") or []
    ramp.color_ramp.interpolation = ramp_data.get("interpolation", "LINEAR")
    elements = ramp.color_ramp.elements
    # ColorRamp 一定有兩個預設色標，不能全刪；先塞滿再刪多的。
    for index, stop in enumerate(stops):
        element = elements[index] if index < len(elements) else elements.new(0.0)
        element.position = float(stop["pos"])
        element.color = tuple(stop["color"])
    while len(elements) > max(len(stops), 1):
        elements.remove(elements[len(elements) - 1])
    return ramp


def _build_mapping(node_tree, mapping_data):
    """回傳 (texcoord, mapping) 兩個節點，已接好。

    `coord` 與 `vector_type` 不能寫死——原檔的「漸層」光板走的是
    Texture Coordinate 的 Object 輸出 ＋ Mapping 的 NORMAL 模式，
    寫死成 Generated/POINT 會讓那組的漸層方向整個跑掉，而那片板子
    是該組唯一的光源。
    """
    texcoord = node_tree.nodes.new("ShaderNodeTexCoord")
    mapping = node_tree.nodes.new("ShaderNodeMapping")
    mapping.vector_type = mapping_data.get("vector_type", "POINT")

    # ⚠️ vector_type 設成 NORMAL / VECTOR 時，Blender 會把用不到的接點
    # （Location、有時還有 Scale）從 inputs 拿掉，照名稱直接取會丟 KeyError。
    _set_socket(mapping, "Location", tuple(mapping_data.get("loc", (0, 0, 0))))
    _set_socket(mapping, "Rotation", tuple(
        math.radians(v) for v in mapping_data.get("rot", (0, 0, 0))))
    _set_socket(mapping, "Scale", tuple(mapping_data.get("scale", (1, 1, 1))))

    coord = mapping_data.get("coord", "Generated")
    if coord not in texcoord.outputs:
        coord = "Generated"
    node_tree.links.new(texcoord.outputs[coord], mapping.inputs["Vector"])
    return texcoord, mapping


def build_material(recipe_data, name):
    """依 PRESET_SPEC 第 3.3 節的五種配方建材質。回傳 material 或 None。"""
    recipe = recipe_data.get("recipe", "none")

    if recipe in ("none", "UNSUPPORTED"):
        return None

    mat = _new_material(name)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    output = nodes.new("ShaderNodeOutputMaterial")

    if recipe == "emission":
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = tuple(recipe_data["color"]) + (1.0,)
        emission.inputs["Strength"].default_value = float(recipe_data["strength"])
        links.new(emission.outputs["Emission"], output.inputs["Surface"])

    elif recipe == "principled":
        # 給遮擋板、反光板這類「不發光但要有質感」的物件用。
        # 百葉窗的葉片就是靠 Alpha 讓一部分光透過去，條紋才不會死黑。
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        _set_socket(bsdf, "Base Color", tuple(recipe_data.get("base_color", (0.8,) * 3)) + (1.0,))
        _set_socket(bsdf, "Metallic", float(recipe_data.get("metallic", 0.0)))
        _set_socket(bsdf, "Roughness", float(recipe_data.get("roughness", 0.5)))
        _set_socket(bsdf, "Alpha", float(recipe_data.get("alpha", 1.0)))
        _set_socket(bsdf, ("Transmission Weight", "Transmission"),
                    float(recipe_data.get("transmission", 0.0)))
        _set_socket(bsdf, "IOR", float(recipe_data.get("ior", 1.5)))
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        if hasattr(mat, "blend_method"):
            mat.blend_method = recipe_data.get("blend_method", "HASHED")

    elif recipe == "volume":
        volume = nodes.new("ShaderNodeVolumePrincipled")
        volume.inputs["Color"].default_value = tuple(recipe_data["color"]) + (1.0,)
        volume.inputs["Density"].default_value = float(recipe_data["density"])
        links.new(volume.outputs["Volume"], output.inputs["Volume"])

    elif recipe in ("gradient_emission", "magic_emission"):
        _, mapping = _build_mapping(mat.node_tree, recipe_data.get("mapping", {}))

        if recipe == "gradient_emission":
            texture = nodes.new("ShaderNodeTexGradient")
            texture.gradient_type = recipe_data.get("gradient_type", "LINEAR")
            texture_output = texture.outputs["Color"]
        else:
            magic = recipe_data.get("magic", {})
            texture = nodes.new("ShaderNodeTexMagic")
            texture.turbulence_depth = int(magic.get("depth", 2))
            texture.inputs["Scale"].default_value = float(magic.get("scale", 5.0))
            texture.inputs["Distortion"].default_value = float(magic.get("distortion", 1.0))
            texture_output = texture.outputs["Color"]

        links.new(mapping.outputs["Vector"], texture.inputs["Vector"])
        ramp = _build_ramp(mat.node_tree, recipe_data.get("ramp", {}))
        links.new(texture_output, ramp.inputs["Fac"])

        colour_output = ramp.outputs["Color"]

        # 原檔的夕陽漸層球在 ColorRamp 後面還夾了一個 Bright/Contrast。
        # 選填，沒有這個欄位就不建這個節點。
        bright_contrast = recipe_data.get("bright_contrast")
        if bright_contrast:
            adjust = nodes.new("ShaderNodeBrightContrast")
            adjust.inputs["Bright"].default_value = float(
                bright_contrast.get("brightness", 0.0))
            adjust.inputs["Contrast"].default_value = float(
                bright_contrast.get("contrast", 0.0))
            links.new(colour_output, adjust.inputs["Color"])
            colour_output = adjust.outputs["Color"]

        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Strength"].default_value = float(recipe_data["strength"])
        links.new(colour_output, emission.inputs["Color"])
        links.new(emission.outputs["Emission"], output.inputs["Surface"])

    else:
        raise ValueError("未知的材質配方：%s" % recipe)

    # 節點位置只影響編輯器裡好不好看，但學生會打開來看，所以稍微排一下。
    for index, node in enumerate(reversed(nodes)):
        node.location = (index * -220, 0)

    return mat


# ---------------------------------------------------------------- 燈光

def _apply_light_shape(light, shape, k):
    """套用形狀參數。角度類不縮放，長度類乘 k。"""
    light_type = light.type

    if light_type == "AREA":
        light.shape = shape.get("area_shape", "SQUARE")
        light.size = float(shape.get("size", 1.0)) * k
        if light.shape in {"RECTANGLE", "ELLIPSE"}:
            light.size_y = float(shape.get("size_y", shape.get("size", 1.0))) * k
    elif light_type == "SPOT":
        light.shadow_soft_size = float(shape.get("size", 0.25)) * k
        light.spot_size = math.radians(float(shape.get("spot_size", 45.0)))
        light.spot_blend = float(shape.get("spot_blend", 0.15))
    elif light_type == "POINT":
        light.shadow_soft_size = float(shape.get("size", 0.25)) * k
    elif light_type == "SUN":
        light.angle = math.radians(float(shape.get("sun_angle", 0.526)))


def build_light(spec, k, preset_id):
    light_type = spec["light_type"]
    data = bpy.data.lights.new(name=spec["name"], type=light_type)
    obj = bpy.data.objects.new(spec["name"], data)

    data.color = tuple(spec["color"])

    # SUN 的 energy 是輻照度(W/m²)，與距離無關，不縮放。其餘是總功率(W)，要補 k²。
    if light_type == "SUN":
        data.energy = float(spec["energy"])
    else:
        data.energy = float(spec["energy"]) * (k ** 2)

    _apply_light_shape(data, spec.get("shape", {}), k)

    obj.rotation_euler = tuple(math.radians(v) for v in spec["rot"])
    # SUN 只有角度有意義，位置隨便擺一個好看的地方就好，不參與縮放。
    if light_type == "SUN":
        obj.location = Vector(spec["pos"]) * k if spec.get("pos") else Vector((0, 0, 0))
    else:
        obj.location = Vector(spec["pos"]) * k

    tags.mark(obj, preset_id, spec.get("role", ""))
    obj[tags.BASE_ENERGY] = data.energy
    obj[tags.BASE_COLOR] = list(data.color)
    return obj


# ---------------------------------------------------------------- Mesh

def build_mesh(spec, k, preset_id):
    primitive = spec["primitive"]
    if primitive in EXPLICIT_PRIMITIVES:
        # QUAD 是 MESH 的特例：四個頂點、一個面。
        faces = spec.get("faces") or [(0, 1, 3, 2)]
        obj = _add_explicit_mesh(spec["verts"], faces, k)
    else:
        obj = _add_primitive(primitive, spec.get("primitive_args", {}))

    obj.name = spec["name"]
    if obj.data:
        obj.data.name = spec["name"]

    # 先清掉 primitive_add 留下的變換，再自己設定。
    obj.location = Vector(spec["pos"]) * k
    obj.rotation_euler = tuple(math.radians(v) for v in spec["rot"])
    obj.scale = (1.0, 1.0, 1.0)

    material_data = dict(spec.get("material") or {"recipe": "none"})

    # 體積霧的 density 是「每單位長度」——霧箱放大 k 倍，光程也變 k 倍，要除回去。
    if material_data.get("recipe") == "volume" and k:
        material_data["density"] = float(material_data["density"]) / k

    material = build_material(material_data, "CL12_%s_%s" % (preset_id, spec["name"]))
    if material:
        obj.data.materials.append(material)

    for modifier_spec in spec.get("modifiers", []):
        if modifier_spec["type"] == "ARRAY":
            modifier = obj.modifiers.new("Array", "ARRAY")
            modifier.count = int(modifier_spec["count"])
            modifier.relative_offset_displace = tuple(modifier_spec["relative_offset"])

    visibility = spec.get("visibility") or {}
    for key, attribute in (
        ("camera", "visible_camera"),
        ("diffuse", "visible_diffuse"),
        ("glossy", "visible_glossy"),
        ("transmission", "visible_transmission"),
        ("volume_scatter", "visible_volume_scatter"),
        ("shadow", "visible_shadow"),
    ):
        if key in visibility and hasattr(obj, attribute):
            setattr(obj, attribute, bool(visibility[key]))

    # 明確頂點的座標已經是最終尺寸，不需要也不可以再套 dims。
    if primitive not in EXPLICIT_PRIMITIVES:
        obj[tags.BASE_DIMS] = list(spec["dims"])
    tags.mark(obj, preset_id, spec.get("role", ""))
    obj[tags.PRIMITIVE] = spec["primitive"]
    if spec.get("may_intersect"):
        obj[tags.MAY_INTERSECT] = True
    return obj


def world_bounds(obj, depsgraph):
    """物件套用修改器後的世界包圍盒。取不到幾何回 None。"""
    evaluated = obj.evaluated_get(depsgraph)
    try:
        mesh = evaluated.to_mesh()
    except RuntimeError:
        return None
    if mesh is None or not mesh.vertices:
        return None
    matrix = evaluated.matrix_world
    points = [matrix @ vertex.co for vertex in mesh.vertices]
    lo = Vector((min(p.x for p in points), min(p.y for p in points),
                 min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points),
                 max(p.z for p in points)))
    evaluated.to_mesh_clear()
    return lo, hi


def push_out_of_subject(context, objects, subject_lo, subject_hi, margin=0.02):
    """把切穿主體的輔助物件往外推，直到不再相交。回傳被推開的物件名稱。

    ⚠️ **完全包住主體的物件不能推**。復古的霧氣方塊與夕陽的漸層球
    本來就該把角色包在裡面（霧要有空氣感、天空罩要罩住整個場景），
    推走它們那兩組就毀了。只有「部分相交」才是穿模。

    會需要這一段，是因為預設是圍著一個高瘦角色擺的，換成寬扁的角色時
    ref 抓到的是寬度，整組燈用一個比身高大很多的尺度展開，
    貼得近的輔助物件就會插進身體裡。
    """
    depsgraph = context.evaluated_depsgraph_get()
    centre = (subject_lo + subject_hi) * 0.5
    moved = []

    for obj in objects:
        if obj.type != "MESH":
            continue
        if obj.get(tags.MAY_INTERSECT):
            continue  # 原檔本來就相交（地板要貼著腳、霧要包住人），推走反而是錯的
        bounds = world_bounds(obj, depsgraph)
        if bounds is None:
            continue
        lo, hi = bounds

        # 只有「明顯」插進去才算穿模。地板貼著腳、牆擦過肩膀這種
        # 差一絲的接觸是正常的，推開反而會讓畫面變怪。
        depths = [min(hi[i], subject_hi[i]) - max(lo[i], subject_lo[i])
                  for i in range(3)]
        span = max(subject_hi - subject_lo)
        if min(depths) <= span * 0.02:
            continue

        enclosing = all(lo[i] <= subject_lo[i] and hi[i] >= subject_hi[i]
                        for i in range(3))
        if enclosing:
            continue  # 霧、天空罩——本來就該包住

        direction = ((lo + hi) * 0.5) - centre
        if direction.length < 1e-6:
            direction = Vector((0.0, -1.0, 0.0))  # 正好同心就往鏡頭方向退
        direction.normalize()

        # 沿 direction 平移，找出「任一軸分離」所需的最小距離。
        distances = []
        for axis in range(3):
            component = direction[axis]
            if abs(component) < 1e-9:
                continue
            if component > 0:
                distances.append((subject_hi[axis] - lo[axis]) / component)
            else:
                distances.append((subject_lo[axis] - hi[axis]) / component)
        distances = [d for d in distances if d > 0]
        if not distances:
            continue

        obj.location = obj.location + direction * (min(distances) + margin * span)
        moved.append(obj.name)

    if moved:
        context.view_layer.update()
    return moved


def apply_mesh_dimensions(obj, k):
    """dimensions 必須在物件已在 depsgraph 中才可靠，所以獨立成一步。

    兩件事要注意：

    1. **`obj.dimensions` 讀的是套用修改器「之後」的包圍盒。** 有 Array 的物件
       （百葉窗）拿它去反算縮放是循環的——量到的是 50 片的總長度，卻要拿來對
       單片的目標尺寸。所以量之前先把修改器關掉，量完再開回來。
       `dims` 的定義因此是**修改器之前的基礎尺寸**。
    2. 逐軸處理：平面在 Z 軸的厚度本來就是 0，那種軸要維持原本的 scale——
       不能拿 0 去算比例，也不能把 scale 設成 0（法線會壞掉，Cycles 算不出東西）。
    """
    dims = obj.get(tags.BASE_DIMS)
    if not dims:
        return

    hidden = []
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            modifier.show_viewport = False
            hidden.append(modifier)

    if hidden:
        bpy.context.view_layer.update()

    try:
        target = Vector(tuple(dims)) * k
        base = obj.dimensions.copy()
        scale = list(obj.scale)
        # 目標厚度是 0 時（例如復古那塊壓扁的反光地板）不能放著不管，
        # 否則會留下一整個單位的厚度；但也不能真的縮到 0（法線會壞掉）。
        floor = 1e-4 * k

        for axis in range(3):
            if abs(base[axis]) < 1e-9:
                continue  # 基礎形在這一軸本來就是扁的，沒得縮
            scale[axis] = max(abs(target[axis]), floor) / base[axis] * scale[axis]

        obj.scale = Vector(scale)
    finally:
        for modifier in hidden:
            modifier.show_viewport = True
