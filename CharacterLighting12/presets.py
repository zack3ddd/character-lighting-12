# SPDX-License-Identifier: GPL-3.0-or-later
"""預設檔的讀寫。

內建預設在外掛資料夾的 presets/，使用者自訂的存在 Blender 的使用者設定夾。
同 id 時使用者版本蓋過內建版本，但內建檔永遠不會被改寫——
這樣阿哲怎麼調都不會把出廠預設弄丟。
"""

import base64
import json
import os
import re
import time

import bpy

SCHEMA = 1

_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILTIN_DIR = os.path.join(_ADDON_DIR, "presets")

_cache = None


def user_dir():
    path = os.path.join(
        bpy.utils.user_resource("CONFIG", path="character_lighting_12", create=True),
        "presets",
    )
    os.makedirs(path, exist_ok=True)
    return path


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_dir(directory, is_user):
    found = {}
    if not os.path.isdir(directory):
        return found
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue
        path = os.path.join(directory, filename)
        try:
            data = _read(path)
        except (OSError, ValueError) as error:
            print("[Character Lighting 12] 讀不了 %s：%s" % (path, error))
            continue
        if data.get("schema") != SCHEMA:
            print("[Character Lighting 12] 略過 %s：schema 版本不符" % filename)
            continue
        data["_path"] = path
        data["_is_user"] = is_user
        data["_filename"] = filename
        found[data["id"]] = data
    return found


def _has_text(value):
    """雙語欄位有沒有實際內容（兩種語言任一有字就算）。"""
    if isinstance(value, dict):
        return any(str(item).strip() for item in value.values())
    return bool(value and str(value).strip())


def load_all(force=False):
    """回傳 {id: preset_data}，使用者版本蓋過內建版本。"""
    global _cache
    if _cache is not None and not force:
        return _cache

    presets = _load_dir(_BUILTIN_DIR, is_user=False)
    for preset_id, data in _load_dir(user_dir(), is_user=True).items():
        builtin = presets.get(preset_id)
        if builtin is not None:
            data["_overrides_builtin"] = True
            data["_builtin_path"] = builtin["_path"]
            # 使用者存的版本只該覆蓋燈光數值。名稱與教學文案若是空的，
            # 退回內建那份——否則使用者在文案寫好之前存了自己的版本，
            # 之後文案更新就永遠被那份空白蓋掉了。
            for field in ("name", "desc", "tip"):
                if not _has_text(data.get(field)):
                    data[field] = builtin.get(field)
            data.setdefault("engine_note", builtin.get("engine_note"))
        presets[preset_id] = data

    _cache = presets
    return presets


def invalidate():
    global _cache
    _cache = None


def ordered():
    """照檔名排序（檔名前綴就是教學順序）。"""
    return sorted(load_all().values(), key=lambda data: data.get("_filename", data["id"]))


def get(preset_id):
    return load_all().get(preset_id)


def thumb_cache_dir():
    """使用者預設縮圖的解碼快取。

    縮圖以 base64 存在 JSON 裡（這樣一個檔案就是一個完整的預設，
    匯出＝複製檔案，不會發生「檔案帶走了縮圖掉了」），
    但 Blender 的 previews 只能從檔案載入，所以要先解碼落檔。
    """
    path = os.path.join(
        bpy.utils.user_resource("CONFIG", path="character_lighting_12", create=True),
        "thumb_cache",
    )
    os.makedirs(path, exist_ok=True)
    return path


def thumbnail_path(data):
    """回傳這個預設的縮圖檔案路徑，沒有就回 None。

    內建預設用外掛內附的 PNG；使用者預設從 JSON 裡的 base64 解出來。
    """
    preset_id = data["id"]
    if not data.get("_is_user"):
        builtin = os.path.join(_ADDON_DIR, "thumbnails", "%s.png" % preset_id)
        return builtin if os.path.exists(builtin) else None

    encoded = data.get("thumbnail_png")
    if not encoded:
        # 使用者版本沒帶縮圖時，退回同 id 的內建縮圖
        builtin = os.path.join(_ADDON_DIR, "thumbnails", "%s.png" % preset_id)
        return builtin if os.path.exists(builtin) else None

    cached = os.path.join(thumb_cache_dir(), "%s.png" % preset_id)
    signature = os.path.join(thumb_cache_dir(), "%s.len" % preset_id)
    current = str(len(encoded))
    if os.path.exists(cached) and os.path.exists(signature):
        with open(signature, "r", encoding="utf-8") as handle:
            if handle.read().strip() == current:
                return cached      # 快取還新，不用重解

    try:
        with open(cached, "wb") as handle:
            handle.write(base64.b64decode(encoded))
        with open(signature, "w", encoding="utf-8") as handle:
            handle.write(current)
    except (OSError, ValueError) as error:
        print("[Character Lighting 12] 縮圖解碼失敗：%s" % error)
        return None
    return cached


def encode_thumbnail(path):
    """把 PNG 檔讀成 base64 字串。失敗回 None。"""
    try:
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")
    except OSError as error:
        print("[Character Lighting 12] 讀不到縮圖 %s：%s" % (path, error))
        return None


def make_id(name, existing):
    """從名稱做出一個唯一的 id。中文名稱做不出英數 id 時退回時間戳。"""
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    if not slug:
        slug = "custom_%s" % time.strftime("%Y%m%d_%H%M%S")
    candidate = slug
    index = 2
    while candidate in existing:
        candidate = "%s_%d" % (slug, index)
        index += 1
    return candidate


def delete_user(preset_id):
    """刪掉使用者預設（含縮圖快取）。回傳是否真的刪了。"""
    data = load_all().get(preset_id)
    if not data or not data.get("_is_user"):
        return False
    try:
        os.remove(data["_path"])
    except OSError:
        return False
    for suffix in (".png", ".len"):
        stale = os.path.join(thumb_cache_dir(), preset_id + suffix)
        if os.path.exists(stale):
            try:
                os.remove(stale)
            except OSError:
                pass
    invalidate()
    return True


def save_user(data):
    """把預設寫進使用者資料夾。回傳寫入路徑。"""
    payload = {key: value for key, value in data.items() if not key.startswith("_")}
    payload["schema"] = SCHEMA
    payload["user"] = True

    filename = data.get("_filename") or ("%s.json" % data["id"])
    path = os.path.join(user_dir(), filename)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    invalidate()
    return path


def revert_user(preset_id):
    """刪掉使用者版本，回到內建版本。回傳是否真的刪了東西。"""
    data = load_all().get(preset_id)
    if not data or not data.get("_is_user"):
        return False
    try:
        os.remove(data["_path"])
    except OSError:
        return False
    invalidate()
    return True


def localized(data, field, language):
    """取 name/desc/tip 的當前語言版本，缺就退回英文再退回 id。"""
    value = data.get(field)
    if isinstance(value, dict):
        return value.get(language) or value.get("en") or ""
    return value or ""
