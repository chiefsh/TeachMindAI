"""题库配图：入库、裁切、签名访问。"""
from __future__ import annotations

import hashlib
import hmac
import io
import time
import uuid
from urllib.parse import quote

from app.core.config import settings
from app.core.minio_client import upload_file, get_file_bytes

_ASSET_TTL = 6 * 3600
_MIN_CROP = 40


def store_question_image(teacher_id: int, data: bytes, ext: str = "jpg", content_type: str = "image/jpeg") -> str:
    ext = (ext or "jpg").lstrip(".").lower()
    if ext == "jpeg":
        ext = "jpg"
    object_name = f"{teacher_id}/qimg/{uuid.uuid4().hex}.{ext}"
    upload_file(settings.MINIO_BUCKET_QUESTIONS, object_name, data, content_type)
    return object_name


def is_safe_object_name(object_name: str, teacher_id: int) -> bool:
    if not object_name or ".." in object_name or object_name.startswith("/"):
        return False
    return object_name.startswith(f"{int(teacher_id)}/")


def _sign(teacher_id: int, object_name: str, exp: int) -> str:
    msg = f"{int(teacher_id)}\n{object_name}\n{int(exp)}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def question_asset_url(object_name: str, teacher_id: int, ttl: int = _ASSET_TTL) -> str:
    exp = int(time.time()) + ttl
    sig = _sign(teacher_id, object_name, exp)
    return f"/api/v1/questions/assets/{quote(object_name, safe='/')}?exp={exp}&sig={sig}"


def verify_asset_sig(object_name: str, teacher_id: int, exp: int | str | None, sig: str | None) -> bool:
    try:
        exp_i = int(exp or 0)
    except (TypeError, ValueError):
        return False
    if not sig or exp_i < int(time.time()):
        return False
    if not is_safe_object_name(object_name, teacher_id):
        return False
    expect = _sign(teacher_id, object_name, exp_i)
    return hmac.compare_digest(expect, sig)


def public_images(raw, teacher_id: int) -> dict | None:
    """把库里的 object_name 转成可给 <img> 用的签名 URL。"""
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    stem = [x for x in (raw.get("stem") or []) if isinstance(x, str) and x]
    if stem:
        out["stem"] = [question_asset_url(x, teacher_id) for x in stem]
    opts = raw.get("options") if isinstance(raw.get("options"), dict) else {}
    mapped = {
        str(k): question_asset_url(v, teacher_id)
        for k, v in opts.items()
        if isinstance(v, str) and v
    }
    if mapped:
        out["options"] = mapped
    return out or None


def guess_content_type(object_name: str) -> str:
    ext = object_name.rsplit(".", 1)[-1].lower() if "." in object_name else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "application/octet-stream")


def read_question_asset(object_name: str) -> bytes:
    return get_file_bytes(settings.MINIO_BUCKET_QUESTIONS, object_name)


def _normalize_xywh(bbox) -> tuple[float, float, float, float] | None:
    """把模型给的框统一成 0~1 的 x,y,w,h。兼容 [x,y,w,h] 与 [x1,y1,x2,y2]。"""
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        a, b, c, d = [float(v) for v in bbox[:4]]
    except (TypeError, ValueError):
        return None
    # 明显是像素坐标时先归一化不了，留给调用方按图尺寸再除；这里只处理 0~1
    if max(a, b, c, d) > 1.5:
        return None
    x, y, w, h = a, b, c, d
    # 第三、四个数更像右下角：按 xywh 会超出画布
    if 0 <= a <= 1 and 0 <= b <= 1 and c > a and d > b and c <= 1.05 and d <= 1.05:
        if a + c > 1.02 or b + d > 1.02:
            x, y, w, h = a, b, c - a, d - b
    return x, y, w, h


def is_full_page_bbox(bbox, min_area: float = 0.38) -> bool:
    """整页/大半页框，不能当题干或单个选项图。"""
    xywh = _normalize_xywh(bbox)
    if not xywh:
        return False
    x, y, w, h = xywh
    return (w * h) >= min_area or (w >= 0.82 and h >= 0.45)


def crop_norm_bbox(image_bytes: bytes, bbox, *, kind: str = "option") -> bytes | None:
    """按 0~1 框裁切。选项框会多留右边和下边，避免图+说明被切掉。"""
    xywh = _normalize_xywh(bbox)
    if not xywh:
        return None
    x, y, w, h = xywh
    if w <= 0.02 or h <= 0.02:
        return None
    # 整页框不当选项/题干局部图
    area_limit = 0.36 if kind == "stem" else 0.55
    if w * h >= area_limit or w > 0.92 or h > 0.92:
        return None
    if x < -0.08 or y < -0.08 or x + w > 1.15 or y + h > 1.15:
        return None
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    W, H = im.size
    # 相对框本身外扩：右边/下边多留，吃进被模型切掉的图边和说明文字
    pad_l = max(0.012, w * 0.10)
    pad_t = max(0.012, h * 0.10)
    pad_r = max(0.045, w * 0.32)
    pad_b = max(0.025, h * 0.18)
    if kind == "stem":
        pad_l = pad_t = pad_r = pad_b = max(0.015, min(w, h) * 0.08)
    box = (
        max(0, int((x - pad_l) * W)),
        max(0, int((y - pad_t) * H)),
        min(W, int((x + w + pad_r) * W)),
        min(H, int((y + h + pad_b) * H)),
    )
    if box[2] - box[0] < _MIN_CROP or box[3] - box[1] < _MIN_CROP:
        return None
    out = io.BytesIO()
    im.crop(box).save(out, format="JPEG", quality=88)
    return out.getvalue()


def refine_option_box(image_bytes: bytes, bbox) -> tuple[int, int, int, int] | None:
    """以模型框为种子，向右略扩以补全配图，再去掉空白边；竖直方向几乎不扩，避免切到下一选项。"""
    xywh = _normalize_xywh(bbox)
    if not xywh or is_full_page_bbox(bbox):
        return None
    x, y, w, h = xywh
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:
        return None
    W, H = im.size
    x1, y1 = int(x * W), int(y * H)
    x2, y2 = int((x + w) * W), int((y + h) * H)
    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
    pad_r = min(40, max(12, int(bw * 0.42)))
    pad_l = min(14, max(4, int(bw * 0.10)))
    pad_y = min(10, max(4, int(bh * 0.08)))
    x1, y1 = max(0, x1 - pad_l), max(0, y1 - pad_y)
    x2, y2 = min(W, x2 + pad_r), min(H, y2 + pad_y)
    pix = im.load()

    def row_dense(yy: int) -> bool:
        n = max(1, x2 - x1)
        dark = sum(1 for xx in range(x1, x2) if pix[xx, yy] < 248)
        return dark > max(3, int(n * 0.035))

    def col_dense(xx: int) -> bool:
        n = max(1, y2 - y1)
        dark = sum(1 for yy in range(y1, y2) if pix[xx, yy] < 248)
        return dark > max(3, int(n * 0.035))

    while y1 < y2 - 12 and not row_dense(y1):
        y1 += 1
    while y2 > y1 + 12 and not row_dense(y2 - 1):
        y2 -= 1
    while x1 < x2 - 12 and not col_dense(x1):
        x1 += 1
    while x2 > x1 + 12 and not col_dense(x2 - 1):
        x2 -= 1
    if x2 - x1 < 24 or y2 - y1 < 24:
        return None
    return (x1, y1, x2, y2)


def crop_pixel_box(image_bytes: bytes, box: tuple[int, int, int, int], pad: int = 4) -> bytes | None:
    """按像素框裁切，只留很小边距。"""
    if not box or len(box) < 4:
        return None
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    W, H = im.size
    x1, y1, x2, y2 = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(W, x2 + pad), min(H, y2 + pad)
    if x2 - x1 < _MIN_CROP or y2 - y1 < _MIN_CROP:
        return None
    out = io.BytesIO()
    im.crop((x1, y1, x2, y2)).save(out, format="JPEG", quality=90)
    return out.getvalue()


def _sort_option_figures(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """阅读顺序：先从上到下分排，再从左到右（2x2 则为 A B / C D）。"""
    if len(boxes) <= 1:
        return list(boxes)
    if len(boxes) != 4:
        return sorted(boxes, key=lambda b: ((b[1] + b[3]) / 2, b[0]))
    cys = sorted((b[1] + b[3]) / 2 for b in boxes)
    mid_y = (cys[1] + cys[2]) / 2
    top = [b for b in boxes if (b[1] + b[3]) / 2 <= mid_y]
    bot = [b for b in boxes if (b[1] + b[3]) / 2 > mid_y]
    top.sort(key=lambda b: b[0])
    bot.sort(key=lambda b: b[0])
    return top + bot


def assign_figures_to_questions(
    boxes: list[tuple[int, int, int, int]],
    n_questions: int,
) -> list[list[tuple[int, int, int, int]]]:
    """把检测到的配图按题目分组，每题最多 4 张（A–D）。"""
    n_questions = max(1, n_questions)
    if not boxes:
        return [[] for _ in range(n_questions)]
    ordered = sorted(boxes, key=lambda b: ((b[1] + b[3]) / 2, b[0]))
    if n_questions == 1 or len(ordered) <= 4:
        groups = [ordered]
    elif len(ordered) >= 4 * n_questions:
        groups = [ordered[i * 4:(i + 1) * 4] for i in range(n_questions)]
    else:
        # 按 y 最大间隙切开
        cys = [(b[1] + b[3]) / 2 for b in ordered]
        gaps = [(cys[i + 1] - cys[i], i) for i in range(len(cys) - 1)]
        gaps.sort(reverse=True)
        cuts = sorted(g[1] + 1 for g in gaps[: n_questions - 1])
        groups, start = [], 0
        for cut in cuts + [len(ordered)]:
            groups.append(ordered[start:cut])
            start = cut
        while len(groups) < n_questions:
            groups.append([])
    return [_sort_option_figures(g[:4]) for g in groups[:n_questions]]


def detect_option_figures(image_bytes: bytes) -> list[tuple[int, int, int, int]]:
    """在整页截图里找出选项配图的像素框（白底上的照片块），阅读序。"""
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:
        return []
    W, H = im.size
    if W < 80 or H < 80:
        return []
    pix = im.load()
    bs = max(10, min(W, H) // 48)
    gh, gw = H // bs, W // bs
    high = [[False] * gw for _ in range(gh)]
    for i in range(gh):
        for j in range(gw):
            vals = [
                pix[x, y]
                for y in range(i * bs, min(H, (i + 1) * bs))
                for x in range(j * bs, min(W, (j + 1) * bs))
            ]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            # 照片块方差大；纯白/细字行通常过不了
            high[i][j] = var > 220 and mean < 248

    # 不整页膨胀：膨胀会把汉字行和配图粘成一块，最后 0 张。
    seen = [[False] * gw for _ in range(gh)]
    comps: list[tuple[int, int, int, int, int]] = []
    for i in range(gh):
        for j in range(gw):
            if not high[i][j] or seen[i][j]:
                continue
            stack = [(i, j)]
            seen[i][j] = True
            cells = []
            while stack:
                ci, cj = stack.pop()
                cells.append((ci, cj))
                for di, dj in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                    ni, nj = ci + di, cj + dj
                    if 0 <= ni < gh and 0 <= nj < gw and high[ni][nj] and not seen[ni][nj]:
                        seen[ni][nj] = True
                        stack.append((ni, nj))
            is_ = [c[0] for c in cells]
            js_ = [c[1] for c in cells]
            i0, i1, j0, j1 = min(is_), max(is_), min(js_), max(js_)
            bw, bh = j1 - j0 + 1, i1 - i0 + 1
            # 只要中等大小的近似方块，丢掉整行文字
            if bw < 4 or bh < 4 or bw > 16 or bh > 16:
                continue
            fill = len(cells) / (bw * bh)
            if fill < 0.28:
                continue
            aspect = bw / bh
            if aspect < 0.45 or aspect > 2.4:
                continue
            pad = 1
            x1 = max(0, (j0 - pad) * bs)
            y1 = max(0, (i0 - pad) * bs)
            x2 = min(W, (j1 + 1 + pad) * bs)
            y2 = min(H, (i1 + 1 + pad) * bs)
            comps.append((x1, y1, x2, y2, bw * bh))

    comps.sort(key=lambda c: -c[4])
    kept: list[tuple[int, int, int, int]] = []
    for x1, y1, x2, y2, _ in comps:
        if any(x1 >= kx - bs and y1 >= ky - bs and x2 <= kw + bs and y2 <= kh + bs for kx, ky, kw, kh in kept):
            continue
        kept.append((x1, y1, x2, y2))
    if not kept:
        return []
    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in kept]
    med = sorted(areas)[len(areas) // 2]
    kept = [b for b, a in zip(kept, areas) if 0.32 * med <= a <= 3.2 * med]
    return kept


def image_looks_useful(data: bytes, min_side: int = 56) -> bool:
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(data))
        w, h = im.size
    except Exception:
        return False
    return w >= min_side and h >= min_side
