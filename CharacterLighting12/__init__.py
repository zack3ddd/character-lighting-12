# SPDX-License-Identifier: GPL-3.0-or-later
"""Character Lighting 12 — 12 種角色打光預設。

把 12 個打光範例做成一鍵套用的預設，並依主體尺寸自動縮放距離與強度。
設計文件見 _dev/PRESET_SPEC.md。
"""

bl_info = {
    "name": "Character Lighting 12",
    "author": "Zack (zack3d.art)",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar > Lighting",
    "description": "12 character lighting presets that scale to your subject.",
    "doc_url": "https://github.com/zack3ddd/character-lighting-12",
    "category": "Lighting",
}

import importlib

from . import builder, domain, extract, i18n, operators, presets, previews, properties, tags, ui

_MODULES = (tags, i18n, presets, builder, extract, domain, properties, previews, operators, ui)

if "bpy" in locals():
    for module in _MODULES:
        importlib.reload(module)

import bpy


def register():
    properties.register()
    previews.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    previews.unregister()
    properties.unregister()
    presets.invalidate()


if __name__ == "__main__":
    register()
