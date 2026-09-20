"""AI 生成服务：课件、作业、OCR、成绩分析"""
import asyncio
import copy
import json
import logging
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decrypt_api_key
from app.models.courseware import Courseware, save_courseware_version
from app.models.textbook import Textbook, TextbookChapter, ParseStatus
from app.models.education import Subject
from app.models.subject_prompt import SubjectPromptTemplate
from app.models.llm_config import LLMConfig
from app.models.question import Question

logger = logging.getLogger(__name__)


async def _get_default_llm(_teacher_id: int | None, db: AsyncSession):
    """全站系统默认大模型。_teacher_id 已废弃，保留以免改调用方。"""
    result = await db.execute(
        select(LLMConfig).where(
            LLMConfig.teacher_id.is_(None),
            LLMConfig.is_default == True,
            LLMConfig.is_active == True,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        result = await db.execute(
            select(LLMConfig).where(
                LLMConfig.teacher_id.is_(None),
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


# 上游网关（如 Cloudflare / LiteLLM proxy）常见 120s 读超时 → HTTP 524。
# 非流式要等完整响应才回包，推理模型很容易踩中；流式先吐 token 可保活。
# OpenAI 客户端默认再把 5xx 连着重试 2 次（3×120s），这里关掉，改由我们短间隔重试。
_LLM_ATTEMPTS = 3
_LLM_RETRY_WAIT = (2, 8)
_LLM_TIMEOUT_SECONDS = 300
_LLM_RETRYABLE_MARKERS = (
    "524", "502", "503", "504",
    "timeout", "timed out", "overloaded",
    "rate limit", "429",
    "connection reset", "connecterror", "remoteprotocolerror",
    "server disconnected", "temporarily unavailable",
)


def _is_llm_retryable(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(m in text for m in _LLM_RETRYABLE_MARKERS)


def _delta_field(delta, name: str) -> str:
    if delta is None:
        return ""
    if isinstance(delta, dict):
        value = delta.get(name)
    else:
        value = getattr(delta, name, None)
        if not value and isinstance(getattr(delta, "model_extra", None), dict):
            value = delta.model_extra.get(name)
    return value or ""


async def _collect_stream(resp):
    """把 litellm 流式块拼成与非流式相同的结构，供 _resp_content 使用。"""
    if hasattr(resp, "choices") and not hasattr(resp, "__aiter__"):
        return resp
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = None
    usage = None
    async for chunk in resp:
        usage = getattr(chunk, "usage", None) or usage
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None) or finish_reason
        delta = getattr(choice, "delta", None)
        piece = _delta_field(delta, "content")
        if piece:
            content_parts.append(piece)
        reasoning = _delta_field(delta, "reasoning_content")
        if reasoning:
            reasoning_parts.append(reasoning)
    msg = SimpleNamespace(
        content="".join(content_parts),
        reasoning_content="".join(reasoning_parts) or None,
        model_extra=None,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason=finish_reason)],
        usage=usage,
    )


async def _call_llm(cfg: LLMConfig, messages: list[dict], stream: bool = False, max_tokens: int | None = None):
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    # 兜底：max_tokens 为空或非法时使用合理默认值，避免传 0/None 触发 provider 报错
    effective_max_tokens = max_tokens or cfg.max_tokens
    if not effective_max_tokens or effective_max_tokens <= 0:
        effective_max_tokens = 4096
    call_kwargs = dict(
        messages=messages,
        temperature=cfg.temperature,
        max_tokens=effective_max_tokens,
        # 一律走 HTTP 流式：网关 120s 内看到首包就不会 524；非流式要等整段生成完才回包
        stream=True,
        timeout=_LLM_TIMEOUT_SECONDS,
        num_retries=0,
        **build_litellm_kwargs(cfg, api_key),
    )
    last_exc: BaseException | None = None
    for attempt in range(1, _LLM_ATTEMPTS + 1):
        try:
            resp = await litellm.acompletion(**call_kwargs)
            if stream:
                return resp
            return await _collect_stream(resp)
        except Exception as e:
            last_exc = e
            if attempt >= _LLM_ATTEMPTS or not _is_llm_retryable(e):
                raise
            wait = _LLM_RETRY_WAIT[min(attempt - 1, len(_LLM_RETRY_WAIT) - 1)]
            logger.warning(
                "LLM 调用失败（第 %s/%s 次）：%s；%ss 后重试",
                attempt, _LLM_ATTEMPTS, e, wait,
            )
            await asyncio.sleep(wait)
    raise last_exc  # pragma: no cover


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
            await save_courseware_version(db, cw, cw.teacher_id, skip_if_same=False)
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


def _str_list(raw, limit: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()][:limit]


def _normalize_knowledge_points(raw_points: list, max_points: int = 4) -> list[dict]:
    """规范化知识点结构，保证后续组装课件稳定。空字段保持为空，便于验收。"""
    out: list[dict] = []
    for i, p in enumerate(raw_points or []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or p.get("title") or "").strip()
        if not name:
            name = f"知识点{i + 1}"
        out.append({
            "name": name[:64],
            "plain_explanation": str(p.get("plain_explanation") or p.get("explanation") or "").strip(),
            "core_concepts": _str_list(p.get("core_concepts"), 5),
            "common_mistakes": _str_list(p.get("common_mistakes"), 3),
            "life_example": str(p.get("life_example") or "").strip(),
            "activity_goal": str(p.get("activity_goal") or "").strip(),
            "deep_dive": str(p.get("deep_dive") or "").strip(),
            "teacher_focus": str(p.get("teacher_focus") or "").strip(),
        })
    return out[:max_points]


def _normalize_intro(raw) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    steps = []
    for item in (raw.get("steps") or [])[:4]:
        if isinstance(item, dict) and (item.get("title") or item.get("detail")):
            steps.append({
                "title": str(item.get("title") or "").strip(),
                "detail": str(item.get("detail") or item.get("content") or "").strip(),
            })
    return {
        "title": str(raw.get("title") or "情境导入").strip() or "情境导入",
        "subtitle": str(raw.get("subtitle") or "").strip(),
        "content": str(raw.get("content") or "").strip(),
        "steps": steps,
    }


def _normalize_exercises(raw) -> list[dict]:
    out: list[dict] = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            out.append({"question": item.strip(), "answer": ""})
        elif isinstance(item, dict):
            q = str(item.get("question") or item.get("prompt") or "").strip()
            a = str(item.get("answer") or item.get("answer_hint") or item.get("solution") or "").strip()
            if q:
                out.append({"question": q, "answer": a})
    return out[:6]


def _normalize_homework(raw) -> list[dict]:
    out: list[dict] = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            out.append({"task": item.strip()})
        elif isinstance(item, dict):
            t = str(item.get("task") or item.get("content") or "").strip()
            if t:
                out.append({"task": t})
    return out[:4]


def _normalize_example(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    prompt = str(raw.get("prompt") or raw.get("question") or "").strip()
    solution = str(raw.get("solution") or raw.get("answer") or "").strip()
    if not prompt:
        return None
    return {"prompt": prompt, "solution": solution}


def _normalize_blueprint(obj: dict, *, web_style: bool = False) -> dict:
    grain = str((obj or {}).get("lesson_grain") or "period").strip()
    if grain not in ("period", "unit"):
        grain = "period"
    max_points = 4 if grain == "unit" else 2
    points = _normalize_knowledge_points((obj or {}).get("knowledge_points") or [], max_points)
    return {
        "topic": str((obj or {}).get("topic") or "").strip(),
        "lesson_grain": grain,
        "cover_subtitle": str((obj or {}).get("cover_subtitle") or "").strip(),
        "objectives": _str_list((obj or {}).get("objectives"), 4),
        "intro": _normalize_intro((obj or {}).get("intro")),
        "knowledge_points": points,
        "example": _normalize_example((obj or {}).get("example")),
        "exercises": _normalize_exercises((obj or {}).get("exercises")),
        "homework": _normalize_homework((obj or {}).get("homework")),
        "summary": _str_list((obj or {}).get("summary"), 4),
        "web_style": web_style,
    }


def _point_gaps(p: dict, *, web_style: bool) -> list[str]:
    gaps: list[str] = []
    if not (p.get("name") or "").strip() or str(p.get("name")).startswith("知识点"):
        gaps.append("name")
    if len(p.get("plain_explanation") or "") < 18:
        gaps.append("plain_explanation")
    if len(p.get("core_concepts") or []) < 2:
        gaps.append("core_concepts")
    if not p.get("life_example"):
        gaps.append("life_example")
    if not p.get("common_mistakes"):
        gaps.append("common_mistakes")
    if web_style and len(p.get("deep_dive") or "") < 40:
        gaps.append("deep_dive")
    return gaps


def _blueprint_gaps(bp: dict) -> list[str]:
    gaps: list[str] = []
    web_style = bool(bp.get("web_style"))
    if not bp.get("topic"):
        gaps.append("topic")
    if len(bp.get("objectives") or []) < 2:
        gaps.append("objectives")
    if len((bp.get("intro") or {}).get("steps") or []) < 2:
        gaps.append("intro")
    points = bp.get("knowledge_points") or []
    if not points:
        gaps.append("knowledge_points")
    else:
        for i, p in enumerate(points, 1):
            for g in _point_gaps(p, web_style=web_style):
                gaps.append(f"point{i}.{g}")
    if len(bp.get("exercises") or []) < 2:
        gaps.append("exercises")
    if not bp.get("homework"):
        gaps.append("homework")
    if len(bp.get("summary") or []) < 2:
        gaps.append("summary")
    return gaps


def _fill_blueprint_gaps(bp: dict, cw) -> dict:
    """抽取仍缺字段时，用已有知识点补具体内容，禁止再写万能套话或自拟题。"""
    points = bp.get("knowledge_points") or []
    if not bp.get("topic"):
        bp["topic"] = (points[0]["name"] if points else cw.title)
    if not bp.get("cover_subtitle"):
        bp["cover_subtitle"] = f"{cw.title} · 本课时" if bp["topic"] != cw.title else ""
    if len(bp.get("objectives") or []) < 2:
        derived = list(bp.get("objectives") or [])
        for p in points:
            for c in p.get("core_concepts") or []:
                derived.append(f"能指出：{c}")
            if p.get("life_example"):
                derived.append(f"能结合「{p['life_example'][:24]}」说明{p['name']}")
        bp["objectives"] = derived[:4] or [f"能说明「{bp['topic']}」并给出判断依据"]
    intro = bp.get("intro") or _normalize_intro({})
    if len(intro.get("steps") or []) < 2:
        steps = []
        for p in points:
            if p.get("life_example"):
                steps.append({"title": "观察", "detail": p["life_example"]})
                steps.append({
                    "title": "追问",
                    "detail": f"这个现象和「{p['name']}」有什么关系？先让学生说，再进新知。",
                })
        if not steps:
            steps = [
                {"title": "定向", "detail": f"今天只解决：{bp['topic']}。先问学生已经知道什么。"},
                {"title": "证据", "detail": "不能停在感觉上，要用实验或具体例子拿出证据。"},
            ]
        intro["steps"] = steps[:4]
        intro["content"] = intro.get("content") or f"用具体情境引出「{bp['topic']}」，不要空讲生活。"
        bp["intro"] = intro
    if not bp.get("example") and points:
        p0 = points[0]
        mistake = (p0.get("common_mistakes") or ["只记结论，说不出依据"])[0]
        bp["example"] = {
            "prompt": f"有同学说：“{mistake}”。这种说法对吗？请说明理由。",
            "solution": p0.get("plain_explanation") or f"对照「{p0['name']}」的核心要点判断。",
        }
    if len(bp.get("exercises") or []) < 2:
        exercises = list(bp.get("exercises") or [])
        for p in points:
            for m in p.get("common_mistakes") or []:
                exercises.append({
                    "question": f"判断：{m}。对还是错？依据是什么？",
                    "answer": "这是常见误区，说法不正确。",
                })
            for c in p.get("core_concepts") or []:
                exercises.append({
                    "question": f"用一句话解释：{c}",
                    "answer": p.get("plain_explanation") or "",
                })
        bp["exercises"] = exercises[:4]
    product_task = {
        "task": "作品：给一个未知对象写一张小体检单（现象/操作 → 结论 → 依据），下节课用 1 分钟交流。",
    }
    if not bp.get("homework"):
        tasks = []
        if points and points[0].get("life_example"):
            tasks.append({"task": f"基础：结合「{points[0]['life_example']}」写 3 句判断依据，不要只抄结论。"})
        else:
            tasks.append({"task": f"基础：用自己的话写出「{bp['topic']}」的判断依据，举一个具体例子。"})
        tasks.append({"task": "规范：写出今天最容易错的一点，并改成正确说法。"})
        tasks.append(product_task)
        bp["homework"] = tasks[:4]
    else:
        tasks = list(bp["homework"])
        blob = " ".join(str(t.get("task") if isinstance(t, dict) else t) for t in tasks)
        if "作品" not in blob and "体检单" not in blob:
            tasks.append(product_task)
        bp["homework"] = tasks[:4]
    if len(bp.get("summary") or []) < 2:
        takeaways = []
        for p in points:
            takeaways.extend(p.get("core_concepts") or [])
        bp["summary"] = takeaways[:4] or [bp["topic"], "能说出判断依据"]
    return bp


def _teacher_intent(cw) -> str:
    return str(getattr(cw, "custom_prompt", None) or "").strip()


def _interactive_teacher_intent_block(cw, point: dict) -> str:
    intent = _teacher_intent(cw)
    if not intent:
        return ""
    block = f"\n教师本课要求（互动设计必须呼应，题干、情境、反馈都要对齐）：{intent}"
    focus = str(point.get("teacher_focus") or "").strip()
    if focus:
        block += f"\n本知识点落实要点：{focus}"
    return block


def _inject_teacher_intent(slides: list[dict], intent: str) -> None:
    """先把教师想法写进封面、目标、练习、作业，保证课件里看得见。"""
    if not intent:
        return
    for slide in slides:
        stype = slide.get("type")
        if stype == "cover":
            notes = (slide.get("notes") or "").strip()
            line = f"教师想法：{intent}"
            if line not in notes:
                slide["notes"] = f"{line}\n{notes}".strip() if notes else line
        elif stype == "objectives":
            extra = f"落实教师想法：{intent}"
            bullets = [str(b) for b in (slide.get("bullets") or [])]
            if not any(intent[:24] in str(b) for b in bullets):
                bullets.append(extra)
            slide["bullets"] = bullets[:6]
            content = (slide.get("content") or "").strip()
            if "教师本课要求" not in content:
                slide["content"] = (content + f"\n\n### 教师本课要求\n{intent}").strip()
        elif stype in ("exercise", "homework"):
            content = (slide.get("content") or "").strip()
            if intent not in content:
                label = "练习需对齐教师要求" if stype == "exercise" else "作业需对齐教师要求"
                slide["content"] = f"{content}\n\n{label}：{intent}".strip()


def _merge_slide_patch(slide: dict, patch: dict) -> None:
    if not isinstance(patch, dict):
        return
    for key in ("title", "subtitle", "content", "notes", "prompt", "solution"):
        val = patch.get(key)
        if isinstance(val, str) and val.strip():
            slide[key] = val.strip()
    bullets = patch.get("bullets")
    if isinstance(bullets, list):
        cleaned = [str(x).strip() for x in bullets if str(x).strip()][:8]
        if cleaned:
            slide["bullets"] = cleaned
    steps = patch.get("steps")
    if isinstance(steps, list) and steps:
        cleaned_steps = []
        for item in steps[:6]:
            if isinstance(item, dict) and (item.get("title") or item.get("detail")):
                cleaned_steps.append({
                    "title": str(item.get("title") or "").strip(),
                    "detail": str(item.get("detail") or "").strip(),
                })
        if cleaned_steps:
            slide["steps"] = cleaned_steps


async def _apply_teacher_intent(cfg, cw, lesson: dict, intent: str) -> dict:
    """按教师想法改写页文案，不增删页、不改 type/html/images。"""
    if not intent:
        return lesson
    slides = lesson.get("slides") or []
    if not slides:
        return lesson
    _inject_teacher_intent(slides, intent)

    slim = []
    for slide in slides:
        slim.append({
            "index": slide.get("index"),
            "type": slide.get("type"),
            "title": slide.get("title"),
            "subtitle": slide.get("subtitle"),
            "bullets": slide.get("bullets") or [],
            "content": (slide.get("content") or "")[:800],
            "notes": slide.get("notes") or "",
            "prompt": slide.get("prompt") or "",
            "solution": slide.get("solution") or "",
        })
    system = """你是一线教研员。按教师想法改写已有课件文案。
硬性规则：
1. 不增删页，不改 index/type，不要输出 html/images/skill。
2. 只改 title/subtitle/bullets/content/notes/prompt/solution，必须落实教师想法。
3. 封面 notes、学习目标、讲解、例题、练习、作业必须明显体现教师要求（难度、侧重、例题、节奏）。
4. 只输出 JSON：{"slides":[{...}]}，不要 markdown。"""
    user = (
        f"课题：{cw.title}\n\n【教师想法——必须落实】\n{intent}\n\n"
        f"现有页面：\n{json.dumps(slim, ensure_ascii=False)}"
    )
    try:
        resp = await _call_llm(
            cfg,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max(cfg.max_tokens or 0, 6000),
        )
        raw = _resp_content(resp)
        data = _parse_json_object(raw)
        patches = (data or {}).get("slides")
        if not isinstance(patches, list):
            logger.warning("课件 %s 教师想法改写未返回 slides", getattr(cw, "id", "?"))
        else:
            by_index = {
                p.get("index"): p
                for p in patches
                if isinstance(p, dict) and p.get("index") is not None
            }
            for slide in slides:
                patch = by_index.get(slide.get("index"))
                if patch:
                    _merge_slide_patch(slide, patch)
            logger.info("课件 %s 已按教师想法改写文案", getattr(cw, "id", "?"))
        lesson.setdefault("meta", {})["teacher_intent"] = intent
    except Exception as e:
        logger.warning("课件 %s 教师想法改写失败，保留直写内容：%s", getattr(cw, "id", "?"), e)
        lesson.setdefault("meta", {})["teacher_intent"] = intent
    return lesson


def _lesson_extract_prompts(cw, chapter_content: str, subject_name: str, subject_block: str, web_style: bool, missing: list[str] | None = None):
    subject_hint = ""
    if subject_block:
        subject_hint = (
            f"\n【学科：{subject_name or '通用'}】请结合学科特征设计一节 45 分钟课。\n{subject_block}\n"
        )
    web_rule = ""
    deep_dive_field = ""
    if web_style:
        web_rule = (
            "\n5. 本课件将以【网页】形式呈现，学生会自己滚动阅读："
            "plain_explanation 写 2~3 句完整的话；"
            "每个知识点必须给 deep_dive（150~300 字），讲清原理、方法与典型场景。"
        )
        deep_dive_field = ',\n      "deep_dive": "适合自主阅读的深入讲解"'
    intent = _teacher_intent(cw)
    intent_rule = ""
    focus_field = ""
    if intent:
        intent_rule = (
            "\n6. 【教师想法是硬约束】选题、讲解侧重、例题、练习与作业必须对齐；"
            "点名要讲的概念写入该点 teacher_focus。"
        )
        focus_field = ',\n      "teacher_focus": "本点如何落实教师想法"'
    lab_rule = ""
    if getattr(cw, "want_virtual_lab", False):
        lab_rule = (
            "\n7. 教师勾选了实验/动画：仅当本课时确实在做该实验时才把实验操作写成知识点；"
            "指示剂课不要写成中和实验，制气课不要写成过滤。"
        )
    retry_rule = ""
    if missing:
        retry_rule = (
            "\n8. 上次缺了这些字段，必须补全且写具体内容，禁止套话："
            + "、".join(missing[:12])
        )
    system_prompt = f"""你是一线特级教师。根据课题和课本，设计【一节可直接上的 45 分钟课】的教学蓝图，只输出 JSON。{subject_hint}

要求：
1. 先定课时：课题若是大单元名（如酸碱盐、力、电），默认 lesson_grain=period，只取本节最该先上的 1～2 个点，topic 写成具体课时名（如「溶液的酸碱性：指示剂与pH」），不要用单元名当课时名。仅当教师明确要求单元复习时用 unit，可抽 3～4 点。
2. 目标必须可检测（能说出/会判断/会操作），禁止「理解某某标题」「掌握某某知识点」。目标给学生上课前不要念，写进 objectives 供教师备课。
3. 导入必须是具体物品或现象，禁止「从熟悉的生活场景出发」这类空话。课序是先探究再命名：学生先看现象、动手，再出现规范说法。
4. 每个知识点必须有：至少 2 条 core_concepts、至少 1 个真实 life_example、至少 1 条 common_mistakes。
5. 例题、随堂练习、作业都要写具体题面；作业禁止「自拟题」，并包含一个小作品（如体检单、方案、口头报告）。练习要带简短判断依据（给学生看题，依据留给教师）。
6. 小结写学生能复述的短句，不要重复知识点标题。
7. 只输出 JSON，不要 markdown。{web_rule}{intent_rule}{lab_rule}{retry_rule}

JSON 格式：
{{
  "topic": "具体课时名，不要照抄过大的单元名",
  "lesson_grain": "period",
  "cover_subtitle": "一句课眼",
  "objectives": ["能……", "会……"],
  "intro": {{
    "title": "具体情境标题",
    "subtitle": "",
    "content": "为什么要从这里切入",
    "steps": [{{"title": "看", "detail": "具体物品/现象"}}, {{"title": "问", "detail": "学生要回答的问题"}}]
  }},
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "plain_explanation": "用白话解释",
      "core_concepts": ["要点1", "要点2"],
      "common_mistakes": ["易错1"],
      "life_example": "真实物品或课本实例",
      "activity_goal": "互动要达成的可观察目标"{deep_dive_field}{focus_field}
    }}
  ],
  "example": {{"prompt": "完整题干（含选项则写在同一段）", "solution": "判断依据"}},
  "exercises": [{{"question": "具体题", "answer": "依据"}}],
  "homework": [{{"task": "基础：……"}}, {{"task": "规范或挑战：……"}}],
  "summary": ["带走的短句1", "短句2"]
}}"""
    user_prompt = f"课件课题：{cw.title}\n\n课本内容：\n{chapter_content[:9000]}"
    if intent:
        user_prompt += (
            f"\n\n【教师想法——必须遵守】\n{intent}\n"
            "请据此决定讲哪些点、讲到多深、用什么例子。"
        )
    return system_prompt, user_prompt


async def _extract_lesson_blueprint(
    cfg,
    cw,
    chapter_content: str,
    subject_name: str = "",
    subject_block: str = "",
    web_style: bool = False,
) -> dict:
    """抽出一节课的教学蓝图：课时名、目标、导入、知识点、例题、练习、作业。"""
    max_tok = max(cfg.max_tokens or 0, 7000 if web_style else 5000)
    system_prompt, user_prompt = _lesson_extract_prompts(
        cw, chapter_content, subject_name, subject_block, web_style,
    )
    resp = await _call_llm(
        cfg,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=max_tok,
    )
    obj = _parse_json_object(_resp_content(resp)) or {}
    bp = _normalize_blueprint(obj, web_style=web_style)
    gaps = _blueprint_gaps(bp)
    if gaps:
        logger.info("课件 %s 蓝图缺字段，补抽一次：%s", getattr(cw, "id", "?"), "、".join(gaps[:8]))
        system2, user2 = _lesson_extract_prompts(
            cw, chapter_content, subject_name, subject_block, web_style, missing=gaps,
        )
        resp2 = await _call_llm(
            cfg,
            [{"role": "system", "content": system2}, {"role": "user", "content": user2}],
            max_tokens=max_tok,
        )
        obj2 = _parse_json_object(_resp_content(resp2)) or {}
        bp2 = _normalize_blueprint(obj2, web_style=web_style)
        if not _blueprint_gaps(bp2) or len(_blueprint_gaps(bp2)) < len(gaps):
            bp = bp2
        else:
            # 两次都缺，合并非空字段
            if bp2.get("topic"):
                bp["topic"] = bp2["topic"]
            if bp2.get("objectives"):
                bp["objectives"] = bp2["objectives"]
            if (bp2.get("intro") or {}).get("steps"):
                bp["intro"] = bp2["intro"]
            if bp2.get("knowledge_points"):
                bp["knowledge_points"] = bp2["knowledge_points"]
            if bp2.get("example"):
                bp["example"] = bp2["example"]
            if bp2.get("exercises"):
                bp["exercises"] = bp2["exercises"]
            if bp2.get("homework"):
                bp["homework"] = bp2["homework"]
            if bp2.get("summary"):
                bp["summary"] = bp2["summary"]
    bp = _fill_blueprint_gaps(bp, cw)
    if not bp.get("knowledge_points"):
        return {}
    return bp


async def _extract_knowledge_points(
    cfg,
    cw,
    chapter_content: str,
    subject_name: str = "",
    subject_block: str = "",
    web_style: bool = False,
) -> list[dict]:
    """给知识图谱等调用方：只返回知识点列表。"""
    bp = await _extract_lesson_blueprint(
        cfg, cw, chapter_content, subject_name, subject_block, web_style,
    )
    return (bp or {}).get("knowledge_points") or []


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
    交互：先给现象，再判断；规范说法点开后才出现。
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
        f"<div class='panel' style='margin-top:12px'><b>先观察</b><p class='muted' style='margin:6px 0 0'>{life}</p></div>"
        if life else ""
    )

    # 误区判断小测：把第一个常见误区作为“错误说法”让学生判断
    quiz_block = ""
    if mistakes:
        wrong_stmt = mistakes[0]
        quiz_block = f"""
  <div class='card' style='margin-top:14px'>
    <p class='badge'>根据现象判断</p>
    <p style='margin:8px 0'>有同学说：“{wrong_stmt}”。对照你刚才看到的现象，这种说法站得住吗？</p>
    <div class='row'>
      <button class='btn' onclick='cwJudge(this,false)'>站得住</button>
      <button class='btn' onclick='cwJudge(this,true)'>站不住</button>
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
      fb.textContent = correct
        ? '根据现象可以判断：这句话把结论说反了。先说出你看到了什么，再对照规范说法。'
        : '再看一眼现象。这句话听起来像结论，但和常见观察对不上，所以站不住。';
    }
    var btns = btn.parentNode.querySelectorAll('.btn');
    btns.forEach(function(b){ b.disabled = true; });
    btn.classList.add(correct ? 'correct' : 'wrong');
    if(window.CW){ correct ? window.CW.correct('误区判断', '错误') : window.CW.wrong('误区判断', '正确'); }
  }
  </script>"""

    observe_block = life_block or (
        f"<div class='panel'><b>先观察</b><p class='muted' style='margin:6px 0 0'>"
        f"结合「{name}」想一个你见过的具体现象，再说它说明什么。</p></div>"
    )
    return f"""<div class="stage fade-in">
  <p class="title">{name}</p>
  <p class="subtitle">先看现象，再说结论 · {goal}</p>
  <div class="card">
    <p class="badge">先探究</p>
    {observe_block}
    {quiz_block}
    <button class="btn primary" style="margin-top:14px" onclick="cwReveal(this)">对照规范说法</button>
    <div id="cw-explain" class="panel" style="display:none;margin-top:12px">
      <p class="muted">规范说法（操作后再看）</p>
      <ul style="margin:8px 0 0;padding-left:20px">{concepts_li}</ul>
      <p style="margin:10px 0 0">{plain or '结合刚才的现象，用课本语言把判断依据说完整。'}</p>
    </div>
  </div>
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
学科：{subject_name or "通用"}{image_ref}{_interactive_teacher_intent_block(cw, point)}

风格要求：
- 生动、直白，句子短。至少 1 个真实情境、1 个可操作互动（点击/拖拽/输入）。
- 一屏只做一个主操作（观察 / 调节 / 判断三选一），不要再堆一套选择题或概念清单。
- 先观察或判断，再公布规范说法；不要在学生操作前列出核心要点或答案。
- 反馈要诠释现象：根据学生看到的颜色/读数/变化说明「为什么这样判断」，不要只写「正确/错误」。
- 学科事实必须正确。化学：石蕊只有红/紫/蓝，酚酞只有无色/红；彩虹色仅用于 pH 试纸；不要用万能指示剂颜色冒充石蕊或酚酞。
- 判定对错时调用 window.CW?.correct(题目, 答案) 或 window.CW?.wrong(题目, 答案)。

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
        retry_intent = _teacher_intent(cw)
        retry_prompt = (
            f"请直接输出一个 HTML 代码块（用 ```html 包裹），"
            f"内容是围绕「{point.get('name', '')}」的互动教学页面片段，"
            f"以 <div class=\"stage\"> 开头，含1个可点击互动。"
            f"不要任何说明文字，只输出代码块。"
        )
        if retry_intent:
            retry_prompt += f"必须呼应教师要求：{retry_intent[:200]}"
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


# ─── 单页 AI 优化（不走整课生成，不改 gen_status） ─────────────────────

_OPTIMIZE_HINTS = {
    "rewrite": "改写本页，语言更适合课堂讲授，保留原意与知识点，不要新增无关内容。",
    "shorten": "压缩本页，只留最核心的要点，适合老师口述；句子短、条目少。",
    "expand": "扩充本页，补充解释、过渡语和生活化例子，适合学生阅读。",
    "examples": "为本页补充生活化例子或例题解析；保留原有知识点，可改写 bullets/content/prompt/solution。",
    "notes": "只重写 notes 教师讲稿（课堂怎么讲、提问、板书提示），不要改其他字段。",
    "interactive": "重新生成本页互动 HTML。",
}

_SLIDE_TEXT_KEYS = (
    "title", "subtitle", "bullets", "content", "notes",
    "prompt", "solution", "left_title", "right_title", "columns", "steps",
)


def _slide_prompt_payload(slide: dict) -> dict:
    return {k: slide.get(k) for k in ("type", *_SLIDE_TEXT_KEYS)}


def _as_slide_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for x in value:
            if isinstance(x, str) and x.strip():
                parts.append(x.strip())
            elif isinstance(x, dict):
                t = x.get("text") or x.get("title") or x.get("detail") or x.get("content")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
        return "\n".join(parts) if parts else None
    # 对象/整课结构不能写进正文，否则页面会变成完整 JSON
    return None


def _as_str_list(value) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    for x in value:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict):
            t = x.get("text") or x.get("title") or x.get("detail") or x.get("content")
            if isinstance(t, str) and t.strip():
                out.append(t.strip())
    return out


def _pick_slide_from_lesson(obj: dict, original: dict) -> dict | None:
    slides = obj.get("slides")
    if not isinstance(slides, list):
        return None
    orig_title = (original.get("title") or "").strip()
    orig_type = (original.get("type") or "").strip()
    for s in slides:
        if isinstance(s, dict) and orig_title and (s.get("title") or "").strip() == orig_title:
            return s
    if orig_type:
        for s in slides:
            if isinstance(s, dict) and (s.get("type") or "").strip() == orig_type:
                return s
    return None


def _content_is_structure_dump(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 8 or t[0] not in "{[":
        return False
    try:
        data = json.loads(t)
    except Exception:
        return False
    if isinstance(data, dict):
        return bool(data.get("slides") or data.get("meta") or data.get("pages"))
    return isinstance(data, list) and bool(data) and isinstance(data[0], dict)


def _coerce_slide_updates(obj: dict, original: dict, mode: str) -> dict:
    """只留下当前页字段。模型若误输出整课 JSON，按标题/类型抽一页，否则丢弃。"""
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get("slides"), list):
        picked = _pick_slide_from_lesson(obj, original)
        if not picked:
            return {}
        obj = picked
    if mode == "notes":
        notes = _as_slide_text(obj.get("notes"))
        return {"notes": notes} if notes else {}

    out: dict = {}
    for k in ("title", "subtitle", "content", "notes", "prompt", "solution", "left_title", "right_title"):
        if k not in obj:
            continue
        text = _as_slide_text(obj.get(k))
        if text is None:
            continue
        if k == "content" and _content_is_structure_dump(text):
            continue
        out[k] = text
    if "bullets" in obj:
        bullets = _as_str_list(obj.get("bullets"))
        if bullets is not None:
            out["bullets"] = bullets
    for k in ("columns", "steps"):
        val = obj.get(k)
        if not isinstance(val, list):
            continue
        cleaned = []
        for item in val:
            if not isinstance(item, dict):
                continue
            row = {}
            for fk in ("title", "detail", "items"):
                if fk not in item:
                    continue
                if fk == "items":
                    items = _as_str_list(item.get("items"))
                    if items is not None:
                        row["items"] = items
                else:
                    t = _as_slide_text(item.get(fk))
                    if t is not None:
                        row[fk] = t
            if row:
                cleaned.append(row)
        if cleaned:
            out[k] = cleaned
    return out


def _optimize_updates_unusable(updates: dict, mode: str) -> bool:
    if not updates:
        return True
    if mode == "notes":
        return not isinstance(updates.get("notes"), str) or not updates["notes"].strip()
    return not any(k in updates for k in ("title", "content", "bullets", "notes", "prompt", "solution"))


async def _mark_slide_edit(courseware_id: int, index: int, status: str, error: str | None = None):
    from sqlalchemy.orm.attributes import flag_modified
    async with AsyncSessionLocal() as db:
        cw = (await db.execute(select(Courseware).where(Courseware.id == courseware_id))).scalar_one_or_none()
        if not cw or not isinstance(cw.content, dict):
            return
        slides = cw.content.get("slides") or []
        if index < 0 or index >= len(slides) or not isinstance(slides[index], dict):
            return
        slides[index]["edit_status"] = status
        if error:
            slides[index]["edit_error"] = error[:500]
        else:
            slides[index].pop("edit_error", None)
        if status != "processing":
            slides[index].pop("task_id", None)
        flag_modified(cw, "content")
        await db.commit()


async def do_optimize_courseware_slide(
    courseware_id: int, index: int, instruction: str, mode: str,
):
    """只重写一页。整课 gen_status 保持不变。"""
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.courseware_theme import page_kind

    async with AsyncSessionLocal() as db:
        cw = (await db.execute(select(Courseware).where(Courseware.id == courseware_id))).scalar_one_or_none()
        if not cw or not isinstance(cw.content, dict):
            return
        slides = cw.content.get("slides") or []
        if index < 0 or index >= len(slides) or not isinstance(slides[index], dict):
            slides_err = "页面不存在"
            # 仍尝试把状态写回（若页还在）
            logger.warning("课件 %s 单页优化：%s index=%s", courseware_id, slides_err, index)
            return
        cfg = await _get_default_llm(cw.teacher_id, db)
        if not cfg:
            slides[index]["edit_status"] = "failed"
            slides[index]["edit_error"] = "未配置默认大模型"
            slides[index].pop("task_id", None)
            flag_modified(cw, "content")
            await db.commit()
            return

        slide_snap = copy.deepcopy(slides[index])
        title = cw.title
        subject_name = subject_block = subject_interactive = ""
        if cw.textbook_id:
            tb = (await db.execute(select(Textbook).where(Textbook.id == cw.textbook_id))).scalar_one_or_none()
            if tb:
                subject_name, subject_block, subject_interactive = await _resolve_subject_prompt(
                    db, cw.teacher_id, tb.subject_id,
                )

    try:
        updates = await _rewrite_one_slide(
            cfg, title, slide_snap, index, instruction, mode,
            subject_name, subject_block, subject_interactive,
        )
    except Exception as e:
        logger.exception("课件 %s 第 %s 页优化失败：%s", courseware_id, index + 1, e)
        await _mark_slide_edit(courseware_id, index, "failed", str(e))
        return

    async with AsyncSessionLocal() as db:
        cw = (await db.execute(select(Courseware).where(Courseware.id == courseware_id))).scalar_one_or_none()
        if not cw or not isinstance(cw.content, dict):
            return
        slides = cw.content.get("slides") or []
        if index < 0 or index >= len(slides) or not isinstance(slides[index], dict):
            return
        slide = slides[index]
        if mode == "notes":
            if isinstance(updates.get("notes"), str):
                slide["notes"] = updates["notes"]
        elif mode == "interactive":
            html = updates.get("html") or ""
            if html:
                slide["html"] = html
                slide["type"] = "interactive"
            if updates.get("skill"):
                slide["skill"] = updates["skill"]
            else:
                slide.pop("skill", None)
        else:
            cleaned = _coerce_slide_updates(updates, slide, mode)
            for k in _SLIDE_TEXT_KEYS:
                if k in cleaned and cleaned[k] is not None:
                    slide[k] = cleaned[k]
            if cleaned.get("title"):
                slide["title"] = cleaned["title"]
            slide["type"] = page_kind(slide.get("type"))
        slide["edit_status"] = "idle"
        slide.pop("task_id", None)
        slide.pop("edit_error", None)
        flag_modified(cw, "content")
        await db.commit()


async def _rewrite_one_slide(
    cfg, cw_title: str, slide: dict, index: int, instruction: str, mode: str,
    subject_name: str, subject_block: str, subject_interactive: str,
) -> dict:
    if mode == "interactive":
        from app.services import skill_service
        from app.services.courseware_components import build_interactive_prompt

        point = {
            "name": slide.get("title") or f"第{index + 1}页",
            "plain_explanation": slide.get("content") or "",
            "core_concepts": slide.get("bullets") if isinstance(slide.get("bullets"), list) else [],
            "common_mistakes": [],
            "life_example": slide.get("prompt") or "",
            "activity_goal": instruction or slide.get("subtitle") or "通过互动练习巩固本页知识点",
        }
        html = ""
        routed = None
        try:
            prev = slide.get("skill") if isinstance(slide.get("skill"), dict) else {}
            lab_key = prev.get("asset_key") or (
                prev.get("problem_type") if prev.get("skill") == "edu-chem-lab" else None
            )
            if lab_key:
                from app.services.animation_service import payload_for_key
                html, routed = await payload_for_key(lab_key)
            if not html:
                prefer_lab = bool(lab_key) or ("实验" in (instruction or slide.get("title") or ""))
                html, routed = await skill_service.maybe_generate_skill(
                    cfg, point, subject_name, lab_key=lab_key, prefer_lab=prefer_lab,
                )
        except Exception as e:
            logger.warning("单页优化 skill 失败，回退 LLM：%s", e)
        if not html:
            class _Cw:
                title = cw_title
                id = 0
            html = await _generate_interactive_html_for_point(
                cfg=cfg, cw=_Cw(), point=point, point_idx=index + 1,
                subject_name=subject_name, image_catalog="",
                interactive_hint=build_interactive_prompt(subject_interactive),
            )
        if not html:
            raise ValueError("未能生成互动页面")
        out = {"html": html}
        if routed:
            out["skill"] = routed
        return out

    from app.services.courseware_theme import page_kind, page_label

    hint = _OPTIMIZE_HINTS.get(mode, _OPTIMIZE_HINTS["rewrite"])
    extra = f"\n教师补充要求：{instruction}" if instruction else ""
    page_type = page_kind(slide.get("type"))
    type_label = page_label(page_type)
    subject_hint = f"\n学科：{subject_name}。用语符合该学科课堂，不要按整课教案来写。" if subject_name else ""
    payload = json.dumps(_slide_prompt_payload(slide), ensure_ascii=False)
    schema_note = (
        '{"title":"","subtitle":"","bullets":[""],"content":"","notes":"","prompt":"","solution":""}'
        if mode != "notes"
        else '{"notes":"教师讲稿全文"}'
    )
    prompt = f"""你是中小学课件编辑。这次只改「当前这一页」的文案，不是生成整节课。

课件标题：{cw_title}
当前页：第 {index + 1} 页，类型 {page_type}（{type_label}）
任务：{hint}{extra}{subject_hint}

当前页 JSON：
{payload}

【硬约束】
- 只输出这一个页面的 JSON 对象，不要 markdown 围栏，不要解释。
- 禁止输出 meta、slides、pages，禁止写成「教学目标 + 教学过程」的整课教案。
- 不要改页面类型，不要新增无关知识点，不要把整单元结构塞进 content。
- 字段：{schema_note}
- bullets 是字符串数组，最多 8 条；content / notes / prompt / solution 必须是字符串（markdown），公式用 $...$。
- 不要输出 html、images、type、index。
"""

    async def _ask(user_prompt: str) -> dict:
        max_tok = max(cfg.max_tokens or 0, 2500)
        resp = await _call_llm(cfg, [{"role": "user", "content": user_prompt}], max_tokens=max_tok)
        raw = _resp_content(resp)
        obj = _parse_json_object(raw)
        if not obj:
            raise ValueError("模型未返回有效 JSON")
        return _coerce_slide_updates(obj, slide, mode)

    updates = await _ask(prompt)
    if _optimize_updates_unusable(updates, mode):
        retry = (
            f"上次你输出了整课结构或非本页字段。现在必须只输出当前这一页。\n"
            f"页类型：{page_type}（{type_label}），标题：{slide.get('title') or ''}\n"
            f"不要 meta，不要 slides 数组，不要教案大纲。字段：{schema_note}\n"
            f"任务：{hint}{extra}\n\n当前页 JSON：\n{payload}"
        )
        updates = await _ask(retry)
    if _optimize_updates_unusable(updates, mode):
        raise ValueError("模型未返回当前页可用内容")
    return updates


async def _generate_lesson_content(
    cfg, cw, chapter_content: str, image_catalog: str,
    subject_name: str = "", subject_block: str = "", subject_interactive: str = "",
) -> dict:
    """两阶段课件生成：先抽教学蓝图，再按蓝图拼课。

    蓝图含课时名、可检测目标、具体导入/例题/练习/作业；拼课时不再用点名盖空壳。
    互动页默认最多 2 个（1 个概念互动 + 至多 1 个自动匹配的动画库实验）。
    render_style：ppt 精炼要点；html 带深入讲解段落。
    """
    from app.models.courseware import RenderStyle

    is_web = getattr(cw, "render_style", RenderStyle.ppt) == RenderStyle.html

    interactive_hint = ""
    if cw.is_interactive:
        from app.services.courseware_components import build_interactive_prompt
        interactive_hint = build_interactive_prompt(subject_interactive)

    # Stage 1: 抽出可上课的教学蓝图（课时名、目标、导入、例题、练习、作业）
    blueprint = await _extract_lesson_blueprint(
        cfg, cw, chapter_content, subject_name, subject_block, web_style=is_web,
    )
    points = (blueprint or {}).get("knowledge_points") or []
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
        form_hint = (
            "一份【学生可自主滚动阅读的网页课件】，每个小节的 content 要写成完整段落（可用 ### 小标题分段）"
            if is_web else
            "一节【完整的、可直接照着讲授的】课堂教学课件（类似 PPT），每页 content 精炼、以要点为主"
        )
        system_prompt = f"""你是一位资深的一线教师和课件设计专家。请基于课本内容，设计{form_hint}，时长约 40-45 分钟。{subject_hint}
要求：
1. 课件需有 meta + slides 结构。每页字段：index,type,title,subtitle,bullets,content,notes；对比页可加 columns[{{title,items}}]，过程页可加 steps[{{title,detail}}]，例题页可加 prompt/solution。
2. 课序必须先探究再命名：cover → process（导入）→ interactive → knowledge → comparison → example → summary → exercise → homework。
   不要生成 objectives 页；可检测目标只写在 meta.objectives，供教师备课。
   type 从以上标准类型中选；旧别名 title/content/intro/quiz 也可。
3. 全部中文，输出严格 JSON，不要 markdown 代码块。
4. 若为互动课件，可在 interactive 页附 html 字段（片段）。一屏一个主操作；反馈要诠释现象，不要只报对错。
5. 例题解析、练习答案只写在 notes，不要和题干并排展示。作业含一个小作品（体检单/方案/口头报告）。
6. 若用户给出了教师想法，必须当作硬约束：选题、讲解侧重、例题难度、练习与作业都要对齐，不能只写在备注里。
{interactive_hint}
"""
        user_prompt = f"课件课题：{cw.title}\n\n课本内容：\n{chapter_content[:8000]}{image_hint}"
        fallback_intent = _teacher_intent(cw)
        if fallback_intent:
            user_prompt += (
                "\n\n【教师想法——硬约束，必须在学习目标、讲解侧重、例题、练习与作业中落实，不要只当参考】\n"
                f"{fallback_intent}"
            )
        resp = await _call_llm(
            cfg,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=max(cfg.max_tokens or 0, 8000),
        )
        raw = resp.choices[0].message.content
        data = _parse_lesson_json(raw)
        if data and data.get("slides"):
            if fallback_intent:
                data = await _apply_teacher_intent(cfg, cw, data, fallback_intent)
            return data
        fallback = {
            "meta": {"title": cw.title},
            "slides": [{"index": 1, "type": "content", "title": cw.title, "content": raw, "bullets": [], "notes": ""}],
        }
        if fallback_intent:
            fallback = await _apply_teacher_intent(cfg, cw, fallback, fallback_intent)
        return fallback

    return await _assemble_lesson_from_blueprint(
        cfg, cw, blueprint, points, subject_name, image_catalog, interactive_hint, is_web,
    )


async def _assemble_lesson_from_blueprint(
    cfg, cw, blueprint: dict, points: list[dict],
    subject_name: str, image_catalog: str, interactive_hint: str, is_web: bool,
) -> dict:
    """用蓝图拼课：先探究再命名；目标只进 meta，不给学生看。"""
    from app.models.courseware import RenderStyle
    from app.services.animation_service import resolve_keys as _resolve_anim_keys

    topic = blueprint.get("topic") or cw.title
    unit_note = f"单元：{cw.title}。" if topic != cw.title else ""
    subtitle = blueprint.get("cover_subtitle") or (
        f"{subject_name} · {cw.title}" if subject_name else cw.title
    )
    intro = blueprint.get("intro") or _normalize_intro({})
    example = blueprint.get("example")
    exercises = blueprint.get("exercises") or []
    homework = blueprint.get("homework") or []
    summary = blueprint.get("summary") or []
    objectives = blueprint.get("objectives") or []

    explicit_anim = bool(getattr(cw, "animation_keys", None))
    anim_keys = _resolve_anim_keys(cw, points, topic, subject_name) if cw.is_interactive else []
    if not explicit_anim:
        anim_keys = anim_keys[:1]
    point_ix_budget = 0
    if cw.is_interactive:
        point_ix_budget = 1 if anim_keys else 2

    slides: list[dict] = []
    idx = 1
    slides.append({
        "index": idx, "type": "cover", "title": topic, "subtitle": subtitle,
        "bullets": [], "content": "",
        "notes": (
            f"{unit_note}开场抛出本节核心问题：{topic}。"
            "不要念教学目标。停课点：学生猜完再进情境。"
        ).strip(),
    })
    idx += 1
    slides.append({
        "index": idx, "type": "process",
        "title": intro.get("title") or "情境导入",
        "subtitle": intro.get("subtitle") or "从具体现象切入",
        "bullets": [s["detail"] for s in intro.get("steps") or [] if s.get("detail")][:3],
        "steps": intro.get("steps") or [],
        "content": intro.get("content") or f"用具体情境引出「{topic}」。",
        "notes": "停课点：学生说完自己的判断后再往下翻。这一页只观察、只表达，不公布规范说法。",
    })
    idx += 1

    interactive_jobs: list[tuple[int, int, dict]] = []
    for point_i, p in enumerate(points, 1):
        if point_i > point_ix_budget:
            break
        interactive_slide = {
            "index": idx,
            "type": "interactive",
            "title": f"{p['name']} · 动手做",
            "subtitle": "先观察再下结论",
            "bullets": [p.get("activity_goal") or "根据现象说出判断依据"],
            "content": "先完成一个操作，再根据现象说出判断依据。系统会解释你看到的现象，不急着给标准答案。",
            "notes": (
                "停课点：操作后先问「你看到了什么？这说明什么？」不要立刻给标准答案。"
                "反馈要诠释现象，不要只报对错。"
            ),
        }
        slides.append(interactive_slide)
        interactive_jobs.append((len(slides) - 1, point_i, p))
        idx += 1

    if interactive_jobs:
        from app.services import skill_service
        sem = asyncio.Semaphore(3)

        async def _gen_html(point_i: int, p: dict) -> tuple[str, dict | None]:
            async with sem:
                html = ""
                routed = None
                try:
                    html, routed = await skill_service.maybe_generate_skill(cfg, p, subject_name)
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
                return html or "", routed

        htmls = await asyncio.gather(*[_gen_html(pi, p) for _, pi, p in interactive_jobs])
        for (slide_i, _, _), (html, routed) in zip(interactive_jobs, htmls):
            if html:
                slides[slide_i]["html"] = html
            if routed:
                slides[slide_i]["skill"] = routed

    if anim_keys:
        from app.services.animation_service import payload_for_key, KIND_SUBTITLE
        for key in anim_keys:
            try:
                html, routed = await payload_for_key(key)
            except Exception as e:
                logger.warning("课件 %s 引用动画 %s 失败：%s", cw.id, key, e)
                continue
            if not html or not routed:
                continue
            kind = routed.get("kind") or ""
            is_lab = kind == "chem_lab" or routed.get("skill") == "edu-chem-lab"
            slides.append({
                "index": idx,
                "type": "interactive",
                "title": routed.get("title") or "互动动画",
                "subtitle": KIND_SUBTITLE.get(kind) or "动画库 · 可操作演示",
                "bullets": ["与本课核心点对齐的动画库实验，不重复生成"],
                "content": "",
                "notes": (
                    "停课点：让学生按步骤操作，看完现象先口述，再点名概念。"
                    "错了先讲安全再重做。若本课尚未建立对应概念，只作为现象观察。"
                    if is_lab else
                    "停课点：让学生按提示操作，先描述变化，再对照规范说法。"
                ),
                "html": html,
                "skill": routed,
            })
            idx += 1

    for point_i, p in enumerate(points, 1):
        bullets = p.get("core_concepts") or []
        if not bullets and p.get("plain_explanation"):
            bullets = [p["plain_explanation"]]
        content_parts = []
        if p.get("plain_explanation"):
            content_parts.append(f"### 先用一句话说清楚\n{p['plain_explanation']}")
        if is_web and p.get("deep_dive"):
            content_parts.append(f"### 深入理解\n{p['deep_dive']}")
        if p.get("common_mistakes"):
            content_parts.append("### 常见误区\n" + "\n".join(f"- {x}" for x in p["common_mistakes"]))
        if p.get("teacher_focus"):
            content_parts.append(f"### 按教师要求\n{p['teacher_focus']}")
        if p.get("life_example"):
            content_parts.append(f"### 生活中的例子\n- {p['life_example']}")
        slides.append({
            "index": idx,
            "type": "knowledge",
            "title": p["name"] if len(points) == 1 else f"{point_i}. {p['name']}",
            "subtitle": "把刚才看到的现象说成规范说法",
            "bullets": bullets[:5],
            "content": "\n\n".join(content_parts),
            "notes": "停课点：先让学生用刚才的现象自己说，再揭开规范说法。讲解要短句、直白。",
        })
        idx += 1

    mistakes = [m for p in points for m in (p.get("common_mistakes") or [])][:4]
    if mistakes:
        corrects = []
        for p in points:
            corrects.extend(p.get("core_concepts") or [])
        if not corrects:
            corrects = [p.get("plain_explanation") or p["name"] for p in points[:4]]
        slides.append({
            "index": idx,
            "type": "comparison",
            "title": "易错对照",
            "subtitle": "把误区掰过来",
            "left_title": "常见误区",
            "right_title": "正确理解",
            "columns": [
                {"title": "常见误区", "items": mistakes},
                {"title": "正确理解", "items": corrects[:4]},
            ],
            "bullets": mistakes + corrects[:4],
            "content": "",
            "notes": "停课点：先让学生指出错在哪里，再对照正确说法。",
        })
        idx += 1

    if example:
        solution = example.get("solution") or ""
        slides.append({
            "index": idx,
            "type": "example",
            "title": "例题精讲",
            "subtitle": "先做，再对照依据",
            "prompt": example["prompt"],
            "bullets": [],
            "content": "",
            "solution": solution,
            "notes": (
                "停课点：先独立做，不要投影解析。\n"
                f"解析：{solution}\n"
                "追问：换一种试剂或条件，结论会怎么变？"
            ),
        })
        idx += 1

    slides.append({
        "index": idx,
        "type": "summary",
        "title": "今天带走这几句话",
        "subtitle": "让学生复述，不要老师再念标题",
        "bullets": summary[:4],
        "content": "",
        "notes": (
            "抽三名学生各说一句。"
            + (f" 课末回扣：{'；'.join(objectives[:2])}。" if objectives else "")
        ),
    })
    idx += 1
    answer_notes = "\n".join(
        f"{i+1}. {ex.get('answer') or '看判断依据。'}" for i, ex in enumerate(exercises)
    )
    slides.append({
        "index": idx,
        "type": "exercise",
        "title": "随堂练习",
        "subtitle": "当堂检验，先写依据再对答案",
        "bullets": [ex["question"] for ex in exercises[:4]],
        "content": "独立完成后对照教师讲稿里的判断依据。能说出“因为……”才算过关。",
        "notes": (
            "停课点：先收判断依据，再对答案。\n"
            + (answer_notes or "巡视时关注卡在概念判断上的学生。")
        ),
    })
    idx += 1
    slides.append({
        "index": idx,
        "type": "homework",
        "title": "课后任务",
        "subtitle": "会说出理由，比只选对答案更重要",
        "bullets": [h["task"] for h in homework[:4]],
        "content": "分层完成：基础巩固 + 规范改错 + 小作品。不要自拟题目。",
        "notes": "停课点：下节课用 1 分钟交流作品。收作业时抽查“依据”一栏。",
    })

    lesson = {
        "meta": {
            "title": topic,
            "subject": subject_name or "",
            "render_style": RenderStyle.html.value if is_web else RenderStyle.ppt.value,
            "duration": "45分钟",
            "lesson_grain": blueprint.get("lesson_grain") or "period",
            "unit_title": cw.title,
            "objectives": objectives[:4],
            "key_points": [p["name"] for p in points[:3]],
            "difficulties": [m for p in points for m in p.get("common_mistakes", [])][:3],
            "knowledge_points": points,
        },
        "slides": slides,
    }
    intent = _teacher_intent(cw)
    if intent:
        lesson = await _apply_teacher_intent(cfg, cw, lesson, intent)
    return lesson


async def parse_questions_from_text(cfg, text: str, image_catalog: str = "") -> list[dict]:
    """把老师手动输入的文本（可能含一道或多道题）用 LLM 拆分为结构化题目。"""
    image_rule = ""
    image_fields = ""
    if image_catalog:
        image_rule = (
            "\n- 文本里的 [图N] 是插图占位。题干配图填 stem_image_ids；"
            "某个选项配图填该选项的 image_id。没有配图就空数组 / 不填 image_id。"
            "不要把 [图N] 留在题干或选项文字里。"
        )
        image_fields = (
            ',"stem_image_ids":[1],'
            '"options":{"A":{"text":"选项文字","image_id":2},"B":{"text":"选项文字"}}'
        )
    system_prompt = f"""你是题库整理助手。请把老师输入的文本拆分、整理为结构化题目。
- 文本可能包含一道题，也可能包含多道题，请逐题拆分。
- 自动判断每道题的题型与难度。
- question_type 取值：single_choice(单选)/multi_choice(多选)/fill_blank(填空)/true_false(判断)/short_answer(简答)/essay(作文论述)/calculation(计算)
- difficulty 取值：easy/medium/hard/very_hard
- 选择题把选项放进 options，如 {{"A":"...","B":"...","C":"...","D":"..."}}；非选择题 options 为 null。
- 若原文给出了答案/解析，请填入 answer / explanation，没有则留空字符串。
- tags 填写本题涉及的知识点名称（2~5 个短词）；原文看不出则给空数组。{image_rule}
只输出 JSON，格式：{{"questions":[{{"question_type":"...","difficulty":"...","content":"题干","options":null,"answer":"","explanation":"","tags":["知识点"]{image_fields}}}]}}"""
    user = text[:8000]
    if image_catalog:
        user += f"\n\n【可引用的插图】\n{image_catalog}"
    resp = await _call_llm(
        cfg,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
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


async def do_generate_homework(
    paper_id: int,
    courseware_ids: list[int] | None = None,
    use_question_bank: bool = False,
):
    """组卷入口。范围/来源/是否记分均读试卷行；保留旧参数以兼容未消费完的 Celery 任务。"""
    from app.services.homework_service import generate_homework
    await generate_homework(paper_id)


async def structure_textbook_toc(teacher_id: int, toc_text: str) -> list[dict]:
    """把扫描版教材『目录』页的 OCR 文本交给大模型，还原为规范章节结构。

    返回 [{"level": 1|2, "title": str, "page": int|None}, ...]，按目录顺序排列。
    无 LLM 配置或解析失败时返回 []（上层回退到启发式识别）。
    """
    toc_text = (toc_text or "").strip()
    if not toc_text:
        return []

    async with AsyncSessionLocal() as db:
        cfg = await _get_default_llm(teacher_id, db)
    if not cfg:
        logger.warning("课本目录结构化：教师 %s 未配置 LLM，跳过", teacher_id)
        return []

    prompt = (
        "下面是一本教材『目录』页的 OCR 文本，可能存在错别字、缺字、多余符号、"
        "换行错乱或列错位。请据此还原出规范、通顺的章节目录结构。\n\n"
        "要求：\n"
        "1. 一级条目为『章』(level=1)，二级条目为『节』(level=2)。\n"
        "2. 修正明显的 OCR 错字，使标题为通顺规范的中文（例：『炊烧』→『燃烧』、"
        "『低兢行动』→『低碳行动』）。\n"
        "3. 每个『节』尽量给出其正文页码（整数）；『章』通常没有单独页码，用 null。\n"
        "4. 严格按目录中真实出现的顺序输出，不要遗漏，也不要臆造不存在的条目。\n"
        "5. 忽略『目录』标题本身；『附录』『元素周期表』等若出现可作为 level=1 保留。\n"
        "6. 只输出 JSON，不要输出解释或多余文字。\n\n"
        "输出格式：\n"
        '{"chapters":[{"level":1,"title":"第一章 启航化学之旅","page":null},'
        '{"level":2,"title":"第一节 化学让世界更美好","page":2}]}\n\n'
        f"OCR 文本：\n{toc_text}"
    )

    try:
        resp = await _call_llm(cfg, [{"role": "user", "content": prompt}], max_tokens=2048)
        raw = _resp_content(resp)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            logger.warning("课本目录结构化：LLM 未返回 JSON")
            return []
        data = json.loads(raw[start:end])
    except Exception as e:  # noqa: BLE001
        logger.warning("课本目录结构化失败：%s", e)
        return []

    chapters: list[dict] = []
    for item in (data.get("chapters") or []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        level = 1 if int(item.get("level") or 1) <= 1 else 2
        page = item.get("page")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        chapters.append({"level": level, "title": title[:256], "page": page})
    return chapters


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
        "请识别图片中的所有题目并结构化为 JSON（只输出 JSON）。\n"
        "规则：\n"
        "1. 选项若带图，bbox 必须包住该选项的【整块配图】（图本身完整，不要切掉边缘）。\n"
        "   用 [x,y,w,h]，0~1，相对整张大图左上角。宁可比图略大，不能只框一部分。\n"
        "2. 不要把整页截图、整道题、整行选项当成一个框。\n"
        "3. 题干本身没有独立插图时，stem_bboxes 必须是空数组，禁止把整页图当题干图。\n"
        "4. 选项文字单独放 text；没有图时 bbox 为 null。\n"
        '{"questions":[{"question_type":"single_choice/multi_choice/fill_blank/true_false/short_answer/essay/calculation",'
        '"difficulty":"easy/medium/hard/very_hard","content":"题干文字",'
        '"stem_bboxes":[],'
        '"options":{"A":{"text":"选项文字","bbox":[0.08,0.42,0.38,0.22]},"B":{"text":"...","bbox":null}},'
        '"answer":"答案(若有)","tags":["知识点"]}]}}'
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


async def do_analyze_questions(
    set_id: int, question_ids: list[int], task_id: str | None = None, force: bool = False,
):
    """对批次中被勾选的题目做 AI 图解解析（有限并发），并通过 Redis 推送实时进度。"""
    import asyncio
    from app.models.question_analysis import AnalysisSet, AnalysisQuestion
    from app.services.question_bank_service import (
        apply_analysis_from_bank, find_questions_by_hashes, question_content_hash,
        upsert_and_write_analysis,
    )

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

        hashes = [
            question_content_hash((q.content or "")[:4000], q.options, q.question_type)
            for q in q_rows
        ]
        bank_by_hash = await find_questions_by_hashes(db, aset.teacher_id, hashes)

        llm_rows: list[AnalysisQuestion] = []
        reused = 0
        for q in q_rows:
            q.selected = True
            digest = question_content_hash((q.content or "")[:4000], q.options, q.question_type)
            bank = bank_by_hash.get(digest)
            if not force and bank and apply_analysis_from_bank(q, bank):
                reused += 1
                continue
            q.analysis_status = ParseStatus.processing
            q.analysis_source = None
            llm_rows.append(q)
        await db.commit()

        total = len(q_rows)
        await _publish_progress(task_id, {
            "stage": "start", "total": total, "current": reused,
            "message": f"已从题库套用 {reused} 道" if reused else None,
        })

        if not llm_rows:
            await _publish_progress(task_id, {"stage": "completed", "total": total, "current": total})
            try:
                from app.tasks.knowledge_tasks import persist_analysis_kps_task
                persist_analysis_kps_task.delay(set_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("试题批次 %s 知识点入图任务派发失败：%s", set_id, e)
            return

        if not cfg:
            for q in llm_rows:
                q.analysis_status = ParseStatus.failed
            await db.commit()
            await _publish_progress(task_id, {"stage": "error", "message": "未配置默认大模型"})
            return

        jobs = [
            (q.id, q.seq, {"content": q.content, "options": q.options, "answer": q.answer})
            for q in llm_rows
        ]
        by_id = {q.id: q for q in llm_rows}
        sem = asyncio.Semaphore(3)
        write_lock = asyncio.Lock()
        done_count = reused

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
                    q.analysis_source = "ai"
                    try:
                        await upsert_and_write_analysis(
                            db,
                            teacher_id=aset.teacher_id,
                            subject_id=aset.subject_id,
                            grade_id=aset.grade_id,
                            content=q.content,
                            options=q.options,
                            question_type=q.question_type,
                            difficulty=q.difficulty,
                            answer=q.answer,
                            analysis_content=analysis,
                            analysis_html=html,
                            overwrite=True,
                        )
                    except Exception:
                        logger.exception("题目 %s 解析回写题库失败", qid)
                else:
                    q.analysis_status = ParseStatus.failed
                done_count += 1
                await db.commit()
                await _publish_progress(task_id, {
                    "stage": "done_one", "current": done_count, "total": total,
                    "question_id": qid, "seq": seq, "status": q.analysis_status.value,
                })

        await _publish_progress(task_id, {"stage": "completed", "total": total, "current": total})

        try:
            from app.tasks.knowledge_tasks import persist_analysis_kps_task
            persist_analysis_kps_task.delay(set_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("试题批次 %s 知识点入图任务派发失败：%s", set_id, e)
