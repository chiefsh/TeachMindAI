"""课件视觉主题调色板。

导出（PPTX/DOCX/PDF）与前端渲染（reveal 演示、网页课件）共用同一套主题 key 与配色，
前端实现见 frontend/src/utils/coursewareTheme.ts —— 两边的 key 和色值必须保持一致。

只暴露少量语义色：primary（标题/强调）、accent（渐变与点缀）、text（正文）、muted（次要文字）。
正文色刻意保持接近，避免某些主题下正文对比度不足。
"""

DEFAULT_THEME = "indigo"

THEMES: dict[str, dict[str, str]] = {
    "indigo": {"label": "靛蓝学院", "primary": "#4F46E5", "accent": "#0EA5E9",
               "text": "#1E293B", "muted": "#64748B", "bg": "#F8FAFC"},
    "emerald": {"label": "清新绿意", "primary": "#059669", "accent": "#10B981",
                "text": "#1E293B", "muted": "#64748B", "bg": "#F5FBF8"},
    "amber": {"label": "活力暖橙", "primary": "#D97706", "accent": "#F59E0B",
              "text": "#1E293B", "muted": "#6B7280", "bg": "#FFFBF3"},
    "rose": {"label": "温暖珊瑚", "primary": "#E11D48", "accent": "#FB7185",
             "text": "#1E293B", "muted": "#64748B", "bg": "#FFF5F7"},
    "sky": {"label": "晴空蓝", "primary": "#0284C7", "accent": "#38BDF8",
            "text": "#1E293B", "muted": "#64748B", "bg": "#F3FAFF"},
    "slate": {"label": "极简墨黑", "primary": "#334155", "accent": "#64748B",
              "text": "#0F172A", "muted": "#6B7280", "bg": "#F6F7F9"},
}


def get_theme(key: str | None) -> dict[str, str]:
    """按 key 取主题，未知 key 回退默认主题。"""
    return THEMES.get(key or "", THEMES[DEFAULT_THEME])


def rgb(hex_color: str) -> tuple[int, int, int]:
    """#RRGGBB → (r, g, b)，供 python-pptx / python-docx 构造 RGBColor。"""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        h = THEMES[DEFAULT_THEME]["primary"].lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
