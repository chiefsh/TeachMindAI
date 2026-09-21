"""作业 AI 题独立校验：结构检查 + 盲解对照，对不上的题直接丢弃。"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CHECK_PASSED = "passed"
CHECK_UNCHECKED = "unchecked"
CHECK_BANK = "bank"

SOLVE_TYPES = {
    "single_choice", "multi_choice", "true_false", "fill_blank", "calculation",
}
CHOICE_TYPES = {"single_choice", "multi_choice"}

_TRUE = {"对", "正确", "true", "t", "yes", "y", "1", "√", "是", "right"}
_FALSE = {"错", "错误", "false", "f", "no", "n", "0", "×", "x", "否", "wrong"}

_SOLVE_BATCH = 6


def _norm_text(s: str) -> str:
    return re.sub(r"[\s\$￥，,。．.、；;：:（）()【】\[\]\"'‘’“”]+", "", (s or "")).lower()


def _option_text(val: Any) -> str:
    if isinstance(val, dict):
        return str(val.get("text") or "").strip()
    return str(val or "").strip()


def normalize_options(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = str(k or "").strip().upper()
        key = re.sub(r"[^A-Z]", "", key)[:1]
        text = _option_text(v)
        if key and text:
            out[key] = text
    return out or None


def parse_choice_letters(raw: Any, keys: list[str]) -> list[str]:
    blob = raw if isinstance(raw, str) else (
        "".join(str(x) for x in raw) if isinstance(raw, (list, tuple)) else str(raw or "")
    )
    found: list[str] = []
    for ch in re.findall(r"[A-Za-z]", blob):
        letter = ch.upper()
        if letter in keys and letter not in found:
            found.append(letter)
    return found


def canonicalize_tf(raw: Any) -> str | None:
    s = _norm_text(str(raw or ""))
    if s in _TRUE:
        return "对"
    if s in _FALSE:
        return "错"
    return None


def _sympy_equal(a: str, b: str) -> bool:
    try:
        import sympy as sp
        ea = sp.sympify(a)
        eb = sp.sympify(b)
        if sp.simplify(ea - eb) == 0:
            return True
        fa = complex(ea.evalf())
        fb = complex(eb.evalf())
        return abs(fa - fb) < 1e-6
    except Exception:
        return False


def _blank_parts(raw: Any) -> list[str]:
    return sorted(
        p for p in (_norm_text(x) for x in re.split(r"[;；、,/|]", str(raw or ""))) if p
    )


def answers_match(qtype: str, claimed: Any, solved: Any, options: dict[str, str] | None = None) -> bool:
    """比较命题答案与独立求解结果。"""
    if qtype == "true_false":
        a, b = canonicalize_tf(claimed), canonicalize_tf(solved)
        return bool(a and b and a == b)
    if qtype in CHOICE_TYPES:
        keys = list((options or {}).keys())
        ca = parse_choice_letters(claimed, keys)
        cb = parse_choice_letters(solved, keys)
        return bool(ca) and sorted(ca) == sorted(cb)
    na, nb = _norm_text(str(claimed or "")), _norm_text(str(solved or ""))
    if not na or not nb:
        return False
    if na == nb:
        return True
    if qtype == "fill_blank":
        pa, pb = _blank_parts(claimed), _blank_parts(solved)
        return bool(pa) and pa == pb
    return _sympy_equal(str(claimed), str(solved)) or _sympy_equal(na, nb)


def structural_check(q: dict) -> tuple[bool, str]:
    """格式与选项一致性。通过时就地规范化 options/answer。"""
    content = str(q.get("content") or "").strip()
    if not content:
        return False, "空题干"
    qtype = str(q.get("type") or q.get("question_type") or "").strip()
    answer = q.get("answer")
    if answer is None or not str(answer).strip():
        if qtype == "essay":
            q["answer"] = ""
            return True, ""
        return False, "缺答案"

    if qtype in CHOICE_TYPES:
        options = normalize_options(q.get("options"))
        if not options or len(options) < 2:
            return False, "选项不足"
        texts = [t.strip() for t in options.values()]
        if any(not t for t in texts):
            return False, "空选项"
        if len(set(texts)) != len(texts):
            return False, "选项重复"
        keys = list(options.keys())
        letters = parse_choice_letters(answer, keys)
        if qtype == "single_choice":
            if len(letters) != 1:
                return False, "单选答案不是唯一选项"
        elif len(letters) < 1:
            return False, "多选答案无效"
        q["options"] = options
        q["answer"] = "".join(letters)
        return True, ""

    if qtype == "true_false":
        canon = canonicalize_tf(answer)
        if not canon:
            return False, "判断题答案无法识别"
        q["options"] = None
        q["answer"] = canon
        return True, ""

    q["answer"] = str(answer).strip()
    return True, ""


def _stem_block(i: int, q: dict) -> str:
    lines = [f"{i}. {q.get('content') or ''}"]
    options = q.get("options")
    if isinstance(options, dict):
        for k in sorted(options.keys()):
            lines.append(f"  {k}. {options[k]}")
    qtype = q.get("type") or q.get("question_type")
    hint = {
        "single_choice": "只输出正确选项字母，如 A",
        "multi_choice": "只输出全部正确选项字母，如 AC",
        "true_false": "只输出 对 或 错",
        "fill_blank": "只输出填空结果，多空用分号分隔",
        "calculation": "只输出最终结果（可含单位），不要步骤",
    }.get(str(qtype), "只输出最终答案")
    lines.append(f"  （{hint}）")
    return "\n".join(lines)


async def _solve_batch(cfg, items: list[dict]) -> list[str | None]:
    from app.services.ai_service import _call_llm, _parse_json_object, _resp_content

    numbered = "\n".join(_stem_block(i + 1, q) for i, q in enumerate(items))
    prompt = (
        "你是阅卷人。只根据题干和选项作答，不要使用题外知识编造条件，"
        "算不出就留空字符串。不要输出解析。\n"
        "只输出 JSON：{\"answers\":[{\"i\":1,\"answer\":\"...\"}]}\n\n"
        f"{numbered}"
    )
    try:
        resp = await _call_llm(
            cfg, [{"role": "user", "content": prompt}], max_tokens=1024,
        )
        obj = _parse_json_object(_resp_content(resp)) or {}
        rows = obj.get("answers") or []
    except Exception as e:  # noqa: BLE001
        logger.warning("独立求解失败：%s", e)
        return [None] * len(items)

    by_i: dict[int, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("i") or 0)
        except (TypeError, ValueError):
            continue
        ans = str(row.get("answer") or "").strip()
        if idx >= 1:
            by_i[idx] = ans
    return [by_i.get(i + 1) or None for i in range(len(items))]


async def filter_verified(cfg, items: list[dict]) -> tuple[list[dict], int]:
    """丢掉结构不合格或与独立求解不一致的题。求解器异常时保留并标 unchecked。"""
    if not items:
        return [], 0

    structurally_ok: list[dict] = []
    dropped = 0
    for q in items:
        if not isinstance(q, dict):
            dropped += 1
            continue
        ok, reason = structural_check(q)
        if not ok:
            dropped += 1
            logger.info("丢弃不合格 AI 题：%s | %s", reason, str(q.get("content") or "")[:80])
            continue
        structurally_ok.append(q)

    to_solve: list[tuple[int, dict]] = []
    for i, q in enumerate(structurally_ok):
        qtype = str(q.get("type") or q.get("question_type") or "")
        if qtype in SOLVE_TYPES:
            to_solve.append((i, q))
        else:
            q["check_status"] = CHECK_UNCHECKED

    if not cfg:
        for _, q in to_solve:
            q["check_status"] = CHECK_UNCHECKED
        return structurally_ok, dropped

    solved_at: dict[int, str | None] = {}
    solve_failed = False
    for start in range(0, len(to_solve), _SOLVE_BATCH):
        chunk = to_solve[start:start + _SOLVE_BATCH]
        answers = await _solve_batch(cfg, [q for _, q in chunk])
        if all(a is None for a in answers):
            solve_failed = True
        for (idx, _), ans in zip(chunk, answers):
            solved_at[idx] = ans

    kept: list[dict] = []
    for i, q in enumerate(structurally_ok):
        qtype = str(q.get("type") or q.get("question_type") or "")
        if qtype not in SOLVE_TYPES:
            kept.append(q)
            continue
        if solve_failed and solved_at.get(i) is None:
            q["check_status"] = CHECK_UNCHECKED
            kept.append(q)
            continue
        solved = solved_at.get(i)
        if not solved or not answers_match(qtype, q.get("answer"), solved, q.get("options")):
            dropped += 1
            logger.info(
                "丢弃答案不一致的 AI 题：claimed=%s solved=%s | %s",
                q.get("answer"), solved, str(q.get("content") or "")[:80],
            )
            continue
        q["check_status"] = CHECK_PASSED
        kept.append(q)
    return kept, dropped
