"""代理环境清理。

httpx（litellm 底层用的 HTTP 客户端）默认不支持 socks 代理，若系统设置了
``all_proxy=socks://...`` 之类的环境变量，litellm 在 ``import`` 时即会因
``Unknown scheme for proxy URL`` 崩溃。

LLM 调用应直连（相当于 NO_PROXY），因此这里在进程启动早期移除不被支持的
socks 代理变量。必须在 ``import litellm`` 之前执行。
"""
import os

_PROXY_VARS = (
    "all_proxy", "ALL_PROXY",
    "http_proxy", "HTTP_PROXY",
    "https_proxy", "HTTPS_PROXY",
)


def sanitize_proxy_env() -> None:
    for var in _PROXY_VARS:
        val = os.environ.get(var)
        if val and val.strip().lower().startswith("socks"):
            os.environ.pop(var, None)


# 模块被导入时立即执行
sanitize_proxy_env()
