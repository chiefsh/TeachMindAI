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
                chapters_result = await db.execute(
                    select(TextbookChapter).where(TextbookChapter.textbook_id == cw.textbook_id).limit(40)
                )
                chapters = chapters_result.scalars().all()
                chapter_content = "\n\n".join(
                    f"## {c.title}\n{c.content or ''}" for c in chapters
                )

                # 可用课本插图清单（供模型引用）
                from app.models.textbook import TextbookImage
                img_result = await db.execute(
                    select(TextbookImage)
                    .where(TextbookImage.textbook_id == cw.textbook_id)
                    .order_by(TextbookImage.sort_order)
                    .limit(40)
                )
                imgs = img_result.scalars().all()
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


async def _generate_lesson_content(
    cfg, cw, chapter_content: str, image_catalog: str,
    subject_name: str = "", subject_block: str = "", subject_interactive: str = "",
) -> dict:
    """调用 LLM 生成一节完整的、可直接讲授的课件内容。"""
    interactive_hint = ""
    if cw.is_interactive:
        from app.services.courseware_components import build_interactive_prompt
        interactive_hint = build_interactive_prompt(subject_interactive)

    image_hint = ""
    if image_catalog:
        image_hint = (
            "\n\n【可引用的课本插图】（如某页内容需要配图，把对应图的数字 id 放进该幻灯片的 images 数组）：\n"
            + image_catalog
        )

    subject_hint = ""
    if subject_block:
        subject_hint = (
            f"\n\n【本节课所属科目：{subject_name or '通用'}，请严格结合该科目特点设计】\n{subject_block}"
        )

    system_prompt = f"""你是一位资深的一线教师和课件设计专家。请基于课本内容，设计一节【完整的、可直接照着讲授的】课堂教学课件（类似 PPT），时长约 40-45 分钟。{subject_hint}

要求：
1. 内容必须完整、具体、可直接讲课，而不是大纲。每页要有充实的讲解正文(content)和教师讲稿(notes，指导老师这一页怎么讲、怎么提问、预计用时)。
2. 结构遵循真实课堂流程，依次包含这些类型的幻灯片(type)：
   - title：封面（课题、学科年级）
   - objectives：教学目标
   - intro：情境导入（激发兴趣）
   - content：新知讲解（可多页，每页聚焦一个知识点，content 用 markdown，配 bullets 要点）
   - example：例题精讲（含解题步骤）
   - activity：课堂活动/小组讨论
   - interactive：互动环节（随堂练习/思考题）
   - summary：课堂小结（板书式知识结构）
   - homework：布置作业
3. 每页字段：index, type, title, subtitle(可选), bullets(要点数组), content(markdown 详细讲解), notes(教师讲稿), html(可选,互动动画), images(可选,引用的课本插图 id 数组)。
4. 全部用中文。只输出 JSON，不要任何额外解释。

输出 JSON 结构：
{{
  "meta": {{
    "title": "课题",
    "duration": "45分钟",
    "objectives": ["目标1", "目标2"],
    "key_points": ["重点1"],
    "difficulties": ["难点1"]
  }},
  "slides": [
    {{"index": 1, "type": "title", "title": "...", "subtitle": "...", "bullets": [], "content": "", "notes": ""}}
  ]
}}{interactive_hint}"""

    user_prompt = f"课件课题：{cw.title}\n\n课本内容：\n{chapter_content[:8000]}"
    if cw.custom_prompt:
        user_prompt += f"\n\n教师额外要求（请重点体现）：{cw.custom_prompt}"
    user_prompt += image_hint

    resp = await _call_llm(cfg, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], max_tokens=max(cfg.max_tokens or 0, 8000))
    raw = resp.choices[0].message.content
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        if not data.get("slides"):
            raise ValueError("no slides")
        return data
    except Exception:
        return {
            "meta": {"title": cw.title},
            "slides": [{"index": 1, "type": "content", "title": cw.title, "content": raw, "bullets": [], "notes": ""}],
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
