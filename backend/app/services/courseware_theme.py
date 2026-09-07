"""课件 Theme System。

导出（PPTX/DOCX/PDF）与前端渲染（reveal 演示、网页课件）共用同一套主题 key。
前端实现见 frontend/src/utils/coursewareTheme.ts —— 两边的 key、色值、封面/装饰/阴影
必须保持一致，否则在线预览与导出会长得不一样。

每个主题包含：
- 色板：bg / card / surface / text / muted / primary / accent / cover_from / cover_to / on_cover
- 封面样式 cover_style、装饰样式 deco_style、阴影 shadow / shadow_soft

未知或旧版 key 经 ALIASES 回退到现行主题，不要让页面落到纯白底。
"""

DEFAULT_THEME = "explore"

# 旧版 6 色主题 → 现行主题
ALIASES: dict[str, str] = {
    "indigo": "explore",
    "sky": "explore",
    "emerald": "nature",
    "amber": "vibrant",
    "rose": "humanities",
    "slate": "exam",
}

# 页面类型（生成与渲染共用）。旧 type 经 PAGE_ALIASES 归一。
PAGE_LABELS: dict[str, str] = {
    "cover": "封面",
    "objectives": "学习目标",
    "knowledge": "新知讲解",
    "example": "例题精讲",
    "interactive": "互动探究",
    "comparison": "对比辨析",
    "process": "过程路径",
    "summary": "课堂小结",
    "exercise": "随堂练习",
    "homework": "课后作业",
    # 旧 type 仍显示原来的教学用语
    "title": "封面",
    "content": "新知讲解",
    "intro": "情境导入",
    "activity": "课堂活动",
    "board": "板书设计",
    "quiz": "随堂测验",
}

PAGE_ALIASES: dict[str, str] = {
    "title": "cover",
    "content": "knowledge",
    "intro": "process",
    "activity": "interactive",
    "quiz": "exercise",
    "board": "summary",
}

THEMES: dict[str, dict[str, str]] = {
    "vibrant": {
        "label": "活力课堂",
        "primary": "#E85D04",
        "accent": "#F48C06",
        "text": "#3B1D08",
        "muted": "#9A6240",
        "bg": "#FFF1E4",
        "card": "#FFF8F0",
        "surface": "#FFE0C2",
        "cover_from": "#E85D04",
        "cover_to": "#DC2F02",
        "on_cover": "#FFFFFF",
        "cover_style": "diagonal",
        "deco_style": "circles",
        "shadow": "0 10px 28px rgba(232,93,4,0.14)",
        "shadow_soft": "0 3px 10px rgba(232,93,4,0.08)",
    },
    "nature": {
        "label": "清新自然",
        "primary": "#2D6A4F",
        "accent": "#52B788",
        "text": "#143528",
        "muted": "#52796F",
        "bg": "#EAF6EF",
        "card": "#F6FBF8",
        "surface": "#D4EDDA",
        "cover_from": "#1B4332",
        "cover_to": "#40916C",
        "on_cover": "#FFFFFF",
        "cover_style": "split",
        "deco_style": "leaves",
        "shadow": "0 10px 28px rgba(45,106,79,0.12)",
        "shadow_soft": "0 3px 10px rgba(45,106,79,0.08)",
    },
    "explore": {
        "label": "蓝色探索",
        "primary": "#1D4ED8",
        "accent": "#0EA5E9",
        "text": "#102A4C",
        "muted": "#5B7A9D",
        "bg": "#E7F0FA",
        "card": "#F4F8FD",
        "surface": "#D0E3F6",
        "cover_from": "#1E3A8A",
        "cover_to": "#0284C7",
        "on_cover": "#FFFFFF",
        "cover_style": "ribbon",
        "deco_style": "grid",
        "shadow": "0 10px 28px rgba(29,78,216,0.12)",
        "shadow_soft": "0 3px 10px rgba(29,78,216,0.08)",
    },
    "humanities": {
        "label": "人文阅读",
        "primary": "#9A3412",
        "accent": "#C2410C",
        "text": "#3F2412",
        "muted": "#9A6B52",
        "bg": "#F3E8D9",
        "card": "#FAF4EB",
        "surface": "#E6D3B8",
        "cover_from": "#7C2D12",
        "cover_to": "#B45309",
        "on_cover": "#FFFFFF",
        "cover_style": "panel",
        "deco_style": "waves",
        "shadow": "0 8px 22px rgba(124,45,18,0.12)",
        "shadow_soft": "0 3px 8px rgba(124,45,18,0.08)",
    },
    "lab": {
        "label": "明亮实验室",
        "primary": "#0F766E",
        "accent": "#14B8A6",
        "text": "#134E4A",
        "muted": "#5F8A86",
        "bg": "#E4F4F2",
        "card": "#F2FAF9",
        "surface": "#C8EDE8",
        "cover_from": "#115E59",
        "cover_to": "#0D9488",
        "on_cover": "#FFFFFF",
        "cover_style": "lab",
        "deco_style": "dots",
        "shadow": "0 10px 28px rgba(15,118,110,0.12)",
        "shadow_soft": "0 3px 10px rgba(15,118,110,0.08)",
    },
    "exam": {
        "label": "简洁考试",
        "primary": "#334155",
        "accent": "#64748B",
        "text": "#0F172A",
        "muted": "#64748B",
        "bg": "#E8EDF3",
        "card": "#F4F6F9",
        "surface": "#D9E0E8",
        "cover_from": "#1E293B",
        "cover_to": "#475569",
        "on_cover": "#FFFFFF",
        "cover_style": "minimal",
        "deco_style": "lines",
        "shadow": "0 6px 18px rgba(15,23,42,0.10)",
        "shadow_soft": "0 2px 8px rgba(15,23,42,0.06)",
    },
}


def resolve_theme_key(key: str | None) -> str:
    k = ALIASES.get(key or "", key or DEFAULT_THEME)
    return k if k in THEMES else DEFAULT_THEME


def get_theme(key: str | None) -> dict[str, str]:
    """按 key 取主题，未知/旧 key 回退现行默认主题。"""
    return THEMES[resolve_theme_key(key)]


def page_kind(slide_type: str | None) -> str:
    t = (slide_type or "knowledge").strip() or "knowledge"
    return PAGE_ALIASES.get(t, t if t in PAGE_LABELS else "knowledge")


def page_label(slide_type: str | None) -> str:
    t = slide_type or "knowledge"
    return PAGE_LABELS.get(t) or PAGE_LABELS.get(page_kind(t), "内容")


def rgb(hex_color: str) -> tuple[int, int, int]:
    """#RRGGBB → (r, g, b)，供 python-pptx / python-docx 构造 RGBColor。"""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        h = THEMES[DEFAULT_THEME]["primary"].lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
