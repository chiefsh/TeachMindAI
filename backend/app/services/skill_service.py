"""理科 skill 接入服务。

把「课件知识点」路由到对应的学科 skill（立体几何 / 解析几何 / 化学反应），
用 skill 的 sympy 精确计算核心 + 数据驱动模板，确定性地生成整页交互 HTML。

设计要点：
- LLM 只负责「判类别 + 抽小 spec」（小 JSON），HTML 与数值由 skill 代码确定性产出，
  彻底避免「LLM 现编 HTML」带来的转义 / 吐空 / 答案不一致问题。
- 每个 skill 通过**子进程**调用其 generate.py / runner，进程隔离，规避三 skill 模块名冲突。
- 任何环节失败都返回空串，交由上层回退到原有 LLM 生成流程（纯增益、无回归）。
"""
import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# skills 根目录：backend/app/services/skill_service.py -> parents[2] = backend
SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"
SKILL_RUNNERS = Path(__file__).resolve().parent / "skill_runners"

# ---------------------------------------------------------------------------
# 能力表：登记各 skill 支持的学科与题型
# ---------------------------------------------------------------------------
SKILL_CAPABILITIES: dict[str, dict] = {
    "edu-solid-geometry": {
        "subjects": ["数学"],
        "problem_types": {
            "line_plane_angle": "线面角（直线与平面所成角）",
            "volume": "几何体体积",
            "skew_lines": "异面直线所成角",
            "dihedral": "二面角",
            "point_plane_distance": "点到平面的距离",
            # 通用 3D 教具：不依赖具体题面，讲几何体本身
            "solid_explore": "立体图形探究台（可旋转 3D：顶点棱面、底面与高、体积与表面积）",
        },
    },
    "edu-analytic-geometry": {
        "subjects": ["数学"],
        # 除 curve_explore 外都是固定的“示例题场景”，路由器只需选出最贴近的 key（无需 spec）
        "problem_types": {
            "ellipse_dot_range": "椭圆·过焦点弦上向量数量积的取值范围",
            "ellipse_chord_range": "椭圆·过焦点弦弦长的取值范围",
            "ellipse_area_max": "椭圆·三角形面积最值",
            "ellipse_slopeprod_const": "椭圆·中心对称弦斜率之积为定值",
            "parabola_dot_const": "抛物线·焦点弦向量数量积为定值",
            "hyperbola_ecc_range": "双曲线·离心率取值范围",
            # 通用画板：不依赖具体题面，讲曲线的定义与性质
            "curve_explore": "圆锥曲线画板（拖动动点，实时演示定义与焦半径定值）",
        },
    },
    "edu-chem-reaction": {
        "subjects": ["化学", "生物"],
        "problem_types": {
            "combustion_ch4": "甲烷燃烧",
            "combustion_h2": "氢气燃烧",
            "electrolysis_water": "电解水",
            "redox_na_cl2": "钠与氯气反应（氧化还原·电子转移）",
            "esterification": "酯化反应（乙酸+乙醇）",
            "glucose_combustion": "葡萄糖有氧氧化（细胞呼吸）",
        },
    },
    "edu-chem-lab": {
        "subjects": ["化学", "科学"],
        "problem_types": {},  # 由 LAB_CATALOG 填入
    },
    "edu-bio": {
        "subjects": ["生物"],
        "problem_types": {},  # 由 BIO_CATALOG 填入
    },
    "edu-physics": {
        "subjects": ["物理"],
        "problem_types": {},  # 由 PHYSICS_CATALOG 填入
    },
}


def _is_math(subject: str) -> bool:
    return "数学" in (subject or "")


def _is_chem(subject: str) -> bool:
    s = subject or ""
    return ("化学" in s) or ("生物" in s)


def _is_bio(subject: str) -> bool:
    return "生物" in (subject or "")


def _is_physics(subject: str) -> bool:
    return "物理" in (subject or "")


def _is_lab_subject(subject: str) -> bool:
    s = subject or ""
    return ("化学" in s) or ("科学" in s)


# 宏观实验目录：匹配、课件下拉、PPT 题名共用。新增实验先改 generate.py REGISTRY，再在此补一行。
LAB_CATALOG: list[dict] = [
    {"key": "prep_oxygen_kmno4", "title": "高锰酸钾制取氧气", "group": "制取气体",
     "keywords": ("氧气", "制氧", "制取氧气", "高锰酸钾", "氯酸钾", "过氧化氢", "带火星", "复燃")},
    {"key": "prep_hydrogen", "title": "锌和稀盐酸制取氢气", "group": "制取气体",
     "keywords": ("氢气", "制氢", "锌粒", "爆鸣", "验纯", "向下排空气")},
    {"key": "prep_co2", "title": "大理石和稀盐酸制取二氧化碳", "group": "制取气体",
     "keywords": ("二氧化碳", "大理石", "石灰石", "变浑浊", "向上排空气")},
    {"key": "electrolysis", "title": "电解水", "group": "反应与性质",
     "keywords": ("电解水", "正氧负氢", "霍夫曼", "通电分解")},
    {"key": "neutralization", "title": "酸碱中和（酚酞指示剂）", "group": "反应与性质",
     "keywords": ("中和", "中和反应", "酸碱中和", "滴定", "恰好完全")},
    {"key": "metal_acid", "title": "金属与稀盐酸反应", "group": "反应与性质",
     "keywords": ("金属活动性", "置换氢", "锌和稀盐酸", "铁和稀盐酸", "铜不反应")},
    {"key": "metal_oxide_acid", "title": "氧化铜与稀硫酸反应", "group": "反应与性质",
     "keywords": ("氧化铜", "稀硫酸", "硫酸铜", "金属氧化物", "黑色粉末变蓝")},
    {"key": "nh4hco3_decomp", "title": "碳酸氢铵受热分解", "group": "反应与性质",
     "keywords": ("碳酸氢铵", "铵盐分解", "湿润红色石蕊", "扇闻")},
    {"key": "iron_in_oxygen", "title": "铁丝在氧气中燃烧", "group": "反应与性质",
     "keywords": ("铁丝", "铁丝燃烧", "火星四射", "氧气中燃烧", "四氧化三铁", "瓶底留水")},
    {"key": "filtration", "title": "过滤", "group": "基本操作",
     "keywords": ("过滤", "滤纸", "一贴二低三靠", "残渣")},
    {"key": "evaporation", "title": "蒸发结晶", "group": "基本操作",
     "keywords": ("蒸发", "结晶", "蒸发皿", "余热蒸干", "飞溅")},
    {"key": "solution_prep", "title": "配制一定溶质质量分数的溶液", "group": "基本操作",
     "keywords": ("溶质质量分数", "配制溶液", "称量", "量筒", "托盘天平")},
]
LAB_KEYWORDS: dict[str, tuple[str, ...]] = {e["key"]: e["keywords"] for e in LAB_CATALOG}
SKILL_CAPABILITIES["edu-chem-lab"]["problem_types"] = {
    e["key"]: f"{e['title']}（宏观实验台）" for e in LAB_CATALOG
}

# 生物探究：点击结构 / 分阶段播放。新增场景先改 generate.py REGISTRY，再在此补一行。
BIO_CATALOG: list[dict] = [
    {"key": "animal_cell", "title": "动物细胞结构", "group": "细胞",
     "keywords": ("动物细胞", "细胞膜", "中心体", "溶酶体"),
     "knowledge_tags": ["动物细胞", "细胞结构", "细胞器"]},
    {"key": "plant_cell", "title": "植物细胞结构", "group": "细胞",
     "keywords": ("植物细胞", "细胞壁", "叶绿体", "液泡", "大液泡"),
     "knowledge_tags": ["植物细胞", "细胞结构", "细胞壁"]},
    {"key": "mitosis", "title": "有丝分裂", "group": "细胞增殖",
     "keywords": ("有丝分裂", "赤道板", "纺锤体", "细胞周期"),
     "knowledge_tags": ["有丝分裂", "细胞分裂", "细胞周期"]},
    {"key": "digestive_system", "title": "人体消化系统", "group": "人体",
     "keywords": ("消化系统", "小肠", "消化腺", "消化道"),
     "knowledge_tags": ["消化系统", "小肠", "消化"]},
    {"key": "circulatory_system", "title": "人体循环系统", "group": "人体",
     "keywords": ("循环系统", "体循环", "肺循环", "心脏", "动脉", "静脉"),
     "knowledge_tags": ["循环系统", "血液循环", "心脏"]},
    {"key": "respiratory_system", "title": "人体呼吸系统", "group": "人体",
     "keywords": ("呼吸系统", "肺泡", "膈肌", "呼吸道"),
     "knowledge_tags": ["呼吸系统", "肺", "肺泡"]},
    {"key": "neuron", "title": "神经元", "group": "神经",
     "keywords": ("神经元", "树突", "轴突", "突触", "神经细胞"),
     "knowledge_tags": ["神经元", "神经细胞"]},
    {"key": "nervous_system", "title": "人体神经系统", "group": "神经",
     "keywords": ("神经系统", "脊髓", "反射弧", "周围神经"),
     "knowledge_tags": ["神经系统", "脑", "脊髓"]},
    {"key": "photosynthesis", "title": "光合作用", "group": "代谢",
     "keywords": ("光合作用", "叶绿体", "光反应", "暗反应"),
     "knowledge_tags": ["光合作用", "叶绿体"]},
    {"key": "dna_structure", "title": "DNA 双螺旋", "group": "遗传",
     "keywords": ("DNA", "双螺旋", "碱基互补", "碱基对", "脱氧核糖核酸"),
     "knowledge_tags": ["DNA", "双螺旋", "碱基互补配对"]},
]
BIO_KEYWORDS: dict[str, tuple[str, ...]] = {e["key"]: e["keywords"] for e in BIO_CATALOG}
SKILL_CAPABILITIES["edu-bio"]["problem_types"] = {
    e["key"]: e["title"] for e in BIO_CATALOG
}

PHYSICS_CATALOG: list[dict] = [
    {"key": "magnetic_field", "title": "磁场与磁感线", "group": "电磁",
     "keywords": ("磁场", "磁感线", "条形磁铁", "小磁针"),
     "knowledge_tags": ["磁场", "磁感线", "磁极"]},
    {"key": "electromagnetic_induction", "title": "电磁感应", "group": "电磁",
     "keywords": ("电磁感应", "感应电流", "磁通量", "楞次定律", "磁场变化"),
     "knowledge_tags": ["电磁感应", "感应电流", "磁场变化"]},
    {"key": "circuit_series_parallel", "title": "串并联电路", "group": "电学",
     "keywords": ("串联", "并联", "串并联", "电路"),
     "knowledge_tags": ["串联", "并联", "电路"]},
    {"key": "ohm_law", "title": "欧姆定律", "group": "电学",
     "keywords": ("欧姆定律", "电压表", "电流表"),
     "knowledge_tags": ["欧姆定律", "电阻"]},
    {"key": "force_composition", "title": "力的合成", "group": "力学",
     "keywords": ("力的合成", "平行四边形定则", "合力"),
     "knowledge_tags": ["力的合成", "合力", "平行四边形定则"]},
    {"key": "newton_laws", "title": "牛顿运动定律", "group": "力学",
     "keywords": ("牛顿定律", "牛顿第一定律", "牛顿第二定律", "惯性", "作用力与反作用力"),
     "knowledge_tags": ["牛顿运动定律", "惯性", "牛顿第二定律"]},
    {"key": "state_change", "title": "物态变化", "group": "热学",
     "keywords": ("物态变化", "熔化", "汽化", "升华", "凝华", "液化"),
     "knowledge_tags": ["物态变化", "熔化", "汽化"]},
    {"key": "light_reflection", "title": "光的反射", "group": "光学",
     "keywords": ("光的反射", "反射定律", "入射角", "平面镜"),
     "knowledge_tags": ["光的反射", "反射定律", "平面镜"]},
    {"key": "convex_lens", "title": "凸透镜成像", "group": "光学",
     "keywords": ("凸透镜", "焦距", "实像", "虚像", "放大镜"),
     "knowledge_tags": ["凸透镜", "凸透镜成像"]},
    {"key": "buoyancy", "title": "浮力", "group": "力学",
     "keywords": ("浮力", "阿基米德", "排开液体", "漂浮"),
     "knowledge_tags": ["浮力", "阿基米德原理"]},
    {"key": "projectile_motion", "title": "抛体运动", "group": "力学",
     "keywords": ("抛体", "平抛", "斜抛", "抛射", "抛物线运动"),
     "knowledge_tags": ["抛体运动", "平抛运动"]},
    {"key": "simple_pendulum", "title": "单摆", "group": "振动",
     "keywords": ("单摆", "简谐", "摆长", "周期公式"),
     "knowledge_tags": ["单摆", "简谐运动"]},
    {"key": "collision_momentum", "title": "碰撞与动量", "group": "力学",
     "keywords": ("碰撞", "动量守恒", "弹性碰撞", "非弹性"),
     "knowledge_tags": ["动量守恒", "碰撞"]},
    {"key": "circular_motion", "title": "匀速圆周运动", "group": "力学",
     "keywords": ("圆周运动", "向心力", "向心加速度", "匀速圆周"),
     "knowledge_tags": ["圆周运动", "向心力"]},
    {"key": "incline_friction", "title": "斜面与摩擦", "group": "力学",
     "keywords": ("斜面", "摩擦角", "自锁", "动摩擦因数"),
     "knowledge_tags": ["斜面", "摩擦力"]},
    {"key": "light_refraction", "title": "光的折射", "group": "光学",
     "keywords": ("折射", "折射率", "全反射", "临界角", "斯涅尔"),
     "knowledge_tags": ["光的折射", "全反射"]},
    {"key": "coulomb_law", "title": "库仑定律", "group": "电磁",
     "keywords": ("库仑", "点电荷", "静电力", "电荷相互作用"),
     "knowledge_tags": ["库仑定律", "静电力"]},
    {"key": "lever_balance", "title": "杠杆平衡", "group": "机械",
     "keywords": ("杠杆", "力臂", "力矩", "省力杠杆"),
     "knowledge_tags": ["杠杆", "力矩平衡"]},
    {"key": "pressure", "title": "压强", "group": "力学",
     "keywords": ("压强", "液体压强", "受力面积", "ρgh"),
     "knowledge_tags": ["压强", "液体压强"]},
    {"key": "mechanical_energy", "title": "动能与重力势能", "group": "能量",
     "keywords": ("动能", "重力势能", "机械能", "机械能守恒"),
     "knowledge_tags": ["动能", "重力势能", "机械能"]},
    {"key": "spring_harmonic", "title": "弹簧振子", "group": "振动",
     "keywords": ("弹簧振子", "简谐运动", "劲度系数", "胡克定律"),
     "knowledge_tags": ["弹簧振子", "简谐运动"]},
    {"key": "pulley_block", "title": "滑轮组与机械效率", "group": "机械",
     "keywords": ("滑轮", "动滑轮", "定滑轮", "机械效率", "滑轮组"),
     "knowledge_tags": ["滑轮", "机械效率"]},
    {"key": "ampere_force", "title": "安培力", "group": "电磁",
     "keywords": ("安培力", "左手定则", "通电导线", "磁场力"),
     "knowledge_tags": ["安培力", "左手定则"]},
    {"key": "parallel_capacitor", "title": "平行板电容器", "group": "电磁",
     "keywords": ("电容器", "电容", "平行板", "介电常数"),
     "knowledge_tags": ["电容器", "电容"]},
    {"key": "transformer", "title": "变压器", "group": "电磁",
     "keywords": ("变压器", "匝数比", "升压", "降压", "互感"),
     "knowledge_tags": ["变压器", "互感"]},
    {"key": "ideal_gas", "title": "理想气体", "group": "热学",
     "keywords": ("理想气体", "玻意耳", "查理定律", "气体压强", "pV=nRT"),
     "knowledge_tags": ["理想气体", "气体实验定律"]},
    {"key": "mechanical_wave", "title": "横波与纵波", "group": "波动",
     "keywords": ("横波", "纵波", "机械波", "波长", "波速"),
     "knowledge_tags": ["机械波", "横波", "纵波"]},
    {"key": "doppler_effect", "title": "多普勒效应", "group": "波动",
     "keywords": ("多普勒", "频率变化", "红移", "音调"),
     "knowledge_tags": ["多普勒效应"]},
    {"key": "gravitation_orbit", "title": "万有引力与卫星", "group": "力学",
     "keywords": ("万有引力", "卫星", "第一宇宙速度", "圆轨道", "开普勒"),
     "knowledge_tags": ["万有引力", "卫星运动"]},
    {"key": "photoelectric", "title": "光电效应", "group": "近代",
     "keywords": ("光电效应", "逸出功", "光子", "截止频率", "爱因斯坦"),
     "knowledge_tags": ["光电效应", "光子"]},
]
PHYSICS_KEYWORDS: dict[str, tuple[str, ...]] = {e["key"]: e["keywords"] for e in PHYSICS_CATALOG}
SKILL_CAPABILITIES["edu-physics"]["problem_types"] = {
    e["key"]: e["title"] for e in PHYSICS_CATALOG
}


def known_lab_keys() -> set[str]:
    return {e["key"] for e in LAB_CATALOG}


def lab_experiment_catalog() -> dict:
    """给前端下拉用：按 group 原序返回。"""
    return {
        "items": [{"key": e["key"], "title": e["title"], "group": e["group"]} for e in LAB_CATALOG],
    }


def match_lab_key(text: str, explicit: str | None = None) -> str | None:
    """从指定 key 或关键词中解析宏观实验题型。"""
    caps = SKILL_CAPABILITIES["edu-chem-lab"]["problem_types"]
    key = (explicit or "").strip()
    if key in caps:
        return key
    blob = text or ""
    best_key, best_n = None, 0
    for k, words in LAB_KEYWORDS.items():
        n = sum(1 for w in words if w in blob)
        if n > best_n:
            best_key, best_n = k, n
    # 单个共享词（如「氧气」）不够，避免把不相关课时配上实验台
    if best_n < 2:
        return None
    return best_key


def pick_chem_lab(
    points: list[dict],
    title: str = "",
    lab_key: str | None = None,
    default: str | None = None,
) -> tuple[int, str] | None:
    """给整课指定 1 个宏观实验：返回 (知识点下标, problem_type)。"""
    caps = SKILL_CAPABILITIES["edu-chem-lab"]["problem_types"]
    blob = title or ""
    for p in points or []:
        blob += " " + str(p.get("name") or "") + " " + str(p.get("plain_explanation") or "")
        blob += " " + str(p.get("activity_goal") or "")
    key = match_lab_key(blob, lab_key) or (default if default in caps else None)
    if not key:
        return None
    words = LAB_KEYWORDS.get(key, ())
    best_i, best_n = 0, -1
    for i, p in enumerate(points or []):
        text = " ".join(str(p.get(k) or "") for k in ("name", "plain_explanation", "activity_goal"))
        n = sum(1 for w in words if w in text)
        if n > best_n:
            best_i, best_n = i, n
    return best_i, key


def match_bio_key(text: str) -> str | None:
    blob = text or ""
    best_key, best_n = None, 0
    for k, words in BIO_KEYWORDS.items():
        n = sum(1 for w in words if w in blob)
        if n > best_n:
            best_key, best_n = k, n
    return best_key


def route_bio_point(point: dict, subject_name: str) -> dict | None:
    """生物探究：关键词命中即用模板，不调 LLM。"""
    if not _is_bio(subject_name):
        return None
    text = " ".join(str(point.get(k) or "") for k in ("name", "plain_explanation", "activity_goal"))
    key = match_bio_key(text)
    if not key:
        return None
    return {"skill": "edu-bio", "problem_type": key, "spec": {}}


def match_physics_key(text: str) -> str | None:
    blob = text or ""
    best_key, best_n = None, 0
    for k, words in PHYSICS_KEYWORDS.items():
        n = sum(1 for w in words if w in blob)
        if n > best_n:
            best_key, best_n = k, n
    return best_key


def route_physics_point(point: dict, subject_name: str) -> dict | None:
    """物理探究：关键词命中即用模板，不调 LLM。"""
    if not _is_physics(subject_name):
        return None
    text = " ".join(str(point.get(k) or "") for k in ("name", "plain_explanation", "activity_goal"))
    key = match_physics_key(text)
    if not key:
        return None
    return {"skill": "edu-physics", "problem_type": key, "spec": {}}


# ---------------------------------------------------------------------------
# 路由：数学（立体几何 + 解析几何）
# ---------------------------------------------------------------------------
async def route_math_point(cfg, point: dict, subject_name: str) -> dict | None:
    """判断数学知识点能否用立体几何 / 解析几何 skill 演示。命中返回 routed，否则 None。"""
    if not _is_math(subject_name):
        return None

    from app.services.ai_service import _call_llm, _resp_content, _parse_json_object

    prompt = f"""你是数学课件工具的路由器。判断下面这个知识点是否适合用「确定性交互演示」讲解。

知识点名称：{point.get('name', '')}
白话解释：{point.get('plain_explanation', '')}
互动目标：{point.get('activity_goal', '')}

【立体几何 skill：edu-solid-geometry】（problem_type）：
- line_plane_angle：直线与平面所成角（线面角）。spec 可给 body: pyramid|cube；pyramid 时给 base_edge、height（正整数）。
- volume：长方体体积。spec 给 lx/ly/lz。
- skew_lines：异面直线所成角（正方体）。spec 可给 edge。
- dihedral：二面角（正四面体）。无需参数。
- point_plane_distance：点到平面距离（正方体）。spec 可给 edge。

【解析几何 skill：edu-analytic-geometry】（problem_type，均为固定示例题，spec 留空 {{}}）：
- ellipse_dot_range：椭圆过焦点弦上向量数量积的取值范围。
- ellipse_chord_range：椭圆过焦点弦弦长的取值范围。
- ellipse_area_max：椭圆中三角形面积最值。
- ellipse_slopeprod_const：椭圆中心对称弦斜率之积为定值。
- parabola_dot_const：抛物线焦点弦向量数量积为定值。
- hyperbola_ecc_range：双曲线离心率取值范围。

【通用兜底：没有固定题面、但适合可视化的概念课】
- solid_explore（立体几何 skill）：可旋转 3D 立体图形探究台，讲几何体的顶点/棱/面、底面与高、
  体积与表面积。适用于「认识棱柱棱锥」「几何体的结构特征」「体积/表面积公式」等。
  spec 给 body 及尺寸（正整数、尽量小）：
  - body=cube：edge
  - body=cuboid：lx、ly、lz
  - body=quad_pyramid（正四棱锥）：base_edge、height
  - body=tetrahedron（正四面体）：edge
  - body=tri_prism（正三棱柱）：base_edge、height
  只支持这五种多面体；圆柱、圆锥、球一律不要选。
- curve_explore（解析几何 skill）：可拖动的圆锥曲线画板，实时演示定义与焦半径定值、渐近线、
  准线、切线。适用于「椭圆/双曲线/抛物线的定义与标准方程」「离心率」「渐近线」「圆的方程」等。
  spec 给 curve 及参数（正数、尽量小）：
  - curve=ellipse：a、b（不相等）
  - curve=hyperbola：a、b，可给 orient（"x" 或 "y"）
  - curve=parabola：p，可给 axis（"x" 或 "y"）
  - curve=circle：r

规则：
1. 优先匹配上面的具体题型；只有解题型题目才用具体题型。
2. 若知识点是概念/性质课（没有具体题面）但属于「多面体」或「圆锥曲线与圆」，用对应的通用兜底类型。
3. 两类都不沾边（如概率、数列、三角恒等变换、任意函数图像）时返回 {{"match": false}}。
4. 命中立体几何题型或通用兜底时给出合理示例参数；解析几何固定示例题的 spec 一律为 {{}}。
5. 只输出 JSON，不要解释，不要 markdown 代码块。

命中示例（线面角·正四棱锥）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "line_plane_angle", "spec": {{"body": "pyramid", "base_edge": 2, "height": 1}}}}
命中示例（体积）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "volume", "spec": {{"lx": 3, "ly": 4, "lz": 5}}}}
命中示例（异面直线所成角）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "skew_lines", "spec": {{"edge": 1}}}}
命中示例（二面角）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "dihedral", "spec": {{}}}}
命中示例（点到平面距离）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "point_plane_distance", "spec": {{"edge": 1}}}}
命中示例（解析几何·椭圆离心率之类）：
{{"match": true, "skill": "edu-analytic-geometry", "problem_type": "hyperbola_ecc_range", "spec": {{}}}}
命中示例（概念课·认识正四棱锥）：
{{"match": true, "skill": "edu-solid-geometry", "problem_type": "solid_explore", "spec": {{"body": "quad_pyramid", "base_edge": 4, "height": 3}}}}
命中示例（概念课·椭圆的定义）：
{{"match": true, "skill": "edu-analytic-geometry", "problem_type": "curve_explore", "spec": {{"curve": "ellipse", "a": 2, "b": 1}}}}
未命中：
{{"match": false}}
"""
    return await _classify(cfg, prompt)


# ---------------------------------------------------------------------------
# 路由：化学 / 生物（化学反应）
# ---------------------------------------------------------------------------
async def route_chem_lab_point(
    point: dict,
    subject_name: str,
    lab_key: str | None = None,
    force: bool = False,
) -> dict | None:
    """宏观实验台路由：指定 key 或关键词命中；force 时用默认制氧实验。"""
    if not force and not lab_key and not _is_lab_subject(subject_name):
        return None
    text = " ".join(str(point.get(k) or "") for k in ("name", "plain_explanation", "activity_goal"))
    key = match_lab_key(text, lab_key)
    if not key and force:
        key = "prep_oxygen_kmno4"
    if not key:
        return None
    return {"skill": "edu-chem-lab", "problem_type": key, "spec": {}}


async def route_chem_point(cfg, point: dict, subject_name: str) -> dict | None:
    """判断化学/生物知识点能否用化学反应 skill 演示。命中返回 routed，否则 None。"""
    if not _is_chem(subject_name):
        return None

    prompt = f"""你是化学/生物课件工具的路由器。判断下面这个知识点是否适合用「反应过程 3D 交互演示」讲解。

知识点名称：{point.get('name', '')}
白话解释：{point.get('plain_explanation', '')}
互动目标：{point.get('activity_goal', '')}

【化学反应 skill：edu-chem-reaction】（problem_type，均为固定反应，spec 留空 {{}}）：
- combustion_ch4：甲烷燃烧 CH₄ + O₂。
- combustion_h2：氢气燃烧 2H₂ + O₂。
- electrolysis_water：电解水（分解反应）。
- redox_na_cl2：钠与氯气 2Na + Cl₂（氧化还原·电子转移）。
- esterification：酯化反应（乙酸 + 乙醇，机理·过渡态）。
- glucose_combustion：葡萄糖有氧氧化 C₆H₁₂O₆ + 6O₂（细胞呼吸，适合生物）。

规则：
1. 只有知识点确实对应上述某反应时才命中；否则返回 {{"match": false}}。
2. spec 一律为 {{}}。
3. 只输出 JSON，不要解释，不要 markdown 代码块。

命中示例：
{{"match": true, "skill": "edu-chem-reaction", "problem_type": "combustion_ch4", "spec": {{}}}}
未命中：
{{"match": false}}
"""
    return await _classify(cfg, prompt)


async def _classify(cfg, prompt: str) -> dict | None:
    """调用 LLM 做题型分类，返回校验后的 routed dict，失败/未命中返回 None。"""
    from app.services.ai_service import _call_llm, _resp_content, _parse_json_object
    try:
        resp = await _call_llm(cfg, [{"role": "user", "content": prompt}],
                               max_tokens=max(cfg.max_tokens or 0, 800))
        obj = _parse_json_object(_resp_content(resp)) or {}
    except Exception as e:
        logger.warning("skill 路由调用失败：%s", e)
        return None

    if not obj.get("match"):
        return None
    skill = obj.get("skill")
    pt = obj.get("problem_type")
    caps = SKILL_CAPABILITIES.get(skill, {}).get("problem_types", {})
    if pt not in caps:
        return None
    return {"skill": skill, "problem_type": pt,
            "spec": _normalize_spec(pt, obj.get("spec") or {})}


# 通用兜底题型的合法取值：LLM 给了不认识的几何体/曲线就落到默认，而不是让子进程报错
SOLID_BODIES = ("cube", "cuboid", "quad_pyramid", "tetrahedron", "tri_prism")
EXPLORE_CURVES = ("ellipse", "hyperbola", "parabola", "circle")


def _normalize_spec(problem_type: str, spec: dict) -> dict:
    """把 LLM 给的 spec 收敛到 runner 认识的取值范围内。"""
    if not isinstance(spec, dict):
        return {}
    if problem_type == "solid_explore":
        body = str(spec.get("body", "")).lower()
        spec["body"] = body if body in SOLID_BODIES else "cuboid"
    elif problem_type == "curve_explore":
        curve = str(spec.get("curve", "")).lower()
        spec["curve"] = curve if curve in EXPLORE_CURVES else "ellipse"
    return spec


# ---------------------------------------------------------------------------
# 渲染器
# ---------------------------------------------------------------------------
async def _run_subprocess(argv: list[str], timeout: float) -> bool:
    """运行子进程，成功返回 True。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            logger.warning("skill 子进程失败(rc=%s)：%s", proc.returncode,
                           err.decode("utf-8", "ignore")[:500])
            return False
        return True
    except asyncio.TimeoutError:
        logger.warning("skill 子进程超时：%s", argv[:2])
        return False
    except Exception as e:
        logger.warning("skill 子进程异常：%s", e)
        return False


def _read_html(path: Path) -> str:
    if not path.exists():
        return ""
    html = path.read_text(encoding="utf-8")
    return html if "<html" in html.lower() else ""


async def _render_via_runner(runner_name: str, routed: dict, timeout: float) -> str:
    """调用 skill_runners/<runner_name> 子进程（题型可带参数），返回整页 HTML；失败返回 ''。"""
    runner = SKILL_RUNNERS / runner_name
    if not runner.exists():
        logger.warning("skill runner 不存在：%s", runner)
        return ""
    spec_json = json.dumps({"problem_type": routed["problem_type"], **(routed.get("spec") or {})},
                           ensure_ascii=False)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.html"
        if await _run_subprocess([sys.executable, str(runner), spec_json, str(out)], timeout):
            return _read_html(out)
    return ""


async def render_solid_geometry_html(routed: dict, timeout: float = 40.0) -> str:
    return await _render_via_runner("solid_geometry_runner.py", routed, timeout)


async def render_analytic_geometry_html(routed: dict, timeout: float = 45.0) -> str:
    return await _render_via_runner("analytic_geometry_runner.py", routed, timeout)


async def _render_via_cli(skill_dir: str, key: str, timeout: float = 45.0) -> str:
    """通用 CLI 渲染：调用 skills/<skill_dir>/scripts/generate.py <key> <out>。

    适用于题型为固定场景、无需额外参数的 skill（化学反应）。
    """
    script = SKILLS_ROOT / skill_dir / "scripts" / "generate.py"
    if not script.exists():
        logger.warning("skill 脚本不存在：%s", script)
        return ""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.html"
        if await _run_subprocess([sys.executable, str(script), key, str(out)], timeout):
            return _read_html(out)
    return ""


async def render_chem_reaction_html(routed: dict, timeout: float = 45.0) -> str:
    return await _render_via_cli("edu-chem-reaction", routed["problem_type"], timeout)


async def render_chem_lab_html(routed: dict, timeout: float = 45.0) -> str:
    return await _render_via_cli("edu-chem-lab", routed["problem_type"], timeout)


async def render_bio_html(routed: dict, timeout: float = 30.0) -> str:
    return await _render_via_cli("edu-bio", routed["problem_type"], timeout)


async def render_physics_html(routed: dict, timeout: float = 30.0) -> str:
    return await _render_via_cli("edu-physics", routed["problem_type"], timeout)


_RENDERERS = {
    "edu-solid-geometry": render_solid_geometry_html,
    "edu-analytic-geometry": render_analytic_geometry_html,
    "edu-chem-reaction": render_chem_reaction_html,
    "edu-chem-lab": render_chem_lab_html,
    "edu-bio": render_bio_html,
    "edu-physics": render_physics_html,
}


async def render_skill_html(routed: dict, timeout: float | None = None) -> str:
    """按 routed.skill 调对应渲染器；未知 skill 或失败返回空串。"""
    renderer = _RENDERERS.get((routed or {}).get("skill") or "")
    if not renderer:
        return ""
    if timeout is None:
        return await renderer(routed)
    return await renderer(routed, timeout)


# ---------------------------------------------------------------------------
# 统一入口：供 ai_service 调用。命中并成功则返回整页 HTML，否则返回 ''。
# ---------------------------------------------------------------------------
async def maybe_generate_skill(
    cfg, point: dict, subject_name: str,
    *, lab_key: str | None = None, prefer_lab: bool = False,
) -> tuple[str, dict | None]:
    """尝试用 skill 生成互动 HTML，并带回可导出的 routed 规格。失败返回 ('', None)。"""
    routed = None
    try:
        if prefer_lab or lab_key:
            routed = await route_chem_lab_point(
                point, subject_name, lab_key=lab_key, force=prefer_lab,
            )
        if not routed:
            if _is_math(subject_name):
                routed = await route_math_point(cfg, point, subject_name)
            elif _is_physics(subject_name):
                routed = route_physics_point(point, subject_name)
            elif _is_bio(subject_name):
                routed = route_bio_point(point, subject_name)
                if not routed:
                    routed = await route_chem_point(cfg, point, subject_name)
            elif _is_chem(subject_name):
                routed = await route_chem_point(cfg, point, subject_name)
    except Exception as e:
        logger.warning("skill 路由异常：%s", e)
        return "", None

    if not routed:
        return "", None

    renderer = _RENDERERS.get(routed["skill"])
    if not renderer:
        return "", None
    html = await render_skill_html(routed)
    if not html:
        return "", None
    logger.info("知识点「%s」命中 skill %s/%s", point.get("name"),
                routed["skill"], routed["problem_type"])
    return html, {
        "skill": routed["skill"],
        "problem_type": routed["problem_type"],
        "spec": routed.get("spec") or {},
    }


async def maybe_generate_skill_html(cfg, point: dict, subject_name: str) -> str:
    """尝试用 skill 为知识点生成整页互动 HTML；不命中或失败返回 ''。"""
    html, _ = await maybe_generate_skill(cfg, point, subject_name)
    return html
