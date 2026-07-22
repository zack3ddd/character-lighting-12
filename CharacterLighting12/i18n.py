# SPDX-License-Identifier: GPL-3.0-or-later
"""雙語。

規則跟阿哲其他外掛一致：介面跟隨 Blender 的語言設定——
英文顯示英文，簡體與繁體都顯示**繁體**中文。
預設檔裡的 name/desc/tip 也走這裡的 language() 判斷。
"""

import bpy

ZH = "zh"
EN = "en"


def language():
    """回傳 'zh' 或 'en'。"""
    try:
        locale = bpy.app.translations.locale or ""
    except AttributeError:
        return EN
    return ZH if locale.startswith("zh") else EN


def t(en, zh):
    """就地取用的雙語字串。給面板標題、說明文字這種不需要註冊翻譯的地方。"""
    return zh if language() == ZH else en
