from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import httpx

from app.core.database import get_db
from app.core.security import encrypt_api_key, decrypt_api_key
from app.models.teacher import Teacher
from app.models.llm_config import LLMConfig
from app.models.education import Subject
from app.models.subject_prompt import SubjectPromptTemplate
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigOut
from app.api.deps import get_current_teacher

router = APIRouter(prefix="/settings", tags=["系统设置"])

# 支持的 LLM 供应商预设（含默认接入地址，用于动态拉取模型列表）
PROVIDERS = [
    {"provider": "openai",    "label": "OpenAI",      "base_url": "https://api.openai.com/v1",                        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
    {"provider": "anthropic", "label": "Anthropic",   "base_url": "https://api.anthropic.com/v1",                     "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]},
    {"provider": "qwen",      "label": "通义千问",     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-max", "qwen-plus", "qwen-turbo"]},
    {"provider": "wenxin",    "label": "文心一言",     "base_url": "",                                                 "models": ["ernie-4.0-8k", "ernie-3.5-8k"]},
    {"provider": "deepseek",  "label": "DeepSeek",    "base_url": "https://api.deepseek.com/v1",                      "models": ["deepseek-chat", "deepseek-coder"]},
    {"provider": "ollama",    "label": "Ollama (本地)", "base_url": "http://localhost:11434/v1",                       "models": ["llama3", "qwen2", "mistral"]},
    {"provider": "zhipu",     "label": "智谱清言",     "base_url": "https://open.bigmodel.cn/api/paas/v4",            "models": ["glm-4", "glm-4-flash"]},
]


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None


@router.get("/providers")
async def get_providers():
    """获取支持的 LLM 供应商列表"""
    return PROVIDERS


@router.post("/fetch-models")
async def fetch_models(data: FetchModelsRequest, teacher: Teacher = Depends(get_current_teacher)):
    """根据供应商动态获取可用模型列表。
    优先调用供应商的 OpenAI 兼容 /models 接口；失败则回退到预设列表。
    """
    preset = next((p for p in PROVIDERS if p["provider"] == data.provider), None)
    fallback = preset["models"] if preset else []
    base_url = (data.base_url or (preset["base_url"] if preset else "")).rstrip("/")

    # 没有 base_url 或 api_key 时直接返回预设
    if not base_url or not data.api_key:
        return {"models": fallback, "source": "preset"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {data.api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            models = [m["id"] for m in payload.get("data", []) if m.get("id")]
            if models:
                return {"models": sorted(models), "source": "api"}
            return {"models": fallback, "source": "preset"}
    except Exception as e:
        return {"models": fallback, "source": "preset", "error": str(e)}


@router.get("/llm-configs", response_model=list[LLMConfigOut])
async def list_llm_configs(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LLMConfig).where(LLMConfig.teacher_id == teacher.id).order_by(LLMConfig.created_at)
    )
    return result.scalars().all()


@router.post("/llm-configs", response_model=LLMConfigOut, status_code=201)
async def create_llm_config(
    data: LLMConfigCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    if data.is_default:
        # 取消其他默认
        result = await db.execute(
            select(LLMConfig).where(LLMConfig.teacher_id == teacher.id, LLMConfig.is_default == True)
        )
        for c in result.scalars().all():
            c.is_default = False

    cfg = LLMConfig(
        teacher_id=teacher.id,
        provider=data.provider,
        model_name=data.model_name,
        display_name=data.display_name,
        api_key_encrypted=encrypt_api_key(data.api_key) if data.api_key else None,
        base_url=data.base_url,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        is_default=data.is_default,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.patch("/llm-configs/{cfg_id}", response_model=LLMConfigOut)
async def update_llm_config(
    cfg_id: int,
    data: LLMConfigUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_or_404(cfg_id, teacher.id, db)

    if data.is_default:
        result = await db.execute(
            select(LLMConfig).where(LLMConfig.teacher_id == teacher.id, LLMConfig.is_default == True)
        )
        for c in result.scalars().all():
            c.is_default = False

    if data.display_name is not None:
        cfg.display_name = data.display_name
    if data.api_key is not None:
        cfg.api_key_encrypted = encrypt_api_key(data.api_key)
    if data.base_url is not None:
        cfg.base_url = data.base_url
    if data.temperature is not None:
        cfg.temperature = data.temperature
    if data.max_tokens is not None:
        cfg.max_tokens = data.max_tokens
    if data.is_default is not None:
        cfg.is_default = data.is_default
    if data.is_active is not None:
        cfg.is_active = data.is_active

    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.delete("/llm-configs/{cfg_id}", status_code=204)
async def delete_llm_config(
    cfg_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_or_404(cfg_id, teacher.id, db)
    await db.delete(cfg)


@router.post("/llm-configs/{cfg_id}/test")
async def test_llm_config(
    cfg_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """测试 LLM 配置是否可用"""
    cfg = await _get_or_404(cfg_id, teacher.id, db)
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    try:
        from app.core.proxy import sanitize_proxy_env
        sanitize_proxy_env()
        import litellm
        from app.services.ai_service import build_litellm_kwargs
        resp = await litellm.acompletion(
            messages=[{"role": "user", "content": "你好，请回复「测试成功」"}],
            max_tokens=20,
            **build_litellm_kwargs(cfg, api_key),
        )
        return {"success": True, "reply": resp.choices[0].message.content}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _get_or_404(cfg_id: int, teacher_id: int, db: AsyncSession) -> LLMConfig:
    result = await db.execute(
        select(LLMConfig).where(LLMConfig.id == cfg_id, LLMConfig.teacher_id == teacher_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    return cfg


# ─── 科目课件提示词 ────────────────────────────────────────────────
class SubjectPromptOut(BaseModel):
    subject_name: str
    prompt: str
    interactive_guidance: str | None = None
    is_custom: bool          # 是否为教师个性化覆盖（false 表示用的是系统默认）


class SubjectPromptUpdate(BaseModel):
    prompt: str
    interactive_guidance: str | None = None


async def _load_prompt_row(db, subject_name, teacher_id):
    res = await db.execute(
        select(SubjectPromptTemplate).where(
            SubjectPromptTemplate.subject_name == subject_name,
            SubjectPromptTemplate.teacher_id == teacher_id if teacher_id is not None
            else SubjectPromptTemplate.teacher_id.is_(None),
        )
    )
    return res.scalar_one_or_none()


@router.get("/subject-prompts", response_model=list[SubjectPromptOut])
async def list_subject_prompts(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """列出各科目的有效提示词（教师覆盖优先，否则系统默认）。"""
    # 全部去重的科目名（跨学段同名只出现一次）
    names = (await db.execute(select(Subject.name).distinct())).scalars().all()

    # 一次性取出系统默认 + 教师覆盖
    rows = (await db.execute(
        select(SubjectPromptTemplate).where(
            (SubjectPromptTemplate.teacher_id == teacher.id)
            | (SubjectPromptTemplate.teacher_id.is_(None))
        )
    )).scalars().all()
    sys_map = {r.subject_name: r for r in rows if r.teacher_id is None}
    own_map = {r.subject_name: r for r in rows if r.teacher_id == teacher.id}

    out = []
    for name in sorted(set(names)):
        own = own_map.get(name)
        base = sys_map.get(name)
        eff = own or base
        if not eff:
            continue
        out.append(SubjectPromptOut(
            subject_name=name,
            prompt=eff.prompt,
            interactive_guidance=eff.interactive_guidance,
            is_custom=own is not None,
        ))
    return out


@router.put("/subject-prompts/{subject_name}", response_model=SubjectPromptOut)
async def upsert_subject_prompt(
    subject_name: str,
    data: SubjectPromptUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """新增或更新教师对某科目的个性化提示词。"""
    row = await _load_prompt_row(db, subject_name, teacher.id)
    if row:
        row.prompt = data.prompt
        row.interactive_guidance = data.interactive_guidance
        row.is_active = True
    else:
        row = SubjectPromptTemplate(
            teacher_id=teacher.id,
            subject_name=subject_name,
            prompt=data.prompt,
            interactive_guidance=data.interactive_guidance,
        )
        db.add(row)
    await db.flush()
    await db.refresh(row)
    return SubjectPromptOut(
        subject_name=row.subject_name,
        prompt=row.prompt,
        interactive_guidance=row.interactive_guidance,
        is_custom=True,
    )


@router.delete("/subject-prompts/{subject_name}", response_model=SubjectPromptOut)
async def reset_subject_prompt(
    subject_name: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """删除教师覆盖，恢复为系统默认提示词。"""
    own = await _load_prompt_row(db, subject_name, teacher.id)
    if own:
        await db.delete(own)
        await db.flush()
    base = await _load_prompt_row(db, subject_name, None)
    if not base:
        raise HTTPException(status_code=404, detail="该科目没有默认提示词")
    return SubjectPromptOut(
        subject_name=base.subject_name,
        prompt=base.prompt,
        interactive_guidance=base.interactive_guidance,
        is_custom=False,
    )
