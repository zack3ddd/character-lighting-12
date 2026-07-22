# SPDX-License-Identifier: GPL-3.0-or-later
"""光域：決定燈光範圍的空物體。

使用者選好主體後，這裡量出主體的包圍盒，生成一個置中的 Empty。
之後所有燈光都 parent 到它——轉它就是整組燈繞著主體轉，縮它就是距離與強度一起縮。
"""

import bpy
from mathutils import Matrix, Vector

from . import tags

COLLECTION_NAME = "Character Lighting 12"


def evaluated_bbox(context, objects):
    """算一群物件套用 modifier 之後的世界包圍盒。

    回傳 (center, size, max_dim, lo, hi)，沒有可用幾何時回 None。
    用 evaluated 幾何而不是 base mesh，否則有 Subdivision 的角色會量錯。
    """
    depsgraph = context.evaluated_depsgraph_get()
    minimum = Vector((float("inf"),) * 3)
    maximum = Vector((float("-inf"),) * 3)
    found = False

    for obj in objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        try:
            mesh = evaluated.to_mesh()
        except RuntimeError:
            mesh = None
        if mesh is None:
            continue
        matrix = evaluated.matrix_world
        for vertex in mesh.vertices:
            world = matrix @ vertex.co
            minimum = Vector(map(min, minimum, world))
            maximum = Vector(map(max, maximum, world))
            found = True
        evaluated.to_mesh_clear()

    if not found:
        return None

    size = maximum - minimum
    center = (maximum + minimum) * 0.5
    return center, size, max(size), minimum, maximum


def subject_candidates(context):
    """選取物件中真正能當主體的那些（排除本外掛自己生成的東西）。"""
    return [
        obj for obj in context.selected_objects
        if not tags.is_ours(obj) and tags.DOMAIN not in obj
    ]


def store_subject_bounds(domain, lo, hi):
    domain[tags.DOMAIN_SUBJECT_LO] = list(lo)
    domain[tags.DOMAIN_SUBJECT_HI] = list(hi)


def subject_bounds(domain):
    """回傳 (lo, hi)，沒記錄過就用 ref 回推一個立方體當備案。"""
    lo = domain.get(tags.DOMAIN_SUBJECT_LO)
    hi = domain.get(tags.DOMAIN_SUBJECT_HI)
    if lo and hi:
        return Vector(tuple(lo)), Vector(tuple(hi))
    half = float(domain.get(tags.DOMAIN_REF) or 1.0) * 0.5
    centre = Vector(domain.location)
    return centre - Vector((half,) * 3), centre + Vector((half,) * 3)


def create_domain(context, center, ref, subject_names=(), from_example=False):
    collection = tags.collection_for(context, COLLECTION_NAME)

    name = "CL12 範例光域 Example Domain" if from_example else "CL12 光域 Light Domain"
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "CUBE"
    empty.empty_display_size = ref * 0.5
    empty.location = center
    empty.show_in_front = True

    empty[tags.DOMAIN] = True
    empty[tags.DOMAIN_REF] = ref
    empty[tags.DOMAIN_SUBJECT] = list(subject_names)
    empty[tags.APPLIED_INTENSITY] = 1.0
    empty[tags.APPLIED_TEMPERATURE] = 0.0
    empty[tags.APPLIED_DISTANCE] = 1.0
    if from_example:
        empty[tags.DOMAIN_FROM_EXAMPLE] = True

    collection.objects.link(empty)
    return empty


def resize_domain(domain, ref):
    """改變光域的參考尺寸，同時把顯示大小跟著改。

    注意：這裡只改 empty 本身，燈光不會自動跟著變——
    燈光要重新套用預設才會用新的 ref 生成。
    """
    domain[tags.DOMAIN_REF] = ref
    domain.empty_display_size = ref * 0.5


def link_to_domain(context, domain, objects):
    """把生成的物件收進集合並 parent 到光域。

    ⚠️ `matrix_parent_inverse` 必須是單位矩陣。builder 產出的 location
    是**相對於光域的座標**，要讓光域的位置與旋轉真的傳遞下去。
    若照一般「保持世界座標不動」的作法把它設成光域矩陣的逆，燈會被釘在
    世界原點附近，轉動光域也不會帶著燈跑——整個光域的意義就沒了。
    """
    collection = tags.collection_for(context, COLLECTION_NAME)
    for obj in objects:
        for existing in list(obj.users_collection):
            existing.objects.unlink(obj)
        collection.objects.link(obj)

    for obj in objects:
        obj.parent = domain
        obj.matrix_parent_inverse = Matrix.Identity(4)


def clear_domain_lights(domain):
    """刪掉光域底下所有本外掛生成的物件，光域本身留著。"""
    doomed = tags.domain_children(domain)
    for obj in doomed:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        # 資料塊沒人用了就一起清掉，免得檔案越存越肥。
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
    return len(doomed)
