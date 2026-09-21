"""把直写的化学式/单位改成课堂规范：元素符号、下标、m/s²、v₀。"""
from __future__ import annotations

import re

ELEMENTS = [
    "He", "Li", "Be", "Ne", "Na", "Mg", "Al", "Si", "Cl", "Ar", "Ca", "Sc", "Ti", "Cr", "Mn", "Fe",
    "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Zr", "Nb", "Mo", "Ag", "Cd",
    "In", "Sn", "Sb", "Te", "Xe", "Cs", "Ba", "La", "Hf", "Ta", "Pt", "Au", "Hg", "Pb", "Bi", "Rn",
    "Co", "No",
    "H", "B", "C", "N", "O", "F", "P", "S", "K", "V", "Y", "I", "W", "U",
]
ELEMENT_SET = set(ELEMENTS)
TWO_LETTER = {e for e in ELEMENTS if len(e) == 2}
# 单元素分子：不要把 b2、c2、s2、m/s2 当成化学式
DIATOMIC = {"H2", "O2", "N2", "F2", "I2", "O3", "P4", "S8", "C60"}

_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUP = str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")
_UNSUB = {v: k for k, v in zip("0123456789", "₀₁₂₃₄₅₆₇₈₉")}
_OPS = {"+", "·", "•", "＝", "=", "→", "⇌", "↔"}


def _is_digit(ch: str) -> bool:
    return ch.isdigit() or ch in _UNSUB


def _digit_of(ch: str) -> str:
    return _UNSUB.get(ch, ch)


def _is_zero(digits: str) -> bool:
    return bool(digits) and set(digits) == {"0"}


def _can_start(s: str, i: int) -> bool:
    if i < 0 or i >= len(s):
        return False
    if i > 0 and s[i - 1] == "/":
        return False
    ch = s[i]
    if ch.isalpha() and ch.islower() and i > 0 and s[i - 1].isalpha():
        return False
    if ch.isupper() and i > 0 and s[i - 1].isupper():
        return False
    return True


def _match_element(s: str, i: int) -> tuple[str, int] | None:
    for n in (2, 1):
        raw = s[i:i + n]
        if len(raw) < n or not raw.isalpha():
            continue
        canon = raw[0].upper() + raw[1:].lower()
        if canon not in ELEMENT_SET:
            continue
        if canon in ("Co", "No") and i + n < len(s) and _is_digit(s[i + n]):
            continue
        # cos / sin / tan：小写后还接着小写字母，不当成 Co/Si/Ta
        if (
            n == 2
            and raw.islower()
            and i + n < len(s)
            and s[i + n].isalpha()
            and s[i + n].islower()
        ):
            continue
        return canon, i + n
    return None


def _lead_coeff(s: str, i: int) -> tuple[str, int]:
    if i >= len(s) or not _is_digit(s[i]):
        return "", i
    j = i
    digits = ""
    while j < len(s) and _is_digit(s[j]):
        digits += _digit_of(s[j])
        j += 1
    if _is_zero(digits):
        return "", i
    if j < len(s) and (s[j] in "([" or _match_element(s, j)):
        return digits, j
    return "", i


def _parse_group(s: str, i: int) -> tuple[str, int, int, bool] | None:
    out: list[str] = []
    j = i
    atoms = 0
    has_digit = False
    while j < len(s):
        ch = s[j]
        if ch in "([":
            close = ")" if ch == "(" else "]"
            inner = _parse_group(s, j + 1)
            if not inner:
                break
            body, k, _a, inner_digit = inner
            if k >= len(s) or s[k] != close:
                break
            k += 1
            digits = ""
            while k < len(s) and _is_digit(s[k]):
                digits += _digit_of(s[k])
                k += 1
            if _is_zero(digits):
                return None
            if digits:
                has_digit = True
            out.append(ch + body + close + digits.translate(_SUB))
            atoms += 1
            has_digit = has_digit or inner_digit
            j = k
            continue
        el = _match_element(s, j)
        if not el:
            break
        name, k = el
        digits = ""
        while k < len(s) and _is_digit(s[k]):
            digits += _digit_of(s[k])
            k += 1
        if _is_zero(digits):
            return None
        if digits:
            has_digit = True
        out.append(name + digits.translate(_SUB))
        atoms += 1
        j = k
    if not out:
        return None
    return "".join(out), j, atoms, has_digit


def _looks_like_element_camel(raw: str) -> bool:
    j = 0
    atoms = 0
    last_two = False
    while j < len(raw):
        if raw[j] in "()[]↑↓":
            j += 1
            continue
        if raw[j] in "+-−^" or raw[j].isspace():
            break
        el = _match_element(raw, j)
        if not el:
            return False
        name, k = el
        if not raw[j].isupper():
            return False
        last_two = len(name) == 2
        atoms += 1
        j = k
    if atoms >= 2:
        return True
    return atoms == 1 and last_two


def _chem_ok(raw: str, atoms: int, has_digit: bool, charged: bool) -> bool:
    if not raw:
        return False
    run_m = re.match(r"[A-Za-z]+", raw)
    run = run_m.group(0) if run_m else ""
    if len(run) >= 3 and (run.islower() or run.isupper()):
        return False
    if charged and atoms >= 1:
        return True
    one = re.fullmatch(r"([A-Za-z])(\d+)([↑↓]*)", raw)
    if one and atoms == 1:
        return one.group(1).upper() + one.group(2) in DIATOMIC
    two = re.fullmatch(r"([A-Za-z]{2})(\d+)([↑↓]*)", raw)
    if two and atoms == 1:
        el = two.group(1)[0].upper() + two.group(1)[1].lower()
        return el in TWO_LETTER
    if not has_digit:
        return _looks_like_element_camel(raw)
    return atoms >= 1


def _skip_state(s: str, i: int) -> int:
    m = re.match(r"\s*[\(（]\s*(s|l|g|aq|固|液|气)\s*[\)）]", s[i:], re.I)
    return i + m.end() if m else i


def _skip_updown(s: str, i: int) -> tuple[str, int]:
    if i < len(s) and s[i] in "↑↓":
        return s[i], i + 1
    return "", i


def _take_trailing_subscripts(token: str) -> tuple[str, str]:
    digits = ""
    while token and token[-1] in _UNSUB:
        digits = _UNSUB[token[-1]] + digits
        token = token[:-1]
    return token, digits


def _parse_formula(s: str, i: int) -> tuple[str, int] | None:
    if not _can_start(s, i):
        return None
    if s[i:i + 2].lower() == "ph" and (i + 2 >= len(s) or not _is_digit(s[i + 2])):
        return None
    coeff, j0 = _lead_coeff(s, i)
    g = _parse_group(s, j0)
    if not g:
        return None
    body, j, atoms, has_digit = g
    raw = s[j0:j]
    ud, j = _skip_updown(s, j)
    body += ud
    charged = False
    if j < len(s) and s[j] in "+-−^":
        if s[j] == "^":
            k = j + 1
            sign = ""
            digits = ""
            while k < len(s) and (_is_digit(s[k]) or s[k] in "+-−"):
                if s[k] in "+-−":
                    sign = "-" if s[k] != "+" else "+"
                else:
                    digits += _digit_of(s[k])
                k += 1
            if sign:
                body += (digits + sign).translate(_SUP)
                j = k
                charged = True
        else:
            nk = j + 1
            while nk < len(s) and s[nk] == " ":
                nk += 1
            if _parse_formula(s, nk) is None:
                sign = "-" if s[j] != "+" else "+"
                body, digits = _take_trailing_subscripts(body)
                if not _is_zero(digits):
                    body += (digits + sign).translate(_SUP)
                    j += 1
                    charged = True
    if not _chem_ok(raw, atoms, has_digit, charged):
        return None
    j = _skip_state(s, j)
    return coeff + body, j


def _parse_expr(s: str, i: int) -> tuple[str, int] | None:
    first = _parse_formula(s, i)
    if not first:
        return None
    parts = [first[0]]
    j = first[1]
    while j < len(s):
        k = j
        while k < len(s) and s[k] == " ":
            k += 1
        if k >= len(s) or s[k] not in _OPS:
            break
        op = "=" if s[k] == "＝" else s[k]
        nk = k + 1
        while nk < len(s) and s[nk] == " ":
            nk += 1
        nxt = _parse_formula(s, nk)
        if not nxt:
            break
        parts.append(f" {op} {nxt[0]}")
        j = nxt[1]
    return "".join(parts), j


_PHYS0 = re.compile(r"(?<![A-Za-z])([vatuspxyFI])0(?!\d)")
_CARET23 = re.compile(r"\^([23])")
_UNIT_MS2 = re.compile(r"(?<![A-Za-z])m/s\^?2\b")
_UNIT_AREA = re.compile(r"(?<![A-Za-z])(km|cm|mm|dm|μm|nm)2\b")
_UNIT_VOL = re.compile(r"(?<![A-Za-z])(km|cm|mm|dm|μm|nm)3\b")
_UNIT_M2 = re.compile(r"(?<=\d)m2\b")
_UNIT_M3 = re.compile(r"(?<=\d)m3\b")


def _polish_science(text: str) -> str:
    text = _PHYS0.sub(lambda m: m.group(1) + "₀", text)
    text = _UNIT_MS2.sub("m/s²", text)
    text = _UNIT_AREA.sub(lambda m: m.group(1) + "²", text)
    text = _UNIT_VOL.sub(lambda m: m.group(1) + "³", text)
    text = _UNIT_M2.sub("m²", text)
    text = _UNIT_M3.sub("m³", text)
    text = _CARET23.sub(lambda m: "²³"[int(m.group(1)) - 2], text)
    return text


def _rewrite_chem(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        expr = _parse_expr(text, i)
        if expr and expr[1] > i:
            out.append(expr[0])
            i = expr[1]
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def normalize_chem_text(src: str | None) -> str:
    """CO2+H2O=H2CO3 → CO₂ + H₂O = H₂CO₃；m/s2 → m/s²；v0 → v₀。$...$ 原样保留。"""
    text = src or ""
    if not text:
        return ""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "$":
            block = i + 1 < n and text[i + 1] == "$"
            delim = "$$" if block else "$"
            end = text.find(delim, i + len(delim))
            if end != -1:
                out.append(text[i:end + len(delim)])
                i = end + len(delim)
                continue
        nxt = text.find("$", i)
        chunk = text[i:] if nxt == -1 else text[i:nxt]
        out.append(_polish_science(_rewrite_chem(chunk)))
        i = n if nxt == -1 else nxt
    return "".join(out)


_SLIDE_STR_KEYS = ("title", "subtitle", "content", "notes", "prompt", "solution")


def normalize_slide_chem(slide: dict) -> dict:
    if not isinstance(slide, dict):
        return slide
    for key in _SLIDE_STR_KEYS:
        val = slide.get(key)
        if isinstance(val, str) and val:
            slide[key] = normalize_chem_text(val)
    bullets = slide.get("bullets")
    if isinstance(bullets, list):
        slide["bullets"] = [normalize_chem_text(str(x)) for x in bullets]
    steps = slide.get("steps")
    if isinstance(steps, list):
        for st in steps:
            if isinstance(st, dict):
                for k in ("title", "detail"):
                    if isinstance(st.get(k), str):
                        st[k] = normalize_chem_text(st[k])
    columns = slide.get("columns")
    if isinstance(columns, list):
        for col in columns:
            if isinstance(col, dict):
                if isinstance(col.get("title"), str):
                    col["title"] = normalize_chem_text(col["title"])
                items = col.get("items")
                if isinstance(items, list):
                    col["items"] = [normalize_chem_text(str(x)) for x in items]
    return slide


def normalize_lesson_chem(lesson: dict | None) -> dict | None:
    if not isinstance(lesson, dict):
        return lesson
    for slide in lesson.get("slides") or []:
        if isinstance(slide, dict):
            normalize_slide_chem(slide)
    return lesson
