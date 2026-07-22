# SPDX-License-Identifier: GPL-3.0-or-later
"""預設縮圖。

用 Blender 原生的 previews 機制註冊 thumbnails/ 底下的 PNG，
再包成 EnumProperty 給 template_icon_view 用。
"""

import os

import bpy
import bpy.utils.previews

from . import i18n, presets

_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
_THUMB_DIR = os.path.join(_ADDON_DIR, "thumbnails")

_collection = None
_items_cache = []


def _build_items():
    """回傳 EnumProperty 的 items。

    必須把結果存在模組層級的變數裡——Blender 的 EnumProperty callback
    如果讓回傳的字串被垃圾回收，介面會出現亂碼或直接崩潰。
    """
    global _items_cache

    items = []
    for index, data in enumerate(presets.ordered()):
        preset_id = data["id"]
        name = presets.localized(data, "name", i18n.language()) or preset_id
        icon_id = 0
        if _collection is not None:
            if preset_id in _collection:
                icon_id = _collection[preset_id].icon_id
            else:
                path = presets.thumbnail_path(data)
                if path and os.path.exists(path):
                    icon_id = _collection.load(preset_id, path, "IMAGE").icon_id
        items.append((preset_id, name, name, icon_id, index))

    if not items:
        items = [("NONE", i18n.t("No presets found", "找不到預設檔"), "", 0, 0)]

    _items_cache = items
    return _items_cache


def preset_items(self, context):
    return _build_items()


def _on_preview_change(self, context):
    context.scene.cl12.active_preset = self.cl12_preview


def refresh():
    """預設檔改過之後叫這個，讓縮圖牆重新讀一次。

    previews 的 collection 不能只清單一項再重載——Blender 會沿用舊的 icon_id
    畫出舊圖。整個 collection 重建最省事，12～20 張的量重載不會有感。
    """
    global _collection
    presets.invalidate()
    if _collection is not None:
        bpy.utils.previews.remove(_collection)
        _collection = bpy.utils.previews.new()
    _build_items()


def register():
    global _collection
    _collection = bpy.utils.previews.new()

    bpy.types.Scene.cl12_preview = bpy.props.EnumProperty(
        items=preset_items,
        name="",
        update=_on_preview_change,
    )


def unregister():
    global _collection, _items_cache
    del bpy.types.Scene.cl12_preview
    if _collection is not None:
        bpy.utils.previews.remove(_collection)
        _collection = None
    _items_cache = []
