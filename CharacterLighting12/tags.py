# SPDX-License-Identifier: GPL-3.0-or-later
"""物件標記。

外掛生成的每個東西都蓋上這些自訂屬性，回寫預設時才知道該收哪些物件、
以及每個物件原本是什麼。規格見 _dev/PRESET_SPEC.md 第 5 節。
"""

import bpy

PRESET = "cl12_preset"        # 這個物件屬於哪個預設
ROLE = "cl12_role"            # key / fill / rim / bounce / practical
PRIMITIVE = "cl12_primitive"  # MESH 才有，回寫時不用猜它原本是什麼基本形
MAY_INTERSECT = "cl12_may_intersect"  # 原檔本來就跟角色相交（地板、霧），防穿透要放過它

DOMAIN = "cl12_domain"        # 光域 empty 的識別
DOMAIN_REF = "cl12_ref"       # 光域的參考尺寸（= 主體最大邊長）
DOMAIN_SUBJECT = "cl12_subject_names"
DOMAIN_SUBJECT_LO = "cl12_subject_lo"   # 主體包圍盒（世界座標），防穿透要用
DOMAIN_SUBJECT_HI = "cl12_subject_hi"
DOMAIN_FROM_EXAMPLE = "cl12_domain_from_example"  # 範例自己的光域，移除範例時一起刪

# 全域滑桿：記錄「上次套用的值」，滑桿改變時算差額套上去，
# 這樣使用者手動微調過的數值不會被滑桿洗掉。
APPLIED_INTENSITY = "cl12_applied_intensity"
APPLIED_TEMPERATURE = "cl12_applied_temperature"
APPLIED_DISTANCE = "cl12_applied_distance"

BASE_ENERGY = "cl12_base_energy"
BASE_COLOR = "cl12_base_color"
BASE_DIMS = "cl12_base_dims"

PREVIEW_CAMERA = "cl12_preview_camera"  # 外掛建立的取景相機
EXAMPLE = "cl12_example"      # 範例資產的識別，移除範例時用

# 「這盞燈是外掛關掉的」。還原時只開有這個記號的——
# 使用者原本就自己關掉的燈不能被打開，他關掉是有原因的。
HIDDEN_BY_US = "cl12_hidden_by_addon"
OBJECT_HIDDEN_BY_US = "cl12_object_hidden_by_addon"


def mark(obj, preset_id, role=""):
    obj[PRESET] = preset_id
    obj[ROLE] = role


def is_ours(obj):
    return PRESET in obj


def find_domain(context):
    """回傳目前場景的光域。找不到回 None。

    優先找選取中的，其次找場景裡唯一的一個。有多個又沒選取時回 None，
    由呼叫端要求使用者自己指定——不要猜。
    """
    active = context.active_object
    if active is not None and DOMAIN in active:
        return active

    for obj in context.selected_objects:
        if DOMAIN in obj:
            return obj

    domains = [obj for obj in context.scene.objects if DOMAIN in obj]
    if len(domains) == 1:
        return domains[0]
    if len(domains) > 1:
        # 範例載入後會有兩顆光域（使用者自己的＋範例的），
        # 此時以範例那顆為準——因為使用者剛按下「載入範例」，正在看範例。
        example = [obj for obj in domains if DOMAIN_FROM_EXAMPLE in obj]
        if len(example) == 1:
            return example[0]
    return None


def domain_children(domain):
    """光域底下所有屬於本外掛的物件。"""
    return [obj for obj in domain.children_recursive if is_ours(obj)]


def collection_for(context, name):
    """取得（必要時建立）一個掛在場景根部的集合。"""
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if collection.name not in context.scene.collection.children:
        context.scene.collection.children.link(collection)
    return collection
