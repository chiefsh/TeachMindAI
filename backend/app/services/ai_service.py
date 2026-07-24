"""AI 生成服务：课件、作业、OCR、成绩分析"""
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decrypt_api_key
from app.models.courseware import Courseware
from app.models.homework import HomeworkPaper, HomeworkQuestion
from app.models.textbook import Textbook, TextbookChapter, ParseStatus
from app.models.education import Subject
from app.models.subject_prompt import SubjectPromptTemplate
from app.models.llm_config import LLMConfig
from app.models.question import Question

logger = logging.getLogger(__name__)


async def _get_default_llm(teacher_id: int, db: AsyncSession):
    result = await db.execute(
        select(LLMConfig).where(
            LLMConfig.teacher_id == teacher_id,
            LLMConfig.is_default == True,
            LLMConfig.is_active == True,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        result = await db.execute(
            select(LLMConfig).where(
                LLMConfig.teacher_id == teacher_id,
                LLMConfig.is_active == True,
            ).limit(1)
        )
        cfg = result.scalar_one_or_none()
    return cfg


# litellm 原生支持的 provider 前缀（这些可不依赖 base_url 直接路由）
_NATIVE_LITELLM_PROVIDERS = {
    "openai", "anthropic", "deepseek", "ollama", "azure", "gemini", "mistral",
}


def build_litellm_kwargs(cfg: LLMConfig, api_key: str | None) -> dict:
    """构造传给 litellm 的参数。

    关键点：litellm 需要知道模型属于哪个 provider，否则会报
    "LLM Provider NOT provided"。
    - 模型名已带前缀（如 openai/xxx）：原样使用
    - 配置了 base_url（OpenAI 兼容接口，如通义/智谱/自建网关）：用 openai/ 前缀走兼容通道
    - litellm 原生支持的 provider：用 provider/model 形式
    - 其余情况：默认按 openai 处理
    """
    name = cfg.model_name
    if "/" in name:
        model = name
    elif cfg.base_url:
        model = f"openai/{name}"
    elif cfg.provider in _NATIVE_LITELLM_PROVIDERS and cfg.provider != "openai":
        model = f"{cfg.provider}/{name}"
    else:
        model = name

    kwargs: dict = {"model": model, "api_key": api_key}
    if cfg.base_url:
        kwargs["api_base"] = cfg.base_url
    return kwargs


async def _call_llm(cfg: LLMConfig, messages: list[dict], stream: bool = False, max_tokens: int | None = None):
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    # 兜底：max_tokens 为空或非法时使用合理默认值，避免传 0/None 触发 provider 报错
    effective_max_tokens = max_tokens or cfg.max_tokens
    if not effective_max_tokens or effective_max_tokens <= 0:
        effective_max_tokens = 4096
    return await litellm.acompletion(
        messages=messages,
        temperature=cfg.temperature,
        max_tokens=effective_max_tokens,
        stream=stream,
        **build_litellm_kwargs(cfg, api_key),
    )


def _resp_content(resp) -> str:
    """从 LLM 响应稳健提取正文。

    - 兼容推理模型：content 为空时回退到 reasoning_content。
    - 当 finish_reason=length（被 max_tokens 截断）时打日志，便于排查。
    """
    try:
        choice = resp.choices[0]
    except (AttributeError, IndexError):
        logger.warning("LLM 响应无 choices：%r", resp)
        return ""

    msg = getattr(choice, "message", None)
    content = (getattr(msg, "content", None) or "") if msg else ""

    if not content and msg is not None:
        # 推理模型可能把内容放在 reasoning_content
        reasoning = getattr(msg, "reasoning_content", None)
        if not reasoning and isinstance(getattr(msg, "model_extra", None), dict):
            reasoning = msg.model_extra.get("reasoning_content")
        if reasoning:
            logger.warning("LLM content 为空，回退使用 reasoning_content（长度 %s）", len(reasoning))
            content = reasoning

    if not content:
        finish = getattr(choice, "finish_reason", None)
        usage = getattr(resp, "usage", None)
        logger.warning(
            "LLM 返回空内容，finish_reason=%s，usage=%s（可能被 max_tokens 截断或推理耗尽）",
            finish, usage,
        )

    return content or ""


async def do_generate_courseware(courseware_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Courseware).where(Courseware.id == courseware_id))
        cw = result.scalar_one_or_none()
        if not cw:
            # 行可能尚未提交（极端时序），抛错让任务重试
            raise ValueError(f"课件 {courseware_id} 不存在，稍后重试")

        cw.gen_status = ParseStatus.processing
        await db.commit()

        try:
            cfg = await _get_default_llm(cw.teacher_id, db)
            if not cfg:
                cw.gen_status = ParseStatus.failed
                await db.commit()
                return

            # 获取课本内容
            chapter_content = ""
            image_catalog = ""
            subject_name = ""
            subject_block = ""
            subject_interactive = ""
            if cw.textbook_id:
                # 依据教师选择的「章节多选」或「页码范围」筛选课本内容
                chapter_ids = None
                if isinstance(cw.chapter_range, dict):
                    ids = cw.chapter_range.get("chapter_ids")
                    if isinstance(ids, list) and ids:
                        chapter_ids = [int(x) for x in ids]
                page_start = page_end = None
                if isinstance(cw.page_range, dict):
                    page_start = cw.page_range.get("start")
                    page_end = cw.page_range.get("end")

                # 选中父章节时，展开其所有后代节点，纳入其下各节内容
                if chapter_ids:
                    rows = (await db.execute(
                        select(TextbookChapter.id, TextbookChapter.parent_id)
                        .where(TextbookChapter.textbook_id == cw.textbook_id)
                    )).all()
                    children_map: dict[int | None, list[int]] = {}
                    for cid, pid in rows:
                        children_map.setdefault(pid, []).append(cid)
                    expanded: set[int] = set()
                    stack = list(chapter_ids)
                    while stack:
                        cid = stack.pop()
                        if cid in expanded:
                            continue
                        expanded.add(cid)
                        stack.extend(children_map.get(cid, []))
                    chapter_ids = list(expanded)

                ch_q = select(TextbookChapter).where(TextbookChapter.textbook_id == cw.textbook_id)
                if chapter_ids:
                    ch_q = ch_q.where(TextbookChapter.id.in_(chapter_ids))
                elif page_start and page_end:
                    # 章节页码范围与 [start, end] 有交集即纳入
                    ch_q = ch_q.where(
                        TextbookChapter.page_start <= page_end,
                        TextbookChapter.page_end >= page_start,
                    )
                ch_q = ch_q.order_by(TextbookChapter.sort_order).limit(200)
                chapters = (await db.execute(ch_q)).scalars().all()

                # 若按条件未命中（例如页码/章节无匹配），回退到前 40 条，避免空内容
                if not chapters:
                    chapters = (await db.execute(
                        select(TextbookChapter)
                        .where(TextbookChapter.textbook_id == cw.textbook_id)
                        .order_by(TextbookChapter.sort_order)
                        .limit(40)
                    )).scalars().all()

                chapter_content = "\n\n".join(
                    f"## {c.title}\n{c.content or ''}" for c in chapters
                )

                # 依据所选章节/页码，确定图片可用页码范围
                img_lo, img_hi = page_start, page_end
                if chapter_ids and chapters:
                    ch_pages = [c.page_start for c in chapters if c.page_start] + \
                               [c.page_end for c in chapters if c.page_end]
                    if ch_pages:
                        img_lo, img_hi = min(ch_pages), max(ch_pages)

                # 可用课本插图清单（供模型引用）
                from app.models.textbook import TextbookImage
                img_q = (
                    select(TextbookImage)
                    .where(TextbookImage.textbook_id == cw.textbook_id)
                )
                if img_lo and img_hi:
                    img_q = img_q.where(
                        TextbookImage.page_number >= img_lo,
                        TextbookImage.page_number <= img_hi,
                    )
                img_q = img_q.order_by(TextbookImage.sort_order).limit(40)
                imgs = (await db.execute(img_q)).scalars().all()
                if imgs:
                    image_catalog = "\n".join(
                        f"- 图#{img.id}（位于课本第 {img.page_number} 页）" for img in imgs
                    )

                # 解析该课本所属科目的专属提示词
                tb = (await db.execute(
                    select(Textbook).where(Textbook.id == cw.textbook_id)
                )).scalar_one_or_none()
                if tb:
                    subject_name, subject_block, subject_interactive = await _resolve_subject_prompt(
                        db, cw.teacher_id, tb.subject_id
                    )

            content = await _generate_lesson_content(
                cfg, cw, chapter_content, image_catalog,
                subject_name, subject_block, subject_interactive,
            )
            cw.content = content
            cw.gen_status = ParseStatus.done
        except Exception as e:
            logger.exception("课件 %s 生成失败：%s", cw.id, e)
            cw.gen_status = ParseStatus.failed
        finally:
            await db.commit()

        # 生成成功后异步把知识点回填到知识图谱（best-effort，不影响课件本身）
        if cw.gen_status == ParseStatus.done:
            try:
                from app.tasks.knowledge_tasks import persist_courseware_kps_task
                persist_courseware_kps_task.delay(cw.id)
            except Exception as e:  # noqa: BLE001
                logger.warning("课件 %s 知识点入图任务派发失败：%s", cw.id, e)


async def _resolve_subject_prompt(db: AsyncSession, teacher_id: int, subject_id: int) -> tuple[str, str]:
    """根据科目解析专属提示词，返回 (科目名, 提示词文本块)。

    解析顺序：教师覆盖 > 系统默认 > 通用兜底。
    """
    from app.core.seed import GENERIC_SUBJECT_PROMPT

    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )).scalar_one_or_none()
    if not subject:
        return "", "", ""
    name = subject.name

    tpl = None
    for tid in (teacher_id, None):  # 先找教师覆盖，再找系统默认
        res = await db.execute(
            select(SubjectPromptTemplate).where(
                SubjectPromptTemplate.subject_name == name,
                SubjectPromptTemplate.teacher_id == tid if tid is not None
                else SubjectPromptTemplate.teacher_id.is_(None),
                SubjectPromptTemplate.is_active == True,
            )
        )
        tpl = res.scalar_one_or_none()
        if tpl:
            break

    if tpl:
        block = tpl.prompt
        interactive = tpl.interactive_guidance or ""
    else:
        block = GENERIC_SUBJECT_PROMPT
        interactive = ""
    return name, block, interactive


def _strip_code_fences(text: str) -> str:
    """去除 ```json ... ``` 之类的 markdown 代码围栏。"""
    t = (text or "").strip()
    if t.startswith("```"):
        # 去掉首行围栏（``` 或 ```json）
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1:]
        # 去掉结尾围栏
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _balance_json(text: str) -> str:
    """对（可能被截断的）JSON 文本做括号/字符串平衡补全，使其尽量可被解析。"""
    in_str = False
    esc = False
    stack: list[str] = []
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()
    if in_str:
        text += '"'
    # 去掉可能的悬空逗号
    text = text.rstrip()
    while text.endswith(",") or text.endswith(":"):
        text = text[:-1].rstrip()
    for ch in reversed(stack):
        text += "}" if ch == "{" else "]"
    return text


def _parse_lesson_json(raw: str) -> dict | None:
    """从 LLM 原始输出中尽量稳健地解析课件 JSON；失败返回 None。

    依次尝试：直接解析 → 截断到错误位置后平衡补全 → 退到最后一个完整 slide 后补全。
    """
    if not raw:
        return None
    text = _strip_code_fences(raw)
    start = text.find("{")
    if start < 0:
        return None
    text = text[start:]

    # 1) 直接解析（去掉结尾多余字符）
    end = text.rfind("}")
    if end != -1:
        try:
            data = json.loads(text[: end + 1])
            if data.get("slides"):
                return data
        except Exception:
            pass

    # 2) 利用解析错误位置砍断 + 平衡补全（应对截断 / 局部非法）
    candidate = text
    for _ in range(5):
        try:
            data = json.loads(candidate)
            if data.get("slides"):
                return data
            return None
        except json.JSONDecodeError as e:
            cut = candidate[: e.pos] if e.pos and e.pos > 0 else candidate
            fixed = _balance_json(cut)
            try:
                data = json.loads(fixed)
                if data.get("slides"):
                    return data
            except Exception:
                pass
            # 退到最后一个完整 slide 对象（"}," 边界）后再补全
            last = cut.rfind("},")
            if last == -1:
                break
            candidate = _balance_json(cut[: last + 1])
    return None


def _parse_json_object(raw: str) -> dict | None:
    """尽量稳健地从 LLM 输出中提取 JSON 对象。"""
    if not raw:
        return None
    text = _strip_code_fences(raw)
    start = text.find("{")
    if start < 0:
        return None
    text = text[start:]

    end = text.rfind("}")
    if end != -1:
        try:
            obj = json.loads(text[: end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    candidate = text
    for _ in range(3):
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError as e:
            cut = candidate[: e.pos] if e.pos and e.pos > 0 else candidate
            fixed = _balance_json(cut)
            try:
                obj = json.loads(fixed)
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
            last = cut.rfind("},")
            if last == -1:
                break
            candidate = _balance_json(cut[: last + 1])
    return None


def _normalize_knowledge_points(raw_points: list, max_points: int = 4) -> list[dict]:
    """规范化知识点结构，保证后续组装课件稳定。"""
    out: list[dict] = []
    for i, p in enumerate(raw_points or []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or p.get("title") or f"知识点{i + 1}").strip()
        if not name:
            name = f"知识点{i + 1}"
        plain = str(p.get("plain_explanation") or p.get("explanation") or "").strip()
        concepts = p.get("core_concepts") if isinstance(p.get("core_concepts"), list) else []
        concepts = [str(x).strip() for x in concepts if str(x).strip()][:5]
        mistakes = p.get("common_mistakes") if isinstance(p.get("common_mistakes"), list) else []
        mistakes = [str(x).strip() for x in mistakes if str(x).strip()][:3]
        life_example = str(p.get("life_example") or "").strip()
        activity_goal = str(p.get("activity_goal") or f"通过互动练习掌握{name}").strip()
        out.append({
            "name": name[:64],
            "plain_explanation": plain,
            "core_concepts": concepts,
            "common_mistakes": mistakes,
            "life_example": life_example,
            "activity_goal": activity_goal,
        })
    return out[:max_points]


async def _extract_knowledge_points(
    cfg,
    cw,
    chapter_content: str,
    subject_name: str = "",
    subject_block: str = "",
) -> list[dict]:
    """先分析课本内容，抽取可教学的知识点。"""
    subject_hint = ""
    if subject_block:
        subject_hint = (
            f"\n【学科：{subject_name or '通用'}】请结合学科特征抽取知识点。\n{subject_block}\n"
        )
    system_prompt = f"""你是资深教研专家。请先分析课本内容，抽取可直接用于上课的知识点，输出 JSON。{subject_hint}

要求：
1. 只保留最关键、最适合课堂互动的知识点，3~4个。
2. 解释要生动、有趣、直白，便于学生快速理解；每个知识点必须给生活化例子。
3. 每个知识点都给一个可操作的互动目标（activity_goal），用于后续生成互动课件。
4. 只输出 JSON，不要解释，不要 markdown 代码块。

JSON 格式：
{{
  "topic": "本节主题",
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "plain_explanation": "用白话解释",
      "core_concepts": ["要点1", "要点2"],
      "common_mistakes": ["易错1"],
      "life_example": "生活中的例子",
      "activity_goal": "该知识点互动页要达成的学习目标"
    }}
  ]
}}"""
    user_prompt = f"课件课题：{cw.title}\n\n课本内容：\n{chapter_content[:9000]}"
    if cw.custom_prompt:
        user_prompt += f"\n\n教师额外要求（请在知识点中体现）：{cw.custom_prompt}"

    resp = await _call_llm(
        cfg,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=max(cfg.max_tokens or 0, 4000),
    )
    raw = _resp_content(resp)
    obj = _parse_json_object(raw) or {}
    points = _normalize_knowledge_points(obj.get("knowledge_points") or [])
    return points


def _extract_html_from_response(raw: str) -> str:
    """从 LLM 原始响应中提取 HTML 片段。

    优先顺序：
    1. ```html ... ``` 代码块（含 <div）
    2. ``` ... ``` 通用代码块（含 <div）
    3. 完整 HTML 文档 → 提取 <body> 内容
    4. 裸 HTML：首个 <div 到响应末尾
    """
    import re

    def _has_html(s: str) -> bool:
        return bool(re.search(r"<div|<section|<article", s, re.IGNORECASE))

    # 1) ```html ... ```
    m = re.search(r"```html\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if m:
        content = m.group(1).strip()
        if _has_html(content):
            return content

    # 2) 通用代码块里含 HTML
    m = re.search(r"```[a-zA-Z]*\s*([\s\S]*?)```", raw)
    if m:
        content = m.group(1).strip()
        if _has_html(content):
            return content

    # 3) 完整 HTML 文档 → 提取 body 内容
    if re.search(r"<html[\s>]", raw, re.IGNORECASE):
        body_m = re.search(r"<body[^>]*>([\s\S]*?)</body>", raw, re.IGNORECASE)
        if body_m:
            return body_m.group(1).strip()

    # 4) 裸 HTML：首个 HTML 标签到响应末尾
    for tag in ("<div", "<section", "<article", "<main"):
        start = raw.lower().find(tag)
        if start != -1:
            return raw[start:].strip()

    return ""


def _fallback_interactive_html(point: dict, point_idx: int) -> str:
    """当 LLM 无法产出互动 HTML 时，用知识点数据本地拼出一个基础互动卡片。

    保证互动环节始终有可渲染、可作答的内容，而不是空白。
    交互：点击“显示答案/要点”翻开讲解；有误区时做一个“判断对错”小测。
    """
    import html as _html

    name = _html.escape(str(point.get("name") or f"知识点{point_idx}"))
    plain = _html.escape(str(point.get("plain_explanation") or ""))
    life = _html.escape(str(point.get("life_example") or ""))
    concepts = [_html.escape(str(x)) for x in (point.get("core_concepts") or []) if str(x).strip()]
    mistakes = [_html.escape(str(x)) for x in (point.get("common_mistakes") or []) if str(x).strip()]
    goal = _html.escape(str(point.get("activity_goal") or f"巩固「{name}」"))

    concepts_li = "".join(f"<li>{c}</li>" for c in concepts) or "<li>掌握本知识点的核心含义</li>"
    life_block = (
        f"<div class='panel' style='margin-top:12px'><b>生活中的例子</b><p class='muted' style='margin:6px 0 0'>{life}</p></div>"
        if life else ""
    )

    # 误区判断小测：把第一个常见误区作为“错误说法”让学生判断
    quiz_block = ""
    if mistakes:
        wrong_stmt = mistakes[0]
        quiz_block = f"""
  <div class='card' style='margin-top:14px'>
    <p class='badge'>判断题</p>
    <p style='margin:8px 0'>有同学说：“{wrong_stmt}”。这种说法对吗？</p>
    <div class='row'>
      <button class='btn' onclick='cwJudge(this,false)'>✅ 正确</button>
      <button class='btn' onclick='cwJudge(this,true)'>❌ 错误</button>
    </div>
    <div id='cw-fb' class='hint' style='display:none;margin-top:10px'></div>
  </div>"""

    script = """
  <script>
  function cwReveal(btn){
    var box = document.getElementById('cw-explain');
    if(box){ box.style.display='block'; box.classList.add('fade-in'); }
    btn.disabled = true;
    if(window.CW) window.CW.report({question:'查看讲解', answer:'已查看'});
  }
  function cwJudge(btn, isWrongStmt){
    var fb = document.getElementById('cw-fb');
    // 这是一个“错误说法”，正确判断应为“错误”
    var correct = isWrongStmt === true;
    if(fb){
      fb.style.display='block';
      fb.textContent = correct ? '回答正确！这确实是一个常见误区，要避开它。' : '再想想~ 这其实是一个常见误区，说法是不对的。';
    }
    var btns = btn.parentNode.querySelectorAll('.btn');
    btns.forEach(function(b){ b.disabled = true; });
    btn.classList.add(correct ? 'correct' : 'wrong');
    if(window.CW){ correct ? window.CW.correct('误区判断', '错误') : window.CW.wrong('误区判断', '正确'); }
  }
  </script>"""

    return f"""<div class="stage fade-in">
  <p class="title">{name}</p>
  <p class="subtitle">互动目标：{goal}</p>
  <div class="card">
    <p class="badge">核心要点</p>
    <ul style="margin:8px 0 0;padding-left:20px">{concepts_li}</ul>
    {life_block}
    <button class="btn primary" style="margin-top:14px" onclick="cwReveal(this)">显示白话讲解</button>
    <div id="cw-explain" class="panel" style="display:none;margin-top:12px">{plain or '结合课本内容理解本知识点。'}</div>
  </div>
  {quiz_block}
  {script}
</div>"""


async def _generate_interactive_html_for_point(
    cfg,
    cw,
    point: dict,
    point_idx: int,
    subject_name: str,
    image_catalog: str,
    interactive_hint: str,
) -> str:
    """按知识点生成单页互动 HTML（片段）。

    直接要求 LLM 输出 ```html 代码块，完全避免 JSON-in-JSON 的双重转义问题。
    """
    image_ref = f"\n可引用课本图片：\n{image_catalog}" if image_catalog else ""
    prompt = f"""请围绕以下知识点，生成 1 页可直接运行的互动课件 HTML 片段。

课件标题：{cw.title}
知识点序号：{point_idx}
知识点：{point.get("name", "")}
白话解释：{point.get("plain_explanation", "")}
核心要点：{json.dumps(point.get("core_concepts") or [], ensure_ascii=False)}
常见误区：{json.dumps(point.get("common_mistakes") or [], ensure_ascii=False)}
生活例子：{point.get("life_example", "")}
互动目标：{point.get("activity_goal", "")}
学科：{subject_name or "通用"}{image_ref}

风格要求：
- 生动、有趣、直白，语言口语化，句子简短。
- 至少包含 1 个生活化情境、1 个可操作互动（点击/拖拽/输入）。
- 互动后必须给即时反馈；有对错判断时调用 window.CW?.correct(题目, 答案) 或 window.CW?.wrong(题目, 答案)。

【输出格式——严格遵守，不要有任何多余文字】

输出示例（只需这种格式）：
```html
<div class="stage">
  <!-- 你的互动内容 -->
</div>
```

要求：
- 代码块内容以 <div class="stage"> 开头，可包含 <style> 和 <script>，不要写 <html>/<head>/<body>。
- 代码块之外不要输出任何说明或注释。

{interactive_hint}
"""
    # 互动页含 <style>/<script>，输出较长；推理模型还会额外消耗思维 token，
    # 因此给足 max_tokens，避免 content 被截断成空串。
    max_tok = max(cfg.max_tokens or 0, 6000)
    resp = await _call_llm(cfg, [{"role": "user", "content": prompt}], max_tokens=max_tok)
    raw = _resp_content(resp)
    html = _extract_html_from_response(raw)

    # ── 首次未提取到：记录完整原始响应，再重试一次（更简短的提示） ──
    if not html:
        logger.warning(
            "课件 %s 知识点%s 互动页第1次未提取到 HTML，原始响应（前800字）：\n%s",
            cw.id, point_idx, raw[:800],
        )
        retry_prompt = (
            f"请直接输出一个 HTML 代码块（用 ```html 包裹），"
            f"内容是围绕「{point.get('name', '')}」的互动教学页面片段，"
            f"以 <div class=\"stage\"> 开头，含1个可点击互动。"
            f"不要任何说明文字，只输出代码块。"
        )
        resp2 = await _call_llm(cfg, [{"role": "user", "content": retry_prompt}], max_tokens=max_tok)
        raw2 = _resp_content(resp2)
        html = _extract_html_from_response(raw2)
        if not html:
            logger.error(
                "课件 %s 知识点%s 互动页重试后仍无 HTML，使用本地兜底模板。重试原始响应（前800字）：\n%s",
                cw.id, point_idx, raw2[:800],
            )
            # 兜底：用知识点数据本地拼出基础互动卡片，保证互动环节不空白
            return _fallback_interactive_html(point, point_idx)

    # 确保有 stage 根容器
    if not html.lstrip().startswith('<div class="stage"') and not html.lstrip().startswith("<div class='stage'"):
        html = f'<div class="stage">{html}</div>'

    return html


async def _generate_lesson_content(
    cfg, cw, chapter_content: str, image_catalog: str,
    subject_name: str = "", subject_block: str = "", subject_interactive: str = "",
) -> dict:
    """两阶段课件生成：先抽取知识点，再按知识点生成互动课件。"""
    interactive_hint = ""
    if cw.is_interactive:
        from app.services.courseware_components import build_interactive_prompt
        interactive_hint = build_interactive_prompt(subject_interactive)

    # Stage 1: 分析知识点
    points = await _extract_knowledge_points(cfg, cw, chapter_content, subject_name, subject_block)
    if not points:
        logger.warning("课件 %s 未提取到有效知识点，回退到旧版整课件生成", cw.id)
        # 回退：沿用旧版单次生成，避免任务失败
        subject_hint = ""
        if subject_block:
            subject_hint = (
                f"\n\n【本节课所属科目：{subject_name or '通用'}，请严格结合该科目特点设计】\n{subject_block}"
            )
        image_hint = ""
        if image_catalog:
            image_hint = (
                "\n\n【可引用的课本插图】（如某页内容需要配图，把对应图的数字 id 放进该幻灯片的 images 数组）：\n"
                + image_catalog
            )
        system_prompt = f"""你是一位资深的一线教师和课件设计专家。请基于课本内容，设计一节【完整的、可直接照着讲授的】课堂教学课件（类似 PPT），时长约 40-45 分钟。{subject_hint}
要求：
1. 课件需有 meta + slides 结构，每页字段包含 index,type,title,bullets,content,notes。
2. 全部中文，输出严格 JSON，不要 markdown 代码块。
3. 若为互动课件，可在 interactive 页附 html 字段（片段）。
{interactive_hint}
"""
        user_prompt = f"课件课题：{cw.title}\n\n课本内容：\n{chapter_content[:8000]}{image_hint}"
        if cw.custom_prompt:
            user_prompt += f"\n\n教师额外要求：{cw.custom_prompt}"
        resp = await _call_llm(
            cfg,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=max(cfg.max_tokens or 0, 8000),
        )
        raw = resp.choices[0].message.content
        data = _parse_lesson_json(raw)
        if data and data.get("slides"):
            return data
        return {
            "meta": {"title": cw.title},
            "slides": [{"index": 1, "type": "content", "title": cw.title, "content": raw, "bullets": [], "notes": ""}],
        }

    # Stage 2: 按知识点组装课件 + 生成互动页
    slides: list[dict] = []
    idx = 1
    slides.append({
        "index": idx, "type": "title", "title": cw.title, "subtitle": f"{subject_name} · 知识点互动课",
        "bullets": [], "content": "", "notes": "开场：抛出本节核心问题，说明学习目标。"
    })
    idx += 1
    slides.append({
        "index": idx, "type": "objectives", "title": "学习目标", "subtitle": "",
        "bullets": [f"理解：{p['name']}" for p in points[:3]],
        "content": "本节课以核心知识点为主线，通过生活化例子和互动练习帮助学生真正理解与应用。",
        "notes": "用学生听得懂的话解释“学什么、为什么学、怎么学”。",
    })
    idx += 1
    slides.append({
        "index": idx, "type": "intro", "title": "情境导入", "subtitle": "从生活现象切入",
        "bullets": [p.get("life_example") for p in points if p.get("life_example")][:3],
        "content": "先从熟悉的生活场景出发，引出本节知识点，激发学习兴趣。",
        "notes": "引导学生先观察、再表达自己的判断，不急于给标准答案。",
    })
    idx += 1

    # 先拼讲解页骨架；互动 HTML 有限并发生成，缩短墙钟时间
    interactive_jobs: list[tuple[int, int, dict]] = []  # (slide_list_index, point_i, point)
    for point_i, p in enumerate(points, 1):
        bullets = p.get("core_concepts") or []
        if not bullets and p.get("plain_explanation"):
            bullets = [p["plain_explanation"]]
        content_parts = []
        if p.get("plain_explanation"):
            content_parts.append(f"### 先用一句话说清楚\n{p['plain_explanation']}")
        if p.get("common_mistakes"):
            content_parts.append("### 常见误区\n" + "\n".join(f"- {x}" for x in p["common_mistakes"]))
        if p.get("life_example"):
            content_parts.append(f"### 生活中的例子\n- {p['life_example']}")

        slides.append({
            "index": idx,
            "type": "content",
            "title": f"{point_i}. {p['name']}",
            "subtitle": "知识点讲解",
            "bullets": bullets[:5],
            "content": "\n\n".join(content_parts),
            "notes": "讲解要短句、直白。让学生先说自己的理解，再做纠偏。",
        })
        idx += 1

        interactive_slide = {
            "index": idx,
            "type": "interactive",
            "title": f"{point_i}. {p['name']} - 互动练习",
            "subtitle": "边做边学",
            "bullets": [p.get("activity_goal") or "通过互动练习巩固本知识点"],
            "content": "请完成下面互动任务，系统会即时反馈并说明原因。",
            "notes": "先让学生独立操作，再进行讲评。重点解释“为什么对/错”。",
        }
        slides.append(interactive_slide)
        if cw.is_interactive:
            interactive_jobs.append((len(slides) - 1, point_i, p))
        idx += 1

    if interactive_jobs:
        import asyncio
        from app.services import skill_service
        sem = asyncio.Semaphore(3)

        async def _gen_html(point_i: int, p: dict) -> str:
            async with sem:
                html = ""
                try:
                    html = await skill_service.maybe_generate_skill_html(cfg, p, subject_name)
                except Exception as e:
                    logger.warning("课件 %s 知识点 %s skill 生成失败，回退 LLM：%s", cw.id, p.get("name"), e)
                if not html:
                    try:
                        html = await _generate_interactive_html_for_point(
                            cfg=cfg, cw=cw, point=p, point_idx=point_i,
                            subject_name=subject_name, image_catalog=image_catalog,
                            interactive_hint=interactive_hint,
                        )
                    except Exception as e:
                        logger.warning("课件 %s 知识点 %s 互动页生成失败：%s", cw.id, p.get("name"), e)
                return html or ""

        htmls = await asyncio.gather(*[_gen_html(pi, p) for _, pi, p in interactive_jobs])
        for (slide_i, _, _), html in zip(interactive_jobs, htmls):
            if html:
                slides[slide_i]["html"] = html

    slides.append({
        "index": idx,
        "type": "summary",
        "title": "课堂小结",
        "subtitle": "",
        "bullets": [p["name"] for p in points[:4]],
        "content": "回顾每个知识点：是什么、怎么判断、容易错在哪里、怎么在生活中应用。",
        "notes": "让学生复述“今天最重要的三个收获”。",
    })
    idx += 1
    slides.append({
        "index": idx,
        "type": "homework",
        "title": "课后任务",
        "subtitle": "",
        "bullets": [f"围绕“{p['name']}”各完成1道自拟题并说明判断依据" for p in points[:2]],
        "content": "请结合今天的知识点，完成分层练习：基础题巩固 + 一题生活迁移题。",
        "notes": "布置作业时强调“会说出理由”比“只选对答案”更重要。",
    })

    return {
        "meta": {
            "title": cw.title,
            "duration": "45分钟",
            "objectives": [f"掌握：{p['name']}" for p in points[:3]],
            "key_points": [p["name"] for p in points[:3]],
            "difficulties": [m for p in points for m in p.get("common_mistakes", [])][:3],
            # 完整知识点结构，供知识图谱回填（前端展示时可忽略）
            "knowledge_points": points,
        },
        "slides": slides,
    }


async def parse_questions_from_text(cfg, text: str) -> list[dict]:
    """把老师手动输入的文本（可能含一道或多道题）用 LLM 拆分为结构化题目。"""
    system_prompt = """你是题库整理助手。请把老师输入的文本拆分、整理为结构化题目。
- 文本可能包含一道题，也可能包含多道题，请逐题拆分。
- 自动判断每道题的题型与难度。
- question_type 取值：single_choice(单选)/multi_choice(多选)/fill_blank(填空)/true_false(判断)/short_answer(简答)/essay(作文论述)/calculation(计算)
- difficulty 取值：easy/medium/hard/very_hard
- 选择题把选项放进 options，如 {"A":"...","B":"...","C":"...","D":"..."}；非选择题 options 为 null。
- 若原文给出了答案/解析，请填入 answer / explanation，没有则留空字符串。
只输出 JSON，格式：{"questions":[{"question_type":"...","difficulty":"...","content":"题干","options":null,"answer":"","explanation":""}]}"""
    resp = await _call_llm(
        cfg,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:8000]},
        ],
        max_tokens=max(cfg.max_tokens or 0, 4096),
    )
    raw = resp.choices[0].message.content or ""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        return data.get("questions", []) or []
    except Exception:
        return []


async def do_generate_homework(paper_id: int, courseware_ids: list[int], use_question_bank: bool):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(HomeworkPaper).where(HomeworkPaper.id == paper_id))
        paper = result.scalar_one_or_none()
        if not paper:
            raise ValueError(f"作业 {paper_id} 不存在，稍后重试")

        paper.gen_status = ParseStatus.processing
        await db.commit()

        try:
            cfg = await _get_default_llm(paper.teacher_id, db)
            if not cfg:
                paper.gen_status = ParseStatus.failed
                await db.commit()
                return

            # 获取课件内容
            cw_content = ""
            if courseware_ids:
                cw_result = await db.execute(
                    select(Courseware).where(Courseware.id.in_(courseware_ids))
                )
                coursewares = cw_result.scalars().all()
                for cw in coursewares:
                    if cw.content:
                        slides = cw.content.get("slides", [])
                        cw_content += f"\n课件《{cw.title}》\n"
                        cw_content += "\n".join(s.get("content", "") for s in slides[:10])

            config = paper.question_config or {}
            difficulty_map = {"easy": "简单", "medium": "中等", "hard": "较难", "very_hard": "特难"}
            difficulty_label = difficulty_map.get(paper.difficulty, "中等")

            prompt = f"""请根据以下课件内容，出一份{difficulty_label}难度的{'作业' if paper.paper_type == 'homework' else '试卷'}。

课件内容：
{cw_content[:4000]}

题目配置：
{json.dumps(config, ensure_ascii=False)}

请输出 JSON 格式：
{{
  "questions": [
    {{
      "index": 1,
      "type": "single_choice",
      "content": "题干",
      "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
      "answer": "A",
      "explanation": "解析",
      "score": 5
    }}
  ]
}}"""

            resp = await _call_llm(cfg, [{"role": "user", "content": prompt}], max_tokens=max(cfg.max_tokens or 0, 4096))
            raw = resp.choices[0].message.content

            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                data = json.loads(raw[start:end])
                questions = data.get("questions", [])
            except Exception:
                questions = []

            # 存储题目
            for i, q in enumerate(questions):
                hq = HomeworkQuestion(
                    paper_id=paper.id,
                    sort_order=i + 1,
                    content=q.get("content", ""),
                    options=q.get("options"),
                    answer=q.get("answer"),
                    score=q.get("score", 10),
                )
                db.add(hq)

            paper.content = raw
            paper.gen_status = ParseStatus.done
        except Exception as e:
            logger.exception("作业 %s 生成失败：%s", paper.id, e)
            paper.gen_status = ParseStatus.failed
        finally:
            await db.commit()


async def do_ocr_grades(teacher_id: int, filename: str, file_data: bytes) -> dict:
    """使用大模型 Vision 能力识别成绩图片"""
    async with AsyncSessionLocal() as db:
        cfg = await _get_default_llm(teacher_id, db)
        if not cfg:
            return {"error": "未配置 LLM"}

    import base64
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    b64 = base64.b64encode(file_data).decode()

    resp = await litellm.acompletion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "请识别图片中的学生成绩表，以JSON格式返回：{\"students\":[{\"name\":\"姓名\",\"score\":分数}]}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=2048,
        **build_litellm_kwargs(cfg, api_key),
    )
    raw = resp.choices[0].message.content
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {"raw": raw}


async def do_analyze_grades(report_id: int):
    """AI 生成成绩分析文字报告，并把结果持久化到 grade_reports。"""
    from app.models.student import GradeReport, ExamResult, Student
    from app.services.grade_stats import compute_grade_stats

    async with AsyncSessionLocal() as db:
        report = (
            await db.execute(select(GradeReport).where(GradeReport.id == report_id))
        ).scalar_one_or_none()
        if not report:
            raise ValueError(f"分析报告 {report_id} 不存在，稍后重试")

        report.gen_status = ParseStatus.processing
        await db.commit()

        try:
            cfg = await _get_default_llm(report.teacher_id, db)
            if not cfg:
                report.gen_status = ParseStatus.failed
                report.content = {"error": "未配置默认大模型，请先到设置中配置"}
                await db.commit()
                return

            rows = (await db.execute(
                select(ExamResult, Student.name)
                .join(Student, Student.id == ExamResult.student_id)
                .where(
                    ExamResult.teacher_id == report.teacher_id,
                    ExamResult.subject_id == report.subject_id,
                    ExamResult.exam_name == report.exam_name,
                )
            )).all()
            scores = [
                {"name": name, "score": r.score, "full_score": r.full_score}
                for r, name in rows
            ]
            stats = compute_grade_stats(scores)

            prompt = f"""你是一位有经验的教育分析师。请根据以下考试数据，生成一份专业、可操作的成绩分析报告。

考试名称：{report.exam_name}
参考人数：{stats['total']}
平均分：{stats['avg_score']}　最高分：{stats['max_score']}　最低分：{stats['min_score']}
及格率：{stats['pass_rate'] * 100:.1f}%　优秀率：{stats['excellent_rate'] * 100:.1f}%
分数段分布：{json.dumps(stats['score_distribution'], ensure_ascii=False)}
成绩明细（部分）：{json.dumps(scores[:30], ensure_ascii=False)}

请从以下角度分析：
1. 整体成绩水平评价
2. 成绩分布特点
3. 存在的问题与薄弱点
4. 针对性教学建议（具体、可落地）

以 markdown 格式输出报告。"""
            if report.custom_prompt:
                prompt += f"\n\n教师额外要求（请重点体现）：{report.custom_prompt}"

            resp = await _call_llm(cfg, [{"role": "user", "content": prompt}], max_tokens=max(cfg.max_tokens or 0, 4096))
            report.content = {"report": resp.choices[0].message.content, "stats": stats}
            report.gen_status = ParseStatus.done
        except Exception as e:
            logger.exception("成绩 AI 分析 %s 失败：%s", report.id, e)
            report.gen_status = ParseStatus.failed
            report.content = {"error": str(e)}
        finally:
            await db.commit()


# ─── 试题分析 ─────────────────────────────────────────────────────

async def _publish_progress(task_id: str | None, payload: dict):
    """通过 Redis pub/sub 推送任务进度，供 WebSocket 转发给前端。"""
    if not task_id:
        return
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.publish(f"task_progress:{task_id}", json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        logger.warning("推送进度失败 task=%s：%s", task_id, e)


async def parse_questions_from_image(cfg, data: bytes) -> list[dict]:
    """用大模型 Vision 从图片中识别并结构化题目。"""
    import base64
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    b64 = base64.b64encode(data).decode()
    prompt = (
        "请识别图片中的所有题目并结构化为 JSON（只输出 JSON）：\n"
        '{"questions":[{"question_type":"single_choice/multi_choice/fill_blank/true_false/short_answer/essay/calculation",'
        '"difficulty":"easy/medium/hard/very_hard","content":"题干",'
        '"options":{"A":"..","B":".."}或null,"answer":"答案(若有)"}]}'
    )
    resp = await litellm.acompletion(
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        max_tokens=max(cfg.max_tokens or 0, 4096),
        **build_litellm_kwargs(cfg, api_key),
    )
    raw = _resp_content(resp)
    obj = _parse_json_object(raw)
    return (obj or {}).get("questions", []) or []


async def analyze_one_question(cfg, q: dict, subject_name: str = "") -> dict:
    """对单道题做面向学生的图解式解析，返回结构化 dict。

    结构：{思路, steps:[{title,detail,formula}], 知识点:[...], 易错点, 答案}
    """
    subj = f"（{subject_name}）" if subject_name else ""
    opts = q.get("options") or {}
    opt_text = ""
    if opts:
        opt_text = "\n选项：" + "；".join(f"{k}. {v}" for k, v in opts.items())
    known = f"\n参考答案：{q.get('answer')}" if q.get("answer") else ""

    system_prompt = f"""你是一位善于讲题的{subj}名师，目标是让学生"看懂并学会"这道题，讲解要直观、通俗、由浅入深。
请输出 JSON（只输出 JSON，不要多余文字）：
{{
  "思路": "一句话点破解题突破口",
  "steps": [{{"title": "步骤标题", "detail": "详细讲解，通俗易懂", "formula": "可选，关键公式用 LaTeX，如 $x^2$"}}],
  "知识点": ["涉及的核心知识点"],
  "易错点": "学生常见错误提醒",
  "答案": "最终答案"
}}
要求：分步讲解要完整、逻辑清晰；数学/物理/化学要给出关键公式（LaTeX）；语言面向学生。"""
    user = f"题目：{q.get('content', '')}{opt_text}{known}"

    resp = await _call_llm(
        cfg,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}],
        max_tokens=max(cfg.max_tokens or 0, 3000),
    )
    raw = _resp_content(resp)
    obj = _parse_json_object(raw) or {}
    # 归一化：steps 兜底
    if not obj.get("steps") and raw.strip():
        obj.setdefault("steps", [{"title": "解析", "detail": raw.strip()[:2000], "formula": ""}])
    return obj


async def _generate_question_diagram_html(cfg, q: dict, analysis: dict, subject_name: str = "") -> str:
    """尽力为题目生成一段自包含的「图解」HTML 片段（内联 SVG / KaTeX / Chart.js）。

    失败或无法图解时返回空串——前端会退化为纯文字分步解析。
    """
    subj = f"（{subject_name}）" if subject_name else ""
    steps_txt = "；".join(s.get("title", "") for s in (analysis.get("steps") or []))
    system_prompt = f"""你是{subj}教学动画工程师。请针对给定题目和解题思路，生成一段**自包含的 HTML 片段**，用**图解**方式帮助学生直观理解这道题（例如：几何图形用内联 <svg> 绘制、函数/数据用 Chart.js(window.Chart)、公式用 $...$，可加简单标注/高亮）。
要求：
- 只输出被 ```html 代码块包裹的 HTML 片段（以 <div class="stage"> 开头），不要输出 <html>/<head>/<body>。
- 允许使用已注入的 KaTeX（$...$、$$...$$）与 Chart.js（全局 window.Chart）。
- 图示要与本题强相关、简洁清晰；不要长篇文字（文字解析已单独展示）。
- 若本题不适合图解，返回一个含关键结论的简洁卡片即可。"""
    user = (
        f"题目：{q.get('content', '')}\n"
        f"解题思路：{analysis.get('思路', '')}\n"
        f"关键步骤：{steps_txt}\n"
        f"最终答案：{analysis.get('答案', q.get('answer', ''))}"
    )
    try:
        resp = await _call_llm(
            cfg,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}],
            max_tokens=max(cfg.max_tokens or 0, 3000),
        )
        raw = _resp_content(resp)
        return _extract_html_from_response(raw)
    except Exception as e:
        logger.warning("题目图解生成失败：%s", e)
        return ""


async def do_analyze_questions(set_id: int, question_ids: list[int], task_id: str | None = None):
    """对批次中被勾选的题目做 AI 图解解析（有限并发），并通过 Redis 推送实时进度。"""
    import asyncio
    from app.models.question_analysis import AnalysisSet, AnalysisQuestion

    async with AsyncSessionLocal() as db:
        aset = (await db.execute(
            select(AnalysisSet).where(AnalysisSet.id == set_id)
        )).scalar_one_or_none()
        if not aset:
            raise ValueError(f"试题批次 {set_id} 不存在，稍后重试")

        cfg = await _get_default_llm(aset.teacher_id, db)

        subject_name = ""
        subj = (await db.execute(select(Subject).where(Subject.id == aset.subject_id))).scalar_one_or_none()
        if subj:
            subject_name = subj.name

        q_rows = (await db.execute(
            select(AnalysisQuestion).where(
                AnalysisQuestion.set_id == set_id,
                AnalysisQuestion.id.in_(question_ids),
            ).order_by(AnalysisQuestion.seq)
        )).scalars().all()

        for q in q_rows:
            q.selected = True
            q.analysis_status = ParseStatus.processing
        await db.commit()

        total = len(q_rows)
        await _publish_progress(task_id, {"stage": "start", "total": total, "current": 0})

        if not cfg:
            for q in q_rows:
                q.analysis_status = ParseStatus.failed
            await db.commit()
            await _publish_progress(task_id, {"stage": "error", "message": "未配置默认大模型"})
            return

        # 快照题面，LLM 调用不共享 AsyncSession（会话非线程安全）
        jobs = [
            (q.id, q.seq, {"content": q.content, "options": q.options, "answer": q.answer})
            for q in q_rows
        ]
        by_id = {q.id: q for q in q_rows}
        sem = asyncio.Semaphore(3)
        write_lock = asyncio.Lock()
        done_count = 0

        async def _run_one(qid: int, seq: int, qd: dict):
            async with sem:
                await _publish_progress(task_id, {
                    "stage": "processing", "current": done_count, "total": total,
                    "question_id": qid, "seq": seq,
                })
                try:
                    analysis = await analyze_one_question(cfg, qd, subject_name)
                    html = await _generate_question_diagram_html(cfg, qd, analysis, subject_name)
                    return qid, seq, analysis, html or None, None
                except Exception as e:
                    logger.exception("题目 %s 解析失败：%s", qid, e)
                    return qid, seq, None, None, e

        tasks = [asyncio.create_task(_run_one(qid, seq, qd)) for qid, seq, qd in jobs]
        for fut in asyncio.as_completed(tasks):
            qid, seq, analysis, html, err = await fut
            async with write_lock:
                q = by_id[qid]
                if err is None:
                    q.analysis_content = analysis
                    q.analysis_html = html
                    q.analysis_status = ParseStatus.done
                else:
                    q.analysis_status = ParseStatus.failed
                done_count += 1
                await db.commit()
                await _publish_progress(task_id, {
                    "stage": "done_one", "current": done_count, "total": total,
                    "question_id": qid, "seq": seq, "status": q.analysis_status.value,
                })

        await _publish_progress(task_id, {"stage": "completed", "total": total, "current": total})

        # 解析完成后，把题目知识点异步沉淀进知识图谱（best-effort）
        try:
            from app.tasks.knowledge_tasks import persist_analysis_kps_task
            persist_analysis_kps_task.delay(set_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("试题批次 %s 知识点入图任务派发失败：%s", set_id, e)
