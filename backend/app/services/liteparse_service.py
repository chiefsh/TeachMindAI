"""LiteParse 封装：基于 PDFium 的 PDF 空间文字解析 + 选择性 OCR（中文）。

替代原先「PyMuPDF get_text + pytesseract 整页 OCR」的文字提取方案。
对外提供 parse_pdf()，返回逐页文本与整篇文本；OCR 失败时自动降级为无 OCR 解析。
"""
import logging
import os
import tempfile
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# Debian/Ubuntu 安装 tesseract-ocr-chi-sim 后 tessdata 的常见位置
_TESSDATA_CANDIDATES = [
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tesseract-ocr/tessdata",
    "/usr/share/tessdata",
    "/usr/local/share/tessdata",
]


def _has_traineddata_files(path: str) -> bool:
    try:
        return any(name.endswith(".traineddata") for name in os.listdir(path))
    except OSError:
        return False


def _normalize_tessdata_dir(path: str) -> str | None:
    """归一化为包含 *.traineddata 的目录。

    TESSDATA_PREFIX 有时指向 tessdata 目录本身，有时指向其父目录，需兼容两种写法。
    """
    path = (path or "").strip().rstrip("/")
    if not path or not os.path.isdir(path):
        return None
    if _has_traineddata_files(path):
        return path
    child = os.path.join(path, "tessdata")
    if os.path.isdir(child) and _has_traineddata_files(child):
        return child
    return None


def _detect_tessdata_path() -> str | None:
    configured = (getattr(settings, "OCR_TESSDATA_PATH", "") or "").strip()
    if configured:
        normalized = _normalize_tessdata_dir(configured)
        if normalized:
            return normalized
    env = os.environ.get("TESSDATA_PREFIX", "").strip()
    if env:
        normalized = _normalize_tessdata_dir(env)
        if normalized:
            return normalized
    for p in _TESSDATA_CANDIDATES:
        normalized = _normalize_tessdata_dir(p)
        if normalized:
            return normalized
    return None


def _available_languages(tessdata_dir: str) -> set[str]:
    try:
        return {
            name[:-len(".traineddata")]
            for name in os.listdir(tessdata_dir)
            if name.endswith(".traineddata")
        }
    except OSError:
        return set()


def _resolve_ocr_language(tessdata_dir: str | None) -> str:
    """解析 OCR 语言，只使用本地 tessdata 中实际存在的语言包。

    LiteParse 在找不到本地语言包时会尝试从 GitHub 下载；若配置为 chi_sim+eng，
    会错误请求 chi_sim+eng.traineddata（不存在，404）。因此：
    - 有本地 tessdata 时：仅拼接本地已有的语言（如 chi_sim+eng）
    - 无本地 tessdata 时：退化为单一语言 chi_sim，避免组合语言下载 404
    """
    configured = (getattr(settings, "OCR_LANGUAGE", "chi_sim") or "chi_sim").strip()
    requested = [p.strip() for p in configured.split("+") if p.strip()]
    if not requested:
        requested = ["chi_sim"]

    if tessdata_dir:
        available = _available_languages(tessdata_dir)
        found = [lang for lang in requested if lang in available]
        if found:
            return "+".join(found)
        if "chi_sim" in available:
            logger.warning(
                "OCR 配置语言 %s 在 %s 中不可用，回退为 chi_sim",
                configured, tessdata_dir,
            )
            return "chi_sim"
        if "eng" in available:
            logger.warning("OCR 配置语言 %s 不可用，回退为 eng", configured)
            return "eng"
        logger.warning("tessdata 目录 %s 中未找到可用语言包", tessdata_dir)

    # 无本地包：只用单一语言，避免 LiteParse 下载 chi_sim+eng.traineddata 404
    if len(requested) == 1:
        return requested[0]
    if "chi_sim" in requested:
        return "chi_sim"
    return requested[0]


def _apply_tessdata_env(tessdata_dir: str | None) -> None:
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir


@lru_cache(maxsize=4)
def _make_parser(ocr_enabled: bool = True):
    """构造并缓存 LiteParse 实例。"""
    from liteparse import LiteParse

    tessdata = _detect_tessdata_path()
    _apply_tessdata_env(tessdata)

    ocr_language = _resolve_ocr_language(tessdata) if ocr_enabled else "eng"
    if ocr_enabled:
        if tessdata:
            logger.info("LiteParse OCR: tessdata=%s language=%s", tessdata, ocr_language)
        else:
            logger.warning(
                "LiteParse OCR: 未检测到本地 tessdata，将尝试在线下载语言包 %s",
                ocr_language,
            )

    kwargs: dict = {
        "ocr_enabled": ocr_enabled,
        "ocr_language": ocr_language,
        "output_format": "markdown",
        "quiet": True,
    }
    if tessdata:
        kwargs["tessdata_path"] = tessdata
    return LiteParse(**kwargs)


def _page_to_text(page) -> str:
    """从单页对象中尽量稳健地取出文本（兼容不同字段命名）。"""
    for attr in ("markdown", "text", "content"):
        v = getattr(page, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    items = getattr(page, "text_items", None) or getattr(page, "items", None) or []
    parts: list[str] = []
    for it in items:
        for attr in ("text", "content", "value"):
            t = getattr(it, attr, None)
            if isinstance(t, str) and t:
                parts.append(t)
                break
    return "\n".join(parts).strip()


def _do_parse(data: bytes, ocr_enabled: bool) -> dict:
    parser = _make_parser(ocr_enabled=ocr_enabled)
    result = parser.parse(data)

    pages: list[dict] = []
    raw_pages = getattr(result, "pages", None) or []
    for idx, p in enumerate(raw_pages):
        num = getattr(p, "page_num", None)
        if not isinstance(num, int):
            num = idx + 1
        pages.append({"page_num": num, "text": _page_to_text(p)})

    full_text = "\n".join(pg["text"] for pg in pages if pg["text"])
    markdown = (getattr(result, "text", "") or "").strip() or full_text
    total = len(pages) or int(getattr(result, "num_pages", 0) or 0)
    return {
        "total_pages": total,
        "pages": pages,
        "full_text": full_text,
        "markdown": markdown,
    }


def parse_pdf(data: bytes) -> dict:
    """解析 PDF 字节，返回结构化结果。

    OCR 失败时自动降级为无 OCR 模式（仍可提取 PDF 文字层；纯扫描件可能无文字）。
    """
    try:
        return _do_parse(data, ocr_enabled=True)
    except Exception as e:
        err = str(e)
        if "ocr" in err.lower() or "tessdata" in err.lower():
            logger.warning("LiteParse OCR 失败，降级为无 OCR 解析: %s", e)
            return _do_parse(data, ocr_enabled=False)
        raise


def screenshot_pdf(data: bytes, page_numbers: list[int] | None = None) -> list[tuple[int, bytes]]:
    """渲染 PDF 指定页为 PNG，返回 [(page_num, png_bytes), ...]。

    page_numbers 为空表示全部页。screenshot 走临时文件，兼容仅接受路径的实现。
    """
    parser = _make_parser(ocr_enabled=False)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(data)
            tmp_path = tf.name
        kwargs = {}
        if page_numbers:
            kwargs["page_numbers"] = page_numbers
        shots = parser.screenshot(tmp_path, **kwargs)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    out: list[tuple[int, bytes]] = []
    for idx, s in enumerate(shots or []):
        num = getattr(s, "page_num", None)
        if not isinstance(num, int):
            num = (page_numbers[idx] if page_numbers and idx < len(page_numbers) else idx + 1)
        img = (getattr(s, "image_bytes", None) or getattr(s, "bytes", None)
               or getattr(s, "data", None) or getattr(s, "png", None))
        if img:
            out.append((num, img))
    return out
