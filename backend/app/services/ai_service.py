"""AI 生成服务：课件、作业、OCR、成绩分析"""
import asyncio
import copy
import json
import logging
import re
from datetime import datetime
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
from app.services.chem_text import normalize_lesson_chem, normalize_slide_chem

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


class _GenAbort(Exception):
    """可预期的生成失败，消息直接展示给教师。"""


def _describe_gen_error(exc: BaseException) -> str:
    if isinstance(exc, _GenAbort):
        return str(exc)
    text = str(exc).lower()
    if any(m in text for m in ("timeout", "timed out", "524", "504")):
        return "大模型响应超时，请稍后重新生成"
    if "429" in text or "rate limit" in text or "overloaded" in text:
        return "大模型繁忙或被限流，请稍后重新生成"
    if any(m in text for m in ("401", "403", "authentication", "api key", "api_key", "unauthorized")):
        return "大模型鉴权失败，请到系统设置检查 API Key"
    if "context" in text and ("length" in text or "too long" in text or "maximum" in text):
        return "所选课本内容过长，超出模型上下文，请缩小章节或页码范围"
    if any(m in text for m in ("connection", "502", "503", "unavailable")):
        return "连接大模型服务失败，请稍后重新生成"
    return f"生成出错：{str(exc)[:160]}"


def _build_image_catalog(imgs, chapters) -> str:
    """课本图没有图注，用页码 + 所在最细一级小节标题让模型判断这张图讲什么。"""
    lines = []
    for img in imgs:
        page = img.page_number
        section = ""
        if page:
            best_span = None
            for c in chapters:
                if c.page_start and c.page_end and c.page_start <= page <= c.page_end:
                    span = c.page_end - c.page_start
                    # 同跨度时后出现的通常是子节，更具体
                    if best_span is None or span <= best_span:
                        best_span, section = span, (c.title or "").strip()
        kind = "整页截图" if "/page_" in (img.object_name or "") else "插图"
        where = f"第 {page} 页" if page else "页码未知"
        if section:
            where += f"，小节「{section[:40]}」"
        caption = (getattr(img, "caption", None) or "").strip()
        if caption:
            where += f"，图注「{caption[:60]}」"
        lines.append(f"- 图#{img.id}：{where}（{kind}）")
    return "\n".join(lines)


_CW_PROGRESS_TTL = 3600


async def _no_progress(stage: str, detail: str = "") -> None:
    return None


def _courseware_progress_reporter(cw, task_id: str | None):
    """返回 report(stage, detail)：写 Redis 快照供状态接口轮询，并发布到任务频道。"""
    from app.models.courseware import courseware_progress_key

    steps = [{"key": "prepare", "label": "读取课本内容"}, {"key": "blueprint", "label": "设计教学蓝图"}]
    if cw.textbook_id:
        steps.append({"key": "bank", "label": "匹配题库真题"})
    if cw.is_interactive:
        steps.append({"key": "interactive", "label": "制作互动页"})
    if _teacher_intent(cw):
        steps.append({"key": "intent", "label": "落实教师想法"})
    steps.append({"key": "save", "label": "保存课件"})
    key = courseware_progress_key(cw.id)

    async def report(stage: str, detail: str = "") -> None:
        payload = {"stage": stage, "detail": detail, "steps": steps}
        try:
            from app.core.redis_client import get_redis
            redis = await get_redis()
            await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=_CW_PROGRESS_TTL)
        except Exception as e:  # noqa: BLE001
            logger.warning("课件 %s 写进度失败：%s", cw.id, e)
        await _publish_progress(task_id, payload)

    return report


async def do_generate_courseware(courseware_id: int, task_id: str | None = None):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Courseware).where(Courseware.id == courseware_id))
        cw = result.scalar_one_or_none()
        if not cw:
            # 行可能尚未提交（极端时序），抛错让任务重试
            raise ValueError(f"课件 {courseware_id} 不存在，稍后重试")
        # 投递后才回写 task_id，所以开头允许为空；不一致说明已被新一轮生成取代
        if task_id and cw.task_id and cw.task_id != task_id:
            logger.info("课件 %s 任务 %s 已被 %s 取代，跳过", cw.id, task_id, cw.task_id)
            return

        cw.gen_status = ParseStatus.processing
        cw.gen_started_at = datetime.now()
        cw.gen_error = None
        await db.commit()

        progress = _courseware_progress_reporter(cw, task_id)
        await progress("prepare")
        content = None
        error: str | None = None
        try:
            cfg = await _get_default_llm(cw.teacher_id, db)
            if not cfg:
                raise _GenAbort("未配置可用的大模型，请管理员到系统设置添加并设为默认")

            # 获取课本内容
            chapter_content = ""
            image_catalog = ""
            subject_name = ""
            subject_block = ""
            subject_interactive = ""
            bank_scope: dict | None = None
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
                img_q = img_q.order_by(TextbookImage.page_number, TextbookImage.sort_order).limit(40)
                imgs = (await db.execute(img_q)).scalars().all()
                if imgs:
                    image_catalog = _build_image_catalog(imgs, chapters)

                # 解析该课本所属科目的专属提示词
                tb = (await db.execute(
                    select(Textbook).where(Textbook.id == cw.textbook_id)
                )).scalar_one_or_none()
                if tb:
                    subject_name, subject_block, subject_interactive = await _resolve_subject_prompt(
                        db, cw.teacher_id, tb.subject_id
                    )
                    if tb.subject_id and tb.grade_id:
                        bank_scope = {"subject_id": tb.subject_id, "grade_id": tb.grade_id}

            content = await _generate_lesson_content(
                cfg, cw, chapter_content, image_catalog,
                subject_name, subject_block, subject_interactive,
                progress=progress, bank_scope=bank_scope,
            )
            await progress("save")
        except Exception as e:
            if isinstance(e, _GenAbort):
                logger.warning("课件 %s 生成中止：%s", cw.id, e)
            else:
                logger.exception("课件 %s 生成失败：%s", cw.id, e)
            error = _describe_gen_error(e)
            await db.rollback()

        # 生成期间教师可能又点了重新生成，或任务已被判超时回收
        await db.refresh(cw)
        if task_id and cw.task_id != task_id:
            logger.info("课件 %s 任务 %s 结束时已被取代（当前 %s），丢弃结果", cw.id, task_id, cw.task_id)
            return

        if content is not None:
            cw.content = content
            cw.gen_status = ParseStatus.done
            cw.gen_error = None
            await save_courseware_version(db, cw, cw.teacher_id, skip_if_same=False)
        elif isinstance(cw.content, dict) and cw.content.get("slides"):
            cw.gen_status = ParseStatus.done
            cw.gen_error = f"本次重新生成失败：{error}；已保留上一版内容"[:500]
        else:
            cw.gen_status = ParseStatus.failed
            cw.gen_error = (error or "生成失败")[:500]
        await db.commit()

        # 生成成功后异步把知识点回填到知识图谱（best-effort，不影响课件本身）
        if content is not None:
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
        fixes = _mistake_fixes(p.get("common_mistakes"), 3)
        out.append({
            "name": name[:64],
            "plain_explanation": str(p.get("plain_explanation") or p.get("explanation") or "").strip(),
            "core_concepts": _str_list(p.get("core_concepts"), 5),
            "common_mistakes": [f["wrong"] for f in fixes],
            "mistake_fixes": fixes,
            "life_example": str(p.get("life_example") or "").strip(),
            "activity_goal": str(p.get("activity_goal") or "").strip(),
            "deep_dive": str(p.get("deep_dive") or "").strip(),
            "teacher_focus": str(p.get("teacher_focus") or "").strip(),
            "image_ids": _image_id_list(p.get("image_ids")),
        })
    return out[:max_points]


def _mistake_fixes(raw, limit: int = 3) -> list[dict]:
    """易错项统一成 {wrong, right}；旧格式只有误区字符串时 right 为空。"""
    out: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            wrong = str(item.get("wrong") or item.get("mistake") or "").strip()
            right = str(item.get("right") or item.get("fix") or item.get("correct") or "").strip()
        else:
            wrong, right = str(item or "").strip(), ""
        if wrong:
            out.append({"wrong": wrong, "right": right})
    return out[:limit]


def _image_id_list(raw, limit: int = 2) -> list[int]:
    """模型写的图号可能是 123 / "123" / "#123" / "图#123"，统一成去重的 int。"""
    out: list[int] = []
    for x in raw if isinstance(raw, list) else []:
        digits = "".join(ch for ch in str(x) if ch.isdigit())
        if digits and int(digits) not in out:
            out.append(int(digits))
    return out[:limit]


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
        "image_ids": _image_id_list(raw.get("image_ids")),
    }


_TEACHER_ONLY_RE = re.compile(r"强调|提醒学生|引导学生|让学生|组织学生|请学生|教师用|备课")
_TEACHER_DEMO_RE = re.compile(r"(教师|老师)[^，。；！？]{0,12}?(展示|演示|出示|播放|拿出|点燃|进行)")
_STUDENT_DO_RE = re.compile(r"(?<![让请])学生(观察|思考|讨论|回答|说出|猜测|预测)")
_ASK_STUDENT_RE = re.compile(r"^(请|让|引导)学生(先)?(预测|猜测|猜一猜|思考|回答|说出|讨论|观察)[：:，,]")


def _student_voice_steps(steps: list[dict]) -> tuple[list[dict], list[str]]:
    """导入步骤投影给学生：教师操作句挪进讲稿，「教师展示…」「学生观察…」改成学生视角。"""
    out: list[dict] = []
    moved: list[str] = []
    for st in steps:
        kept = []
        for sent in re.findall(r"[^。；！？]+[。；！？]?", st.get("detail") or ""):
            sent = _ASK_STUDENT_RE.sub("", sent.strip())
            if not sent:
                continue
            if _TEACHER_ONLY_RE.search(sent):
                moved.append(sent.strip())
                continue
            sent = _TEACHER_DEMO_RE.sub(lambda m: "" if m.group(2) in ("展示", "出示", "播放", "拿出", "进行") else m.group(2), sent)
            sent = _STUDENT_DO_RE.sub(r"\1", sent)
            kept.append(sent.strip("，、 "))
        detail = "".join(kept).strip()
        if detail:
            out.append({**st, "detail": detail})
    if not out:
        return steps, []
    return out, moved


def _short_point_name(name: str, limit: int = 14) -> str:
    """互动页标题只用知识点名冒号前的部分，太长时不截断以免断词。"""
    head = re.split(r"[：:]", name or "", maxsplit=1)[0].strip()
    return head if head and len(head) <= limit else (name or "").strip()


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


# 课型：决定蓝图要求、课序与题量。order 里的块名见 _assemble_lesson_from_blueprint
_LESSON_PROFILES: dict[str, dict] = {
    "new": {
        "label": "新授课", "max_examples": 1, "max_exercises": 4,
        "order": ["cover", "intro", "interactive", "knowledge", "comparison",
                  "example", "summary", "exercise", "homework"],
    },
    "review": {
        "label": "复习课", "max_examples": 1, "max_exercises": 6,
        "order": ["cover", "intro", "review_map", "interactive", "knowledge", "comparison",
                  "example", "exercise", "summary", "homework"],
    },
    "practice": {
        "label": "习题课", "max_examples": 2, "max_exercises": 6,
        "order": ["cover", "intro", "knowledge", "interactive", "example", "exercise",
                  "comparison", "summary", "homework"],
    },
    "lab": {
        "label": "实验课", "max_examples": 1, "max_exercises": 4,
        "order": ["cover", "intro", "lab_setup", "interactive", "knowledge", "comparison",
                  "example", "exercise", "summary", "homework"],
    },
}


def _lesson_type(cw) -> str:
    t = str(getattr(cw, "lesson_type", None) or "new")
    return t if t in _LESSON_PROFILES else "new"


def _normalize_lab(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    steps = []
    for item in (raw.get("steps") or [])[:6]:
        if isinstance(item, dict) and (item.get("title") or item.get("detail")):
            steps.append({
                "title": str(item.get("title") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
            })
        elif isinstance(item, str) and item.strip():
            steps.append({"title": "", "detail": item.strip()})
    return {
        "purpose": str(raw.get("purpose") or "").strip(),
        "materials": _str_list(raw.get("materials"), 10),
        "steps": steps,
        "safety": _str_list(raw.get("safety"), 3),
        "observations": _str_list(raw.get("observations"), 4),
    }


def _normalize_blueprint(obj: dict, *, web_style: bool = False, lesson_type: str = "new") -> dict:
    obj = obj or {}
    grain = str(obj.get("lesson_grain") or "period").strip()
    if grain not in ("period", "unit"):
        grain = "period"
    if lesson_type == "review":
        grain = "unit"
    max_points = 4 if grain == "unit" else 2
    points = _normalize_knowledge_points(obj.get("knowledge_points") or [], max_points)
    profile = _LESSON_PROFILES[lesson_type]
    examples = [e for e in (_normalize_example(x) for x in (obj.get("examples") or [])) if e]
    if not examples:
        single = _normalize_example(obj.get("example"))
        examples = [single] if single else []
    examples = examples[: profile["max_examples"]]
    return {
        "topic": str(obj.get("topic") or "").strip(),
        "lesson_grain": grain,
        "lesson_type": lesson_type,
        "cover_subtitle": str(obj.get("cover_subtitle") or "").strip(),
        "objectives": _str_list(obj.get("objectives"), 4),
        "intro": _normalize_intro(obj.get("intro")),
        "knowledge_points": points,
        "example": examples[0] if examples else None,
        "examples": examples,
        "lab": _normalize_lab(obj.get("lab")) if lesson_type == "lab" else None,
        "exercises": _normalize_exercises(obj.get("exercises"))[: profile["max_exercises"]],
        "homework": _normalize_homework(obj.get("homework")),
        "summary": _str_list(obj.get("summary"), 4),
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
    lesson_type = bp.get("lesson_type") or "new"
    min_exercises = 4 if lesson_type in ("review", "practice") else 2
    if len(bp.get("exercises") or []) < min_exercises:
        gaps.append("exercises")
    if lesson_type == "practice" and len(bp.get("examples") or []) < 2:
        gaps.append("examples")
    if lesson_type == "lab" and len((bp.get("lab") or {}).get("steps") or []) < 2:
        gaps.append("lab.steps")
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
    if bp.get("example") and not bp.get("examples"):
        bp["examples"] = [bp["example"]]
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
    """把教师想法写进封面、目标、练习、作业的 notes（只给教师看，学生页不出现）。"""
    if not intent:
        return
    labels = {
        "cover": "教师想法",
        "objectives": "落实教师想法",
        "exercise": "练习需对齐教师要求",
        "homework": "作业需对齐教师要求",
    }
    for slide in slides:
        label = labels.get(slide.get("type"))
        if not label:
            continue
        notes = (slide.get("notes") or "").strip()
        if intent in notes:
            continue
        line = f"{label}：{intent}"
        slide["notes"] = f"{line}\n{notes}".strip() if notes else line


def _merge_slide_patch(slide: dict, patch: dict) -> None:
    if not isinstance(patch, dict):
        return
    for key in ("title", "subtitle", "content", "notes", "prompt", "solution"):
        val = patch.get(key)
        if isinstance(val, str) and val.strip():
            slide[key] = val.strip()
    if slide.get("pairs") and isinstance(patch.get("pairs"), list):
        pairs = _mistake_fixes(patch["pairs"], 10)
        if pairs:
            upd = {"pairs": pairs}
            _keep_slide_pairs_aligned(upd, slide)
            slide.update(upd)
    bullets = patch.get("bullets")
    if isinstance(bullets, list) and not slide.get("pairs"):
        cleaned = [str(x).strip() for x in bullets if str(x).strip()][:8]
        if cleaned:
            old_bullets = slide.get("bullets") or []
            slide["bullets"] = cleaned
            if slide.get("answers") is not None:
                answers = patch.get("answers")
                if isinstance(answers, list) and len(answers) == len(cleaned):
                    slide["answers"] = [str(x or "").strip() for x in answers]
                elif cleaned != old_bullets:
                    # 题改了却没给对得上的答案：宁可不给学生页答案，也不能错配
                    slide.pop("answers", None)
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
    normalize_slide_chem(slide)


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
            **({"answers": slide["answers"]} if slide.get("answers") else {}),
            **({"pairs": slide["pairs"]} if slide.get("pairs") else {}),
        })
    system = """你是一线教研员。按教师想法改写已有课件文案。
硬性规则：
1. 不增删页，不改 index/type，不要输出 html/images/skill。
2. 只改 title/subtitle/bullets/content/notes/prompt/solution/answers/pairs，必须落实教师想法。练习页 answers 与 bullets 一一对应，改了题就同步改答案；易错对照页改 pairs（每条 wrong 配直接纠正它的 right），不要改它的 bullets。
3. 学生页文案面向学生上课看，禁止说课口吻（「本节课我们将学习」「教学目标」「请同学们」）。教师要求写进 notes，不要出现在 title/bullets/content 上。
4. 不得改写公式、方程式、实验现象、装置、单位、数据等学科事实；教师想法只改变讲解侧重与例题情境。
5. 只输出 JSON：{"slides":[{...}]}，不要 markdown。"""
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


_LESSON_TYPE_RULES = {
    "review": (
        "\n\n【课型：复习课——以下要求优先于上面第 1、3 条】"
        "\n- lesson_grain=unit，抽 3～4 个本单元最核心、最易混的知识点，topic 写成「××复习」。"
        "\n- intro 写成「回忆问题链」：steps 给 2～3 个由浅入深、学生凭记忆回答的问题，不做新现象探究。"
        "\n- 每个知识点 plain_explanation 要点出它和其他点的联系；common_mistakes 每点至少 2 条。"
        "\n- exercises 给 6 道覆盖各知识点的综合题，其中至少 1 道跨知识点。"
    ),
    "practice": (
        "\n\n【课型：习题课——以下要求优先于上面第 1、3 条】"
        "\n- 围绕 1～2 个核心解题方法：knowledge_points 的 name 写方法名，core_concepts 写方法步骤/适用条件，"
        "common_mistakes 写典型错法，life_example 写这个方法常见的题型场景。"
        "\n- intro 写成「引例」：一道能引出方法的题，steps 写「读题→找条件/想方法」。"
        "\n- 用 examples 给 2 道例题（先基础后提高），solution 写完整过程并点明方法。"
        "\n- exercises 给 6 道变式题，按「模仿→变式→拓展」排列。"
    ),
    "lab": (
        "\n\n【课型：实验课——以下要求优先于上面第 3 条】"
        "\n- 必须给 lab：purpose（实验要回答的问题）、materials（器材与试剂）、steps（3～6 步具体操作）、"
        "safety（1～3 条安全注意）、observations（应观察到的现象，教师用）。实验必须是课本里的，不得另编。"
        "\n- intro 写成「提出问题 + 猜想」，不要提前说出现象。"
        "\n- knowledge_points 写实验得出的结论与原理，activity_goal 写学生在实验台上要完成的操作。"
    ),
}


def _lesson_extract_prompts(
    cw, chapter_content: str, subject_name: str, subject_block: str, web_style: bool,
    missing: list[str] | None = None, image_catalog: str = "",
):
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
    image_rule = ""
    intro_img_field = ""
    point_img_field = ""
    if image_catalog:
        image_rule = (
            "\n9. 用户消息末尾有【课本插图清单】，你看不到图本身，只能凭图注、页码和所在小节判断。"
            "有图注的图以图注为准：图注讲的正是这个知识点的实验装置、现象或示意图（如「电解水实验」「水分子分解示意图」）时，"
            "务必把图号（数字）写进该处 image_ids；没有图注的，只有所在小节正好讲这个知识点时才用。"
            "每处最多 2 张，同一张图不要重复用；拿不准就留空数组。优先用「插图」，「整页截图」只在没有插图可用时才用。"
        )
        intro_img_field = ',\n    "image_ids": []'
        point_img_field = ',\n      "image_ids": []'
    lesson_type = _lesson_type(cw)
    type_rule = _LESSON_TYPE_RULES.get(lesson_type, "")
    example_field = '"example": {"prompt": "完整题干（含选项则写在同一段）", "solution": "判断依据"},'
    lab_field = ""
    if lesson_type == "practice":
        example_field = (
            '"examples": [{"prompt": "例题1（基础）", "solution": "完整解题过程与方法点拨"}, '
            '{"prompt": "例题2（提高）", "solution": "完整解题过程与方法点拨"}],'
        )
    if lesson_type == "lab":
        lab_field = (
            '\n  "lab": {"purpose": "这个实验要回答的问题", "materials": ["器材或试剂"], '
            '"steps": [{"title": "步骤名", "detail": "具体操作"}], "safety": ["安全注意"], '
            '"observations": ["应观察到的现象（教师用，先不给学生看）"]},'
        )
    from app.services.courseware_components import ACCURACY_RULES

    system_prompt = f"""你是一线特级教师。根据课题和课本，设计【一节可直接上的 45 分钟课】的教学蓝图，只输出 JSON。{subject_hint}

{ACCURACY_RULES}

要求：
0. 下面「课本内容」是事实来源。知识点、公式、方程式、现象、装置、数据必须与之相符；对不上就不要写进蓝图。
1. 先定课时：课题若是大单元名（如酸碱盐、力、电），默认 lesson_grain=period，只取本节最该先上的 1～2 个点，topic 写成具体课时名（如「溶液的酸碱性：指示剂与pH」），不要用单元名当课时名。仅当教师明确要求单元复习时用 unit，可抽 3～4 点。
2. 目标必须可检测（能说出/会判断/会操作），禁止「理解某某标题」「掌握某某知识点」。目标给学生上课前不要念，写进 objectives 供教师备课。
3. 导入必须是具体物品或现象，禁止「从熟悉的生活场景出发」这类空话。课序是先探究再命名：学生先看现象、动手，再出现规范说法。intro.steps 会直接投影给学生，用学生视角写（如「看：点燃纯净的氢气，罩上干燥烧杯」「问：烧杯壁上的液滴是哪来的？」），禁止出现「教师展示」「学生观察」「强调」等操作说明；教师怎么演示、安全提醒写进 intro.content。
4. 每个知识点必须有：至少 2 条 core_concepts、至少 1 个真实 life_example、至少 1 条 common_mistakes（每条 wrong 都要配一句直接纠正它的 right，不要拿别的要点凑）。理科符号必须规范：化学式用 Unicode 下标（CO₂、H₂O、C₆H₁₂O₆），禁止 CO2/H2O/Co2；物理单位用上标（m/s²、cm²），初速度写 v₀ 不是 v0；数学公式用 $...$，禁止 a2、R2 当指数；三角函数名小写 sin/cos/tan。
5. 例题、随堂练习、作业都要写具体题面；作业禁止「自拟题」，并包含一个小作品（如体检单、方案、口头报告）。练习要带简短判断依据（给学生看题，依据留给教师）。
6. 小结写学生能复述的短句，不要重复知识点标题。小结、例题、练习、作业只考 knowledge_points 里讲过的概念；要考的概念（如单质/化合物/氧化物）必须先写进某个知识点的 core_concepts。
6.1 实验结论写全课本给出的关键定量关系（如电解水正负极气体体积比约 1∶2），不要只写「较多/较少」。
7. 只输出 JSON，不要 markdown。{web_rule}{intent_rule}{lab_rule}{retry_rule}{image_rule}{type_rule}

JSON 格式：
{{
  "topic": "具体课时名，不要照抄过大的单元名",
  "lesson_grain": "period",
  "cover_subtitle": "一句课眼",
  "objectives": ["能……", "会……"],
  "intro": {{
    "title": "具体情境标题",
    "subtitle": "",
    "content": "为什么从这个现象切入、教师怎么演示、安全提醒（教师备课，不投影）",
    "steps": [{{"title": "看", "detail": "学生要看的具体物品/现象（投影给学生）"}}, {{"title": "问", "detail": "学生要回答的问题"}}]{intro_img_field}
  }},
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "plain_explanation": "用白话解释",
      "core_concepts": ["要点1", "要点2"],
      "common_mistakes": [{{"wrong": "学生常见的错误说法", "right": "针对这条错误的正确说法（一句话，直接纠正它）"}}],
      "life_example": "真实物品或课本实例",
      "activity_goal": "互动要达成的可观察目标"{deep_dive_field}{focus_field}{point_img_field}
    }}
  ],{lab_field}
  {example_field}
  "exercises": [{{"question": "具体题", "answer": "依据"}}],
  "homework": [{{"task": "基础：……"}}, {{"task": "规范或挑战：……"}}],
  "summary": ["带走的短句1", "短句2"]
}}"""
    user_prompt = (
        f"课件课题：{cw.title}\n\n"
        "【课本原文——学科事实必须以这里为准，禁止编造】\n"
        f"{chapter_content[:9000]}"
    )
    if intent:
        user_prompt += (
            f"\n\n【教师想法——必须遵守；只改讲解侧重与例题情境，不得改写学科事实】\n{intent}\n"
            "请据此决定讲哪些点、讲到多深、用什么例子。"
        )
    if image_catalog:
        user_prompt += f"\n\n【课本插图清单】\n{image_catalog}"
    return system_prompt, user_prompt


async def _extract_lesson_blueprint(
    cfg,
    cw,
    chapter_content: str,
    subject_name: str = "",
    subject_block: str = "",
    web_style: bool = False,
    progress=None,
    image_catalog: str = "",
) -> dict:
    """抽出一节课的教学蓝图：课时名、目标、导入、知识点、例题、练习、作业。"""
    progress = progress or _no_progress
    await progress("blueprint", "抽取知识点、导入、例题、练习与作业")
    max_tok = max(cfg.max_tokens or 0, 7000 if web_style else 5000)
    system_prompt, user_prompt = _lesson_extract_prompts(
        cw, chapter_content, subject_name, subject_block, web_style,
        image_catalog=image_catalog,
    )
    resp = await _call_llm(
        cfg,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=max_tok,
    )
    obj = _parse_json_object(_resp_content(resp)) or {}
    lesson_type = _lesson_type(cw)
    bp = _normalize_blueprint(obj, web_style=web_style, lesson_type=lesson_type)
    gaps = _blueprint_gaps(bp)
    if gaps:
        logger.info("课件 %s 蓝图缺字段，补抽一次：%s", getattr(cw, "id", "?"), "、".join(gaps[:8]))
        await progress("blueprint", "首轮内容有缺项，正在补全")
        system2, user2 = _lesson_extract_prompts(
            cw, chapter_content, subject_name, subject_block, web_style, missing=gaps,
            image_catalog=image_catalog,
        )
        resp2 = await _call_llm(
            cfg,
            [{"role": "system", "content": system2}, {"role": "user", "content": user2}],
            max_tokens=max_tok,
        )
        obj2 = _parse_json_object(_resp_content(resp2)) or {}
        bp2 = _normalize_blueprint(obj2, web_style=web_style, lesson_type=lesson_type)
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
            if bp2.get("examples") and len(bp2["examples"]) >= len(bp.get("examples") or []):
                bp["example"] = bp2["example"]
                bp["examples"] = bp2["examples"]
            if (bp2.get("lab") or {}).get("steps"):
                bp["lab"] = bp2["lab"]
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


_MACRO_LAB_HINTS = (
    "制取", "倾倒", "熄灭蜡烛", "电解", "过滤", "蒸发",
    "实验装置", "组装装置", "集气", "排水法", "排空气",
    "点燃蜡烛", "灭火原理", "酒精灯加热", "试管口",
    "实验台", "宏观实验", "两支蜡烛",
)
_FAKE_LAB_MARKERS = (
    "实验台演示", "开始演示", "虚拟实验", "虚拟实验台",
    "观察两支蜡烛的状态", "较高处蜡烛", "较低处蜡烛",
)


def _point_text(point: dict) -> str:
    return " ".join(
        str(point.get(k) or "")
        for k in ("name", "plain_explanation", "activity_goal", "life_example")
    )


def _needs_deterministic_lab(point: dict, subject_name: str) -> bool:
    """宏观实验过程必须走系统实验台，不能让 LLM 现编演示。"""
    s = subject_name or ""
    if "化学" not in s and "科学" not in s:
        return False
    blob = _point_text(point)
    return any(w in blob for w in _MACRO_LAB_HINTS)


def _html_fakes_experiment(html: str) -> bool:
    """LLM 片段冒充实验台时丢弃（系统实验台带 edu-lab 标记）。"""
    if not html or "edu-lab:" in html or "edu-sim:" in html:
        return False
    return any(m in html for m in _FAKE_LAB_MARKERS)


async def _generate_interactive_html_for_point(
    cfg,
    cw,
    point: dict,
    point_idx: int,
    subject_name: str,
    image_catalog: str,
    interactive_hint: str,
    chapter_content: str = "",
) -> str:
    """按知识点生成单页互动 HTML（片段）。

    直接要求 LLM 输出 ```html 代码块，完全避免 JSON-in-JSON 的双重转义问题。
    """
    image_ref = f"\n可引用课本图片：\n{image_catalog}" if image_catalog else ""
    textbook_ref = ""
    excerpt = (chapter_content or "").strip()
    if excerpt:
        textbook_ref = (
            "\n【课本原文（事实来源）】互动中的定义、公式、方程式、现象、数据必须与此一致，"
            f"不要另编实验或装置：\n{excerpt[:3500]}\n"
        )
    prompt = f"""请围绕以下知识点，生成 1 页可直接运行的互动课件 HTML 片段。

课件标题：{cw.title}
知识点序号：{point_idx}
知识点：{point.get("name", "")}
白话解释：{point.get("plain_explanation", "")}
核心要点：{json.dumps(point.get("core_concepts") or [], ensure_ascii=False)}
常见误区：{json.dumps(point.get("common_mistakes") or [], ensure_ascii=False)}
生活例子：{point.get("life_example", "")}
互动目标：{point.get("activity_goal", "")}
学科：{subject_name or "通用"}{image_ref}{textbook_ref}{_interactive_teacher_intent_block(cw, point)}

风格要求：
- 生动、直白，句子短。至少 1 个真实情境、1 个可操作互动（点击/拖拽/输入）。
- 一屏只做一个主操作（观察 / 调节 / 判断三选一），不要再堆一套选择题或概念清单。
- 先观察或判断，再公布规范说法；不要在学生操作前列出核心要点或答案。
- 反馈要诠释现象：根据学生看到的颜色/读数/变化说明「为什么这样判断」，不要只写「正确/错误」。
- 学科事实必须正确，以课本为准。化学：石蕊只有红/紫/蓝，酚酞只有无色/红；彩虹色仅用于 pH 试纸；不要用万能指示剂颜色冒充石蕊或酚酞。
- 禁止用 CSS/SVG 自绘化学实验装置。禁止「实验台演示」「开始演示」、禁止用按钮切换蜡烛燃烧/熄灭来假装做实验。宏观实验由系统实验台演示；本页只做判断、配平、读数或步骤排序。
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
            f"不要写实验台、开始演示或蜡烛熄灭动画。"
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

    if _html_fakes_experiment(html):
        logger.warning("课件 %s 知识点%s 互动页是假实验台，改用本地判断模板", cw.id, point_idx)
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
    "title", "subtitle", "bullets", "answers", "pairs", "content", "more", "notes",
    "prompt", "solution", "left_title", "right_title", "columns", "steps",
)


def _slide_prompt_payload(slide: dict) -> dict:
    return {k: slide.get(k) for k in ("type", *_SLIDE_TEXT_KEYS) if k in slide or k == "type"}


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
    for k in ("title", "subtitle", "content", "more", "notes", "prompt", "solution", "left_title", "right_title"):
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
    if isinstance(obj.get("answers"), list):
        out["answers"] = [_as_slide_text(x) or "" for x in obj["answers"]]
    if isinstance(obj.get("pairs"), list):
        pairs = _mistake_fixes(obj["pairs"], 10)
        if pairs:
            out["pairs"] = pairs
    _keep_slide_pairs_aligned(out, original)
    return out


def _keep_slide_pairs_aligned(out: dict, original: dict) -> None:
    """练习答案须与题目一一对应、易错配对须与两栏一致；对不上就清空，学生页回退旧样式而不是错配。"""
    if "bullets" in out or "answers" in out:
        bullets = out.get("bullets", original.get("bullets") or [])
        answers = out.get("answers", original.get("answers"))
        if answers is not None and len(answers) != len(bullets):
            out["answers"] = []
    if out.get("pairs"):
        pairs = out["pairs"]
        out["columns"] = [
            {"title": original.get("left_title") or "常见误区", "items": [p["wrong"] for p in pairs]},
            {"title": original.get("right_title") or "正确说法", "items": [p["right"] for p in pairs]},
        ]
        out["bullets"] = [p["wrong"] for p in pairs] + [p["right"] for p in pairs]
    elif ("columns" in out or "bullets" in out) and original.get("pairs"):
        out["pairs"] = []


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
                    allow_lab=True,
                )
        except Exception as e:
            logger.warning("单页优化 skill 失败，回退 LLM：%s", e)
        if not html and _needs_deterministic_lab(point, subject_name):
            html = _fallback_interactive_html(point, index + 1)
        if not html:
            class _Cw:
                title = cw_title
                id = 0
            html = await _generate_interactive_html_for_point(
                cfg=cfg, cw=_Cw(), point=point, point_idx=index + 1,
                subject_name=subject_name, image_catalog="",
                interactive_hint=build_interactive_prompt(subject_interactive),
            )
        if _html_fakes_experiment(html):
            html = _fallback_interactive_html(point, index + 1)
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
    if mode != "notes":
        if "answers" in slide:
            schema_note += '；练习页另有 "answers":[""]，与 bullets 一一对应，改题必须同步改答案'
        if slide.get("pairs"):
            schema_note += '；易错对照页另有 "pairs":[{"wrong":"错误说法","right":"直接纠正它的正确说法"}]，以 pairs 为准'
        if "more" in slide:
            schema_note += '；知识页另有 "more":"深入理解（学生页折叠）"'
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
- 不得改写公式、方程式、实验现象、装置、单位、数据；拿不准的内容不要编。
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
    progress=None,
    bank_scope: dict | None = None,
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
    progress = progress or _no_progress
    blueprint = await _extract_lesson_blueprint(
        cfg, cw, chapter_content, subject_name, subject_block, web_style=is_web,
        progress=progress, image_catalog=image_catalog,
    )
    points = (blueprint or {}).get("knowledge_points") or []
    if not points:
        logger.warning("课件 %s 未提取到有效知识点，回退到旧版整课件生成", cw.id)
        await progress("blueprint", "未抽到知识点，改为整课一次生成（较慢）")
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
准确性是硬性要求：定义、公式、方程式、实验现象与装置必须与课本一致，禁止编造；课件内动画必须演示正确过程。
要求：
1. 课件需有 meta + slides 结构。每页字段：index,type,title,subtitle,bullets,content,notes；对比页可加 columns[{{title,items}}]，过程页可加 steps[{{title,detail}}]，例题页可加 prompt/solution。
2. 课序必须先探究再命名：cover → process（导入）→ interactive → knowledge → comparison → example → summary → exercise → homework。
   不要生成 objectives 页；可检测目标只写在 meta.objectives，供教师备课。
   type 从以上标准类型中选；旧别名 title/content/intro/quiz 也可。
3. 全部中文，输出严格 JSON，不要 markdown 代码块。
4. 若为互动课件，可在 interactive 页附 html 字段（片段）。一屏一个主操作；反馈要诠释现象，不要只报对错。
5. 例题解析、练习答案只写在 notes，不要和题干并排展示。作业含一个小作品（体检单/方案/口头报告）。学生页禁止说课口吻。
6. 若用户给出了教师想法，落实在例题、练习与作业的题面和讲解侧重上，用学生能看懂的话写，不要写成教案或说课稿。
{interactive_hint}
"""
        lesson_type = _lesson_type(cw)
        if lesson_type != "new":
            system_prompt += _LESSON_TYPE_RULES[lesson_type].replace("上面第 1、3 条", "上面的课序").replace(
                "上面第 3 条", "上面的课序",
            )
        user_prompt = (
            f"课件课题：{cw.title}（{_LESSON_PROFILES[lesson_type]['label']}）\n\n"
            "【课本原文——学科事实必须以这里为准，禁止编造】\n"
            f"{chapter_content[:8000]}{image_hint}"
        )
        fallback_intent = _teacher_intent(cw)
        if fallback_intent:
            user_prompt += (
                "\n\n【教师想法——硬约束，落实在学生能看到的题面与讲解侧重上，不要写成说课稿】\n"
                f"{fallback_intent}"
            )
        resp = await _call_llm(
            cfg,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=max(cfg.max_tokens or 0, 8000),
        )
        raw = _resp_content(resp)
        data = _parse_lesson_json(raw)
        if data and data.get("slides"):
            if fallback_intent:
                await progress("intent")
                data = await _apply_teacher_intent(cfg, cw, data, fallback_intent)
            return normalize_lesson_chem(data)
        fallback = {
            "meta": {"title": cw.title},
            "slides": [{"index": 1, "type": "content", "title": cw.title, "content": raw, "bullets": [], "notes": ""}],
        }
        if fallback_intent:
            await progress("intent")
            fallback = await _apply_teacher_intent(cfg, cw, fallback, fallback_intent)
        return normalize_lesson_chem(fallback)

    if bank_scope:
        await progress("bank")
        profile = _LESSON_PROFILES[_lesson_type(cw)]
        limit = profile["max_examples"] + profile["max_exercises"] - 1
        bank = await _bank_questions_for_points(bank_scope, points, limit)
        if bank:
            _merge_bank_into_blueprint(blueprint, bank, profile)
            await progress("bank", f"用上题库真题 {len(bank)} 道")

    return await _assemble_lesson_from_blueprint(
        cfg, cw, blueprint, points, subject_name, image_catalog, interactive_hint, is_web,
        chapter_content=chapter_content, progress=progress,
    )


async def _bank_questions_for_points(bank_scope: dict, points: list[dict], limit: int = 4) -> list[dict]:
    """按知识点名去全站题库找题；失败不影响生成。"""
    from app.services.question_bank_service import pick_for_lesson

    names = [p.get("name") or "" for p in points]
    try:
        async with AsyncSessionLocal() as db:
            return await pick_for_lesson(
                db,
                subject_id=bank_scope["subject_id"],
                grade_id=bank_scope["grade_id"],
                kp_names=names,
                limit=limit,
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("课件题库选题失败，全部用 AI 出题：%s", e)
        return []


def _merge_bank_into_blueprint(bp: dict, bank: list[dict], profile: dict | None = None) -> None:
    """题库真题优先：有解析的做例题（按课型 1～2 道），其余排在练习最前，留至少 1 道 AI 题，AI 题补足题量。"""
    profile = profile or _LESSON_PROFILES["new"]
    max_examples, max_exercises = profile["max_examples"], profile["max_exercises"]
    rest = list(bank)
    bank_examples = []
    for q in [q for q in rest if q.get("explanation")][:max_examples]:
        rest.remove(q)
        solution = f"答案：{q['answer']}。{q['explanation']}" if q.get("answer") else q["explanation"]
        bank_examples.append({"prompt": q["text"], "solution": solution, "question_id": q["id"]})
    if bank_examples:
        ai_examples = [e for e in (bp.get("examples") or []) if not e.get("question_id")]
        bp["examples"] = (bank_examples + ai_examples)[:max_examples]
        bp["example"] = bp["examples"][0]
    bank_ex = [
        {
            "question": q["text"],
            "answer": "；".join(x for x in (q.get("answer"), q.get("explanation")) if x),
            "question_id": q["id"],
        }
        for q in rest[: max_exercises - 1]
    ]
    ai_ex = [e for e in (bp.get("exercises") or []) if not e.get("question_id")]
    bp["exercises"] = (bank_ex + ai_ex)[:max_exercises]


_TYPE_COPY = {
    "new": {
        "intro_title": "先看这个现象", "intro_sub": "先观察，再下判断",
        "intro_note": "停课点：学生说完自己的判断后再往下翻。这一页只观察、只表达，不公布规范说法。",
        "cover_note": "开场抛出本节核心问题：{topic}。不要念教学目标。停课点：学生猜完再进情境。",
        "kp_title": "{name}", "kp_sub": "把刚才看到的现象说成规范说法",
        "kp_note": "停课点：先让学生用刚才的现象自己说，再揭开规范说法。讲解要短句、直白。",
        "cmp_title": "易错对照", "cmp_sub": "把误区掰过来",
        "ex_title": "随堂练习", "ex_sub": "当堂检验，先写依据再对答案",
        "sum_title": "今天带走这几句话",
    },
    "review": {
        "intro_title": "先回忆这几个问题", "intro_sub": "不看书，先说出来",
        "intro_note": "停课点：学生先凭记忆回答，答不上的记在黑板上，梳理时重点讲。",
        "cover_note": "本节复习：{topic}。先让学生说出本单元还记得的关键词。",
        "kp_title": "{name}", "kp_sub": "要点回顾",
        "kp_note": "停课点：先让学生补全要点，再对照；重点讲刚才答不上的点。",
        "cmp_title": "易错对照", "cmp_sub": "复习最该纠正的说法",
        "ex_title": "综合练习", "ex_sub": "覆盖各知识点，先写依据再对答案",
        "sum_title": "这一单元带走这几句话",
    },
    "practice": {
        "intro_title": "先看这道引例", "intro_sub": "想想用什么方法",
        "intro_note": "停课点：先让学生说思路，不急着算；把想到的方法写在黑板上。",
        "cover_note": "本节习题课：{topic}。先问学生做这类题时最卡在哪一步。",
        "kp_title": "方法：{name}", "kp_sub": "方法要点",
        "kp_note": "停课点：结合引例讲清每一步为什么这样做、什么条件下能用。",
        "cmp_title": "典型错法", "cmp_sub": "错在哪一步，怎么改",
        "ex_title": "变式训练", "ex_sub": "模仿 → 变式 → 拓展",
        "sum_title": "方法小结",
    },
    "lab": {
        "intro_title": "这个实验要回答什么问题", "intro_sub": "先猜结果，再动手验证",
        "intro_note": "停课点：先让学生预测现象，写在黑板上，实验后对照。不要提前说出现象。",
        "cover_note": "本节实验课：{topic}。先抛出要用实验回答的问题。",
        "kp_title": "{name}", "kp_sub": "实验结论",
        "kp_note": "停课点：先让学生根据看到的现象说结论，再给规范表述。",
        "cmp_title": "易错对照", "cmp_sub": "实验和结论里容易错的地方",
        "ex_title": "随堂练习", "ex_sub": "用实验结论解决问题",
        "sum_title": "今天带走这几句话",
    },
}


async def _assemble_lesson_from_blueprint(
    cfg, cw, blueprint: dict, points: list[dict],
    subject_name: str, image_catalog: str, interactive_hint: str, is_web: bool,
    chapter_content: str = "",
    progress=None,
) -> dict:
    """按课型把蓝图拼成课件：先拼各块，再按 _LESSON_PROFILES[课型]["order"] 排序编号。

    目标只进 meta，不给学生看。
    """
    progress = progress or _no_progress
    from app.models.courseware import RenderStyle
    from app.services.animation_service import resolve_keys as _resolve_anim_keys

    lesson_type = _lesson_type(cw)
    profile = _LESSON_PROFILES[lesson_type]
    copy_ = _TYPE_COPY[lesson_type]

    topic = blueprint.get("topic") or cw.title
    unit_note = f"单元：{cw.title}。" if topic != cw.title else ""
    subtitle = blueprint.get("cover_subtitle") or (
        f"{subject_name} · {cw.title}" if subject_name else cw.title
    )
    intro = blueprint.get("intro") or _normalize_intro({})
    examples = blueprint.get("examples") or (
        [blueprint["example"]] if blueprint.get("example") else []
    )
    examples = examples[: profile["max_examples"]]
    exercises = (blueprint.get("exercises") or [])[: profile["max_exercises"]]
    homework = blueprint.get("homework") or []
    summary = blueprint.get("summary") or []
    objectives = blueprint.get("objectives") or []
    lab = blueprint.get("lab") or {}

    # 只认候选清单里的图号，防止模型编号或引用别的课本的图；一张图只用一次
    allowed_images = {int(x) for x in re.findall(r"图#(\d+)", image_catalog or "")}
    used_images: set[int] = set()

    def _pick_images(ids) -> list[int]:
        picked = [i for i in (ids or []) if i in allowed_images and i not in used_images][:2]
        used_images.update(picked)
        return picked

    # 互动预算：新授课默认共 2 个互动页，动画库自动匹配（至多 1 实验台 + 1 动画）优先，
    # 剩余名额给概念互动；教师手选的动画全保留并另配 1 个概念互动。
    # 复习/习题课只做 1 个概念互动、不自动塞动画；实验课优先动画库实验台。
    explicit_anim = bool(getattr(cw, "animation_keys", None))
    anim_keys: list[str] = []
    if cw.is_interactive:
        if lesson_type in ("review", "practice") and not explicit_anim:
            anim_keys = []
        else:
            anim_keys = _resolve_anim_keys(cw, points, topic, subject_name)
            if not explicit_anim:
                anim_keys = anim_keys[:2]
    point_ix_budget = 0
    if cw.is_interactive:
        if lesson_type == "new":
            point_ix_budget = 1 if explicit_anim else max(0, 2 - len(anim_keys))
        elif lesson_type == "lab":
            point_ix_budget = 0 if anim_keys else 1
        else:
            point_ix_budget = 1

    blocks: dict[str, list[dict]] = {}

    blocks["cover"] = [{
        "type": "cover", "title": topic, "subtitle": subtitle,
        "bullets": [], "content": "",
        "notes": (unit_note + copy_["cover_note"].format(topic=topic)).strip(),
    }]

    intro_steps, intro_moved = _student_voice_steps(intro.get("steps") or [])
    intro_notes = " ".join(filter(None, [
        intro.get("content"),
        ("演示提醒：" + "".join(intro_moved)) if intro_moved else "",
        copy_["intro_note"],
    ]))
    blocks["intro"] = [{
        "type": "process",
        "title": intro.get("title") or copy_["intro_title"],
        "subtitle": intro.get("subtitle") or copy_["intro_sub"],
        "bullets": [s["detail"] for s in intro_steps if s.get("detail")][:3],
        "steps": intro_steps,
        "images": _pick_images(intro.get("image_ids")),
        "content": "",
        "notes": intro_notes,
    }]

    if lesson_type == "review":
        map_items = [
            f"{p['name']}：{(p.get('plain_explanation') or '')[:48]}".rstrip("：")
            for p in points
        ]
        blocks["review_map"] = [{
            "type": "knowledge",
            "title": "知识梳理",
            "subtitle": "先理清这几块之间的联系",
            "bullets": map_items,
            "content": "",
            "notes": "停课点：先让学生自己画知识结构图或说出联系，再对照这一页。",
        }]

    if lesson_type == "lab" and (lab.get("steps") or lab.get("materials")):
        parts = []
        if lab.get("materials"):
            parts.append("### 器材与试剂\n" + "\n".join(f"- {m}" for m in lab["materials"]))
        if lab.get("safety"):
            parts.append("### 安全提示\n" + "\n".join(f"- {s}" for s in lab["safety"]))
        notes = "停课点：先让学生复述步骤和安全要求，再动手。"
        if lab.get("observations"):
            notes += "\n应观察到的现象（先不告诉学生）：" + "；".join(lab["observations"])
        blocks["lab_setup"] = [{
            "type": "process",
            "title": "实验目的与步骤",
            "subtitle": lab.get("purpose") or "按步骤操作，边做边记录现象",
            "bullets": [s["detail"] for s in lab.get("steps") or [] if s.get("detail")][:3],
            "steps": lab.get("steps") or [],
            "content": "\n\n".join(parts),
            "notes": notes,
        }]

    concept_slides: list[dict] = []
    interactive_jobs: list[tuple[dict, int, dict]] = []
    for point_i, p in enumerate(points, 1):
        if point_i > point_ix_budget:
            break
        slide = {
            "type": "interactive",
            "title": f"{_short_point_name(p['name'])} · 动手做",
            "subtitle": "先观察再下结论",
            "bullets": [],
            "content": "",
            "notes": (
                (f"互动目标：{p['activity_goal']}\n" if p.get("activity_goal") else "")
                + "停课点：操作后先问「你看到了什么？这说明什么？」不要立刻给标准答案。"
                "反馈要诠释现象，不要只报对错。"
            ),
        }
        concept_slides.append(slide)
        interactive_jobs.append((slide, point_i, p))

    used_anim: set[str] = set()
    if interactive_jobs:
        from app.services import skill_service
        sem = asyncio.Semaphore(3)

        async def _gen_html(point_i: int, p: dict) -> tuple[str, dict | None]:
            async with sem:
                html = ""
                routed = None
                try:
                    from app.services.skill_service import match_lab_key
                    lab_key = match_lab_key(_point_text(p))
                    html, routed = await skill_service.maybe_generate_skill(
                        cfg, p, subject_name, lab_key=lab_key, allow_lab=True,
                    )
                except Exception as e:
                    logger.warning("课件 %s 知识点 %s skill 生成失败，回退 LLM：%s", cw.id, p.get("name"), e)
                if not html and _needs_deterministic_lab(p, subject_name):
                    logger.warning(
                        "课件 %s 知识点「%s」需要真实实验台但未命中 skill，不用 LLM 假实验",
                        cw.id, p.get("name"),
                    )
                    html = _fallback_interactive_html(p, point_i)
                if not html:
                    try:
                        html = await _generate_interactive_html_for_point(
                            cfg=cfg, cw=cw, point=p, point_idx=point_i,
                            subject_name=subject_name, image_catalog=image_catalog,
                            interactive_hint=interactive_hint,
                            chapter_content=chapter_content,
                        )
                    except Exception as e:
                        logger.warning("课件 %s 知识点 %s 互动页生成失败：%s", cw.id, p.get("name"), e)
                    if _html_fakes_experiment(html):
                        logger.warning("课件 %s 丢弃知识点「%s」的假实验页", cw.id, p.get("name"))
                        html = _fallback_interactive_html(p, point_i)
                return html or "", routed

        total_ix = len(interactive_jobs)
        finished_ix = 0
        await progress("interactive", f"0/{total_ix}")

        async def _gen_html_tracked(point_i: int, p: dict) -> tuple[str, dict | None]:
            nonlocal finished_ix
            try:
                return await _gen_html(point_i, p)
            finally:
                finished_ix += 1
                await progress("interactive", f"{finished_ix}/{total_ix}")

        htmls = await asyncio.gather(*[_gen_html_tracked(pi, p) for _, pi, p in interactive_jobs])
        from app.services.animation_service import KIND_SUBTITLE
        for (slide, _, _), (html, routed) in zip(interactive_jobs, htmls):
            if html:
                slide["html"] = html
            if routed:
                slide["skill"] = routed
                kind = routed.get("kind") or ""
                if kind in KIND_SUBTITLE:
                    slide["subtitle"] = KIND_SUBTITLE[kind]
                if routed.get("title"):
                    slide["title"] = routed["title"]
                for k in (routed.get("asset_key"), routed.get("problem_type")):
                    if k:
                        used_anim.add(str(k))

    anim_slides: list[dict] = []
    if anim_keys:
        from app.services.animation_service import payload_for_key, KIND_SUBTITLE
        for key in anim_keys:
            if key in used_anim:
                continue
            try:
                html, routed = await payload_for_key(key)
            except Exception as e:
                logger.warning("课件 %s 引用动画 %s 失败：%s", cw.id, key, e)
                continue
            if not html or not routed:
                continue
            kind = routed.get("kind") or ""
            is_lab = kind in ("chem_lab", "physics_lab") or routed.get("skill") == "edu-chem-lab"
            anim_slides.append({
                "type": "interactive",
                "title": routed.get("title") or ("互动实验台" if is_lab else "互动动画"),
                "subtitle": KIND_SUBTITLE.get(kind) or (
                    "实验台 · 可操作演示" if is_lab else "动画 · 可操作演示"
                ),
                "bullets": [],
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
    # 实验课先上实验台，再做概念互动
    blocks["interactive"] = (
        anim_slides + concept_slides if lesson_type == "lab" else concept_slides + anim_slides
    )

    # 知识页投影给学生：只放要点、例子和图。白话讲法与深入讲解给教师，
    # 网页样式的深入理解折叠在 more 里；误区统一放到后面的易错对照页。
    knowledge_slides = []
    for point_i, p in enumerate(points, 1):
        bullets = p.get("core_concepts") or []
        if not bullets and p.get("plain_explanation"):
            bullets = [p["plain_explanation"]]
        content_parts = []
        notes_bits = [copy_["kp_note"]]
        if p.get("plain_explanation") and p.get("core_concepts"):
            notes_bits.append(f"白话讲法：{p['plain_explanation']}")
        if p.get("teacher_focus"):
            notes_bits.append(f"落实教师要求：{p['teacher_focus']}")
        if p.get("deep_dive") and not is_web:
            notes_bits.append(f"深入讲解：{p['deep_dive']}")
        example = (p.get("life_example") or "").strip()
        if example:
            if lesson_type == "practice":
                label = "常见题型"
            elif example.startswith("课本"):
                label = "课本里的例子"
            else:
                label = "生活中的例子"
            content_parts.append(f"### {label}\n- {example}")
        name = copy_["kp_title"].format(name=p["name"])
        slide = {
            "type": "knowledge",
            "title": name if len(points) == 1 else f"{point_i}. {name}",
            "subtitle": copy_["kp_sub"],
            "bullets": bullets[:4],
            "images": _pick_images(p.get("image_ids")),
            "content": "\n\n".join(content_parts),
            "notes": "\n".join(notes_bits),
        }
        if is_web and p.get("deep_dive"):
            slide["more"] = p["deep_dive"]
        knowledge_slides.append(slide)
    blocks["knowledge"] = knowledge_slides

    # 易错对照：每条误区配它自己的纠正，各知识点轮流取，保证每个点都有代表
    per_point = [
        p.get("mistake_fixes") or [{"wrong": m, "right": ""} for m in p.get("common_mistakes") or []]
        for p in points
    ]
    pairs: list[dict] = []
    for round_i in range(max((len(x) for x in per_point), default=0)):
        for fixes in per_point:
            if round_i < len(fixes) and len(pairs) < 5:
                pairs.append(fixes[round_i])
    if pairs:
        pairs = [{"wrong": f["wrong"], "right": f.get("right") or ""} for f in pairs]
        lefts = [f["wrong"] for f in pairs]
        rights = [f["right"] or "想一想：错在哪里？" for f in pairs]
        blocks["comparison"] = [{
            "type": "comparison",
            "title": copy_["cmp_title"],
            "subtitle": copy_["cmp_sub"],
            "left_title": "常见误区",
            "right_title": "正确说法",
            "pairs": pairs,
            "columns": [
                {"title": "常见误区", "items": lefts},
                {"title": "正确说法", "items": rights},
            ],
            "bullets": lefts + rights,
            "content": "",
            "notes": "停课点：逐条先让学生指出错在哪里，再点开正确说法。",
        }]

    example_slides = []
    for i, ex in enumerate(examples, 1):
        solution = ex.get("solution") or ""
        title = "例题精讲" if len(examples) == 1 else f"例题 {i}"
        slide = {
            "type": "example",
            "title": title,
            "subtitle": "先做，再对照依据",
            "prompt": ex["prompt"],
            "bullets": [],
            "content": "",
            "solution": solution,
            "notes": (
                ("本题来自题库。\n" if ex.get("question_id") else "")
                + "停课点：先独立做，不要投影解析。\n"
                f"解析：{solution}\n"
                "追问：条件变一变，结论或方法还成立吗？"
            ),
        }
        if ex.get("question_id"):
            slide["bank_question_ids"] = [ex["question_id"]]
        example_slides.append(slide)
    blocks["example"] = example_slides

    blocks["summary"] = [{
        "type": "summary",
        "title": copy_["sum_title"],
        "subtitle": "用自己的话说一遍",
        "bullets": summary[:4],
        "content": "",
        "notes": (
            "抽三名学生各说一句。"
            + (f" 课末回扣：{'；'.join(objectives[:2])}。" if objectives else "")
        ),
    }]

    answer_notes = "\n".join(
        f"{i+1}. {'（题库）' if ex.get('question_id') else ''}{ex.get('answer') or '看判断依据。'}"
        for i, ex in enumerate(exercises)
    )
    exercise_slide = {
        "type": "exercise",
        "title": copy_["ex_title"],
        "subtitle": copy_["ex_sub"],
        "bullets": [ex["question"] for ex in exercises],
        "answers": [ex.get("answer") or "" for ex in exercises],
        "content": "先独立完成，能说出“因为……”再对答案。",
        "notes": (
            "停课点：先收判断依据，再对答案。\n"
            + (answer_notes or "巡视时关注卡在概念判断上的学生。")
        ),
    }
    bank_ids = [ex["question_id"] for ex in exercises if ex.get("question_id")]
    if bank_ids:
        exercise_slide["bank_question_ids"] = bank_ids
    blocks["exercise"] = [exercise_slide]

    blocks["homework"] = [{
        "type": "homework",
        "title": "课后任务",
        "subtitle": "会说出理由，比只选对答案更重要",
        "bullets": [h["task"] for h in homework[:4]],
        "content": "",
        "notes": "停课点：下节课用 1 分钟交流作品。收作业时抽查“依据”一栏。",
    }]

    slides: list[dict] = []
    for name in profile["order"]:
        slides.extend(blocks.get(name) or [])
    for i, s in enumerate(slides, 1):
        s["index"] = i

    lesson = {
        "meta": {
            "title": topic,
            "subject": subject_name or "",
            "render_style": RenderStyle.html.value if is_web else RenderStyle.ppt.value,
            "duration": "45分钟",
            "lesson_type": lesson_type,
            "lesson_type_label": profile["label"],
            "lesson_grain": blueprint.get("lesson_grain") or "period",
            "unit_title": cw.title,
            "objectives": objectives[:4],
            "key_points": [p["name"] for p in points[:3]],
            "difficulties": [m for p in points for m in p.get("common_mistakes", [])][:3],
            "knowledge_points": points,
        },
        "slides": slides,
    }
    if lab:
        lesson["meta"]["lab"] = lab
    bank_used = [qid for s in slides for qid in (s.get("bank_question_ids") or [])]
    if bank_used:
        lesson["meta"]["bank_question_ids"] = bank_used
    intent = _teacher_intent(cw)
    if intent:
        await progress("intent")
        # 题库真题不允许被改写：先记下题面，改写后放回
        frozen = {
            i: {k: copy.deepcopy(s.get(k)) for k in ("bullets", "answers", "prompt", "solution", "notes")}
            for i, s in enumerate(slides) if s.get("bank_question_ids")
        }
        lesson = await _apply_teacher_intent(cfg, cw, lesson, intent)
        for i, saved in frozen.items():
            target = lesson["slides"][i]
            for k, v in saved.items():
                if v is None:
                    target.pop(k, None)
                else:
                    target[k] = v
    return normalize_lesson_chem(lesson)


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
