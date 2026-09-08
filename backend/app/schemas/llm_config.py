from pydantic import BaseModel


class LLMConfigCreate(BaseModel):
    provider: str
    model_name: str
    display_name: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    is_default: bool = False


class LLMConfigUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class LLMConfigOut(BaseModel):
    id: int
    provider: str
    model_name: str
    display_name: str
    base_url: str | None
    temperature: float
    max_tokens: int
    is_default: bool
    is_active: bool
    model_config = {"from_attributes": True}


class EmbeddingConfigOut(BaseModel):
    enabled: bool
    model: str
    base_url: str | None = None
    dim: int = 1024
    use_llm_gateway: bool = False
    has_api_key: bool = False
    source: str = "none"


class EmbeddingConfigUpdate(BaseModel):
    enabled: bool = True
    model: str = ""
    base_url: str | None = None
    api_key: str | None = None
    dim: int = 1024
    use_llm_gateway: bool = False
