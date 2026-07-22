# SPDX-License-Identifier: GPL-3.0-or-later
"""N 面板。

動線刻意做成編號的三步驟，因為這個外掛的第一個使用者是學生，
不是熟手——他要看得出「先做這個、再做那個」。
"""

import blf
import bpy

from . import i18n, presets, properties, tags
from .operators import EXAMPLE_COLLECTION

PANEL_CATEGORY_EN = "Lighting"
PANEL_CATEGORY_ZH = "打光"


def wrap_text(text, available, measure):
    """把 text 折成不超過 available 像素的多行。

    抽成獨立函式是為了測得到——折行邏輯埋在 draw() 裡的話，
    headless 測試永遠碰不到它，而「文字被默默吃掉」正是最需要測的。

    `measure(str) -> float` 由呼叫端提供，正式執行時用 blf 量真實像素。
    """
    lines = []
    line = ""
    breakable = " " in text          # 英文在空白斷，中文哪裡都能斷

    for char in text:
        candidate = line + char
        if line and measure(candidate) > available:
            if breakable and " " in line.strip():
                head, _, tail = line.rstrip().rpartition(" ")
                lines.append(head)
                line = tail + char
            else:
                lines.append(line)
                line = char
        else:
            line = candidate

    if line.strip():
        lines.append(line)
    return [item.strip() for item in lines if item.strip()]


class CL12_PT_main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = PANEL_CATEGORY_EN
    bl_label = "Character Lighting 12"
    bl_idname = "CL12_PT_main"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.cl12
        domain = tags.find_domain(context)

        self._draw_engine_warning(layout, context)
        self._draw_step_subject(layout, context, settings, domain)
        layout.separator()
        self._draw_step_preset(layout, context, settings, domain)

        if domain is not None and settings.active_preset:
            layout.separator()
            self._draw_step_adjust(layout, context, settings)
            layout.separator()
            self._draw_step_save(layout, context, settings)

    # ------------------------------------------------------------ 引擎提示

    def _draw_engine_warning(self, layout, context):
        """引擎與運算裝置。這一列固定顯示，位置永遠一樣，不用找。"""
        is_cycles = context.scene.render.engine == "CYCLES"
        box = layout.box()

        if not is_cycles:
            box.alert = True
            column = box.column(align=True)
            column.label(
                text=i18n.t("Tuned for Cycles", "這些數值是照 Cycles 校的"),
                icon="ERROR",
            )
            column.label(
                text=i18n.t("Looks will differ in EEVEE.", "在 EEVEE 下會有落差。"),
            )

        row = box.row(align=True)
        engine = row.row(align=True)
        engine.enabled = not is_cycles          # 已經是 Cycles 就按不下去
        engine.operator("cl12.switch_to_cycles",
                        text=i18n.t("Set Cycles", "設為 Cycles"),
                        icon="SHADING_RENDERED")

        gpu = row.row(align=True)
        gpu.enabled = is_cycles and properties.gpu_available()
        gpu.prop(context.scene.cl12, "use_gpu",
                 text=i18n.t("GPU", "GPU"), toggle=True,
                 icon="CHECKBOX_HLT" if context.scene.cl12.use_gpu
                 else "CHECKBOX_DEHLT")

        if is_cycles and not properties.gpu_available():
            hint = box.column(align=True)
            hint.scale_y = 0.85
            hint.label(text=i18n.t("No GPU device found.",
                                   "偵測不到可用的顯示卡。"), icon="INFO")
        elif is_cycles and context.scene.cl12.use_gpu:
            # 顯示實際在用的後端與裝置。外掛動了系統設定就要講出來，
            # 不然使用者不知道發生過什麼事。
            backend, devices = properties.describe_gpu()
            if backend:
                hint = box.column(align=True)
                hint.scale_y = 0.85
                hint.label(text="%s · %s" % (backend, "、".join(devices) or "—"))

    # ------------------------------------------------------------ 步驟一

    def _draw_step_subject(self, layout, context, settings, domain):
        box = layout.box()
        box.label(text=i18n.t("1. Subject", "1. 主體"), icon="OUTLINER_OB_ARMATURE")

        column = box.column(align=True)
        column.scale_y = 1.3
        column.operator("cl12.create_domain",
                        text=i18n.t("Build Light Domain", "建立光域"),
                        icon="SHADING_BBOX")

        if domain is not None:
            info = box.column(align=True)
            info.scale_y = 0.85
            names = domain.get(tags.DOMAIN_SUBJECT) or []
            if names:
                label = names[0] if len(names) == 1 else (
                    i18n.t("%d objects", "%d 個物件") % len(names)
                )
                info.label(text=str(label), icon="CHECKMARK")
            info.label(text=i18n.t("Size", "尺寸") + "  %.2f"
                       % float(domain.get(tags.DOMAIN_REF) or 0.0))

            # 這兩個是「把主體從場景裡孤立出來」，屬於設定主體的一環，
            # 不是調整燈光。沒有光域時不顯示——那時候分不出誰是主體，
            # 勾下去會把主體自己也藏掉。
            isolate = box.row(align=True)
            isolate.prop(settings, "hide_other_lights", toggle=True,
                         text=i18n.t("Hide Lights", "隱藏原燈光"))
            isolate.prop(settings, "hide_other_objects", toggle=True,
                         text=i18n.t("Hide Objects", "隱藏原物件"))
        else:
            hint = box.column(align=True)
            hint.scale_y = 0.85
            hint.label(text=i18n.t("Select a subject first",
                                   "請先選取主體"), icon="INFO")

        example_row = box.row(align=True)
        has_example = any(tags.EXAMPLE in obj for obj in context.scene.objects)
        if has_example:
            example_row.operator("cl12.remove_example",
                                 text=i18n.t("Remove Example", "移除範例"), icon="TRASH")
            example_row.operator("cl12.view_example_camera",
                                 text="", icon="CAMERA_DATA")
        else:
            example_row.operator("cl12.load_example",
                                 text=i18n.t("Load Example", "載入範例"), icon="IMPORT")

    # ------------------------------------------------------------ 步驟二

    def _draw_step_preset(self, layout, context, settings, domain):
        box = layout.box()
        box.label(text=i18n.t("2. Light", "2. 燈光"), icon="LIGHT_AREA")

        box.template_icon_view(context.scene, "cl12_preview",
                               show_labels=False, scale=7.0, scale_popup=6.0)

        data = presets.get(context.scene.cl12_preview)
        if data is None:
            box.label(text=i18n.t("No preset data found.", "找不到預設資料。"), icon="ERROR")
            return

        language = i18n.language()
        title = box.row()
        title.label(text=presets.localized(data, "name", language))
        if data.get("_is_user"):
            title.label(text=i18n.t("edited", "已修改"), icon="FILE_TICK")

        description = presets.localized(data, "desc", language)
        if description:
            self._wrapped(box, context, description, scale=0.85)

        tip = presets.localized(data, "tip", language)
        if tip:
            tip_box = box.box()
            self._wrapped(tip_box, context, tip, scale=0.85, icon="LIGHT",
                          indent=52)

        note = data.get("engine_note")
        if note and context.scene.render.engine != "CYCLES":
            reason = {
                "volume": i18n.t("uses volumetric fog", "這組用了體積霧"),
                "procedural": i18n.t("uses procedural textures", "這組用了程序紋理"),
            }.get(note, "")
            box.label(text=reason + i18n.t(" — needs Cycles", "，需要 Cycles"),
                      icon="INFO")

        apply_row = box.row()
        apply_row.scale_y = 1.4
        apply_row.enabled = domain is not None
        operator = apply_row.operator("cl12.apply_preset",
                                      text=i18n.t("Apply Light", "套用燈光"),
                                      icon="CHECKMARK")
        operator.preset_id = context.scene.cl12_preview

        if domain is None:
            hint = box.column()
            hint.scale_y = 0.85
            hint.label(text=i18n.t("Build the light domain first",
                                   "請先建立光域"), icon="INFO")

    # ------------------------------------------------------------ 步驟三

    def _draw_step_adjust(self, layout, context, settings):
        box = layout.box()
        box.label(text=i18n.t("3. Adjust", "3. 調整"), icon="MODIFIER")

        column = box.column(align=True)
        column.prop(settings, "intensity", text=i18n.t("Intensity", "強度"), slider=True)
        column.prop(settings, "temperature", text=i18n.t("Temperature", "色溫"))
        column.prop(settings, "distance", text=i18n.t("Distance", "距離"), slider=True)
        column.prop(settings, "rotation", text=i18n.t("Rotation", "旋轉"))

        box.separator()
        options = box.column(align=True)
        options.prop(settings, "film_transparent",
                     text=i18n.t("Transparent Background", "背景透明"))
        options.prop(settings, "wire_helpers",
                     text=i18n.t("Helpers as Wireframe", "輔助物件線框顯示"))

        box.operator("cl12.clear_lights",
                     text=i18n.t("Clear Lights", "清除燈光"), icon="TRASH")

    # ------------------------------------------------------------ 步驟四

    def _draw_step_save(self, layout, context, settings):
        box = layout.box()
        box.label(text=i18n.t("Save Preset", "儲存燈光預設"), icon="FILE_TICK")

        current = presets.get(context.scene.cl12_preview)
        is_custom = bool(current and current.get("_is_user")
                         and not current.get("_overrides_builtin"))

        row = box.row(align=True)
        row.operator("cl12.save_preset",
                     text=i18n.t("Overwrite", "覆蓋目前這組"), icon="FILE_TICK")
        data = presets.get(settings.active_preset)
        if data is not None and data.get("_is_user"):
            row.operator("cl12.revert_preset",
                         text="", icon="LOOP_BACK").preset_id = settings.active_preset

        box.operator("cl12.new_preset",
                     text=i18n.t("New Preset", "新增預設"), icon="ADD")

        # 預覽相機：自訂預設的縮圖要跟內建 12 張構圖一致，得靠它。
        box.operator("cl12.preview_camera",
                     text=i18n.t("Preview Camera", "建立預覽相機"),
                     icon="OUTLINER_OB_CAMERA")

        transfer = box.row(align=True)
        transfer.operator("cl12.export_preset",
                          text=i18n.t("Export", "匯出"), icon="EXPORT")
        transfer.operator("cl12.import_preset",
                          text=i18n.t("Import", "匯入"), icon="IMPORT")

        if is_custom:
            box.operator("cl12.delete_preset",
                         text=i18n.t("Delete This Preset", "刪除這組預設"),
                         icon="TRASH").preset_id = current["id"]

        box.operator("cl12.open_preset_folder",
                     text=i18n.t("Open Preset Folder", "開啟預設資料夾"),
                     icon="FILEBROWSER")

    # ------------------------------------------------------------ 工具

    @staticmethod
    def _measure(text, size):
        """量文字的像素寬度。blf.size 的簽章在 4.0 改過，兩種都要接。"""
        try:
            blf.size(0, size)
        except TypeError:
            blf.size(0, size, 72)
        return blf.dimensions(0, text)[0]

    @classmethod
    def _wrapped(cls, layout, context, text, scale=1.0, icon="NONE", indent=34):
        """N 面板很窄，長句子要自己折行，不然 Blender 會把整行截成「⋯」。

        ⚠️ **不能用「字數 × 固定像素」估寬度。** 中文字寬大約是英文的兩倍，
        用同一個係數算，中文那行就會遠超過實際可用寬度而被截斷。
        這裡直接用 blf 量真實像素寬，所以中英混排也準，面板縮放時會跟著重折。

        `indent` 是外框與圖示佔掉的像素（在 box 裡再包一層 box 要給大一點）。
        """
        column = layout.column(align=True)
        column.scale_y = scale

        ui_scale = context.preferences.system.ui_scale
        size = max(int(round(11 * ui_scale)), 8)
        available = max(context.region.width - indent * ui_scale, 60)
        if icon != "NONE":
            available -= 20 * ui_scale

        def measure(value):
            return cls._measure(value, size)

        try:
            measure("測試")
        except Exception:
            # blf 不可用時退回估算：中日韓字算兩格，其餘算一格。
            def measure(value):
                units = sum(2 if ord(ch) > 0x2E7F else 1 for ch in value)
                return units * size * 0.55

        for index, content in enumerate(wrap_text(text, available, measure)):
            column.label(text=content, icon=icon if index == 0 else "NONE")


class CL12_PT_main_zh(CL12_PT_main):
    """繁體介面時把分頁名稱也換成中文（Blender 不允許動態改 bl_category，
    所以用兩個類別，註冊時依語言擇一）。"""
    bl_idname = "CL12_PT_main_zh"
    bl_category = PANEL_CATEGORY_ZH


def register():
    bpy.utils.register_class(
        CL12_PT_main_zh if i18n.language() == i18n.ZH else CL12_PT_main
    )


def unregister():
    for cls in (CL12_PT_main, CL12_PT_main_zh):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
