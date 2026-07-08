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
        },
    },
    "edu-analytic-geometry": {
        "subjects": ["数学"],
        # 这些题型是固定的“示例题场景”，路由器只需选出最贴近的 key（无需 spec）
        "problem_types": {
            "ellipse_dot_range": "椭圆·过焦点弦上向量数量积的取值范围",
            "ellipse_chord_range": "椭圆·过焦点弦弦长的取值范围",
            "ellipse_area_max": "椭圆·三角形面积最值",
            "ellipse_slopeprod_const": "椭圆·中心对称弦斜率之积为定值",
            "parabola_dot_const": "抛物线·焦点弦向量数量积为定值",
            "hyperbola_ecc_range": "双曲线·离心率取值范围",
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
}


def _is_math(subject: str) -> bool:
    return "数学" in (subject or "")


def _is_chem(subject: str) -> bool:
    s = subject or ""
    return ("化学" in s) or ("生物" in s)


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

规则：
1. 只有知识点确实属于上述某题型时才命中；否则返回 {{"match": false}}。
2. 命中立体几何题型时给出合理示例参数（正整数、尽量小、答案规整）；解析几何 spec 一律为 {{}}。
3. 只输出 JSON，不要解释，不要 markdown 代码块。

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
未命中：
{{"match": false}}
"""
    return await _classify(cfg, prompt)


# ---------------------------------------------------------------------------
# 路由：化学 / 生物（化学反应）
# ---------------------------------------------------------------------------
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
    return {"skill": skill, "problem_type": pt, "spec": obj.get("spec") or {}}


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


async def render_solid_geometry_html(routed: dict, timeout: float = 40.0) -> str:
    """调用 solid_geometry_runner 子进程（题型带参数），返回整页 HTML；失败返回 ''。"""
    runner = SKILL_RUNNERS / "solid_geometry_runner.py"
    if not runner.exists():
        logger.warning("solid_geometry_runner 不存在：%s", runner)
        return ""
    spec_json = json.dumps({"problem_type": routed["problem_type"], **(routed.get("spec") or {})},
                           ensure_ascii=False)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "sg.html"
        if await _run_subprocess([sys.executable, str(runner), spec_json, str(out)], timeout):
            return _read_html(out)
    return ""


async def _render_via_cli(skill_dir: str, key: str, timeout: float = 45.0) -> str:
    """通用 CLI 渲染：调用 skills/<skill_dir>/scripts/generate.py <key> <out>。

    适用于解析几何、化学（题型为固定场景，无需额外参数）。
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


async def render_analytic_geometry_html(routed: dict, timeout: float = 45.0) -> str:
    return await _render_via_cli("edu-analytic-geometry", routed["problem_type"], timeout)


async def render_chem_reaction_html(routed: dict, timeout: float = 45.0) -> str:
    return await _render_via_cli("edu-chem-reaction", routed["problem_type"], timeout)


_RENDERERS = {
    "edu-solid-geometry": render_solid_geometry_html,
    "edu-analytic-geometry": render_analytic_geometry_html,
    "edu-chem-reaction": render_chem_reaction_html,
}


# ---------------------------------------------------------------------------
# 统一入口：供 ai_service 调用。命中并成功则返回整页 HTML，否则返回 ''。
# ---------------------------------------------------------------------------
async def maybe_generate_skill_html(cfg, point: dict, subject_name: str) -> str:
    """尝试用 skill 为知识点生成整页互动 HTML；不命中或失败返回 ''。"""
    routed = None
    try:
        if _is_math(subject_name):
            routed = await route_math_point(cfg, point, subject_name)
        elif _is_chem(subject_name):
            routed = await route_chem_point(cfg, point, subject_name)
    except Exception as e:
        logger.warning("skill 路由异常：%s", e)
        return ""

    if not routed:
        return ""

    renderer = _RENDERERS.get(routed["skill"])
    if not renderer:
        return ""
    html = await renderer(routed)
    if html:
        logger.info("知识点「%s」命中 skill %s/%s", point.get("name"),
                    routed["skill"], routed["problem_type"])
    return html
