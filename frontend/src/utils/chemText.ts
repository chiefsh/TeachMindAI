/** 把直写的化学式/单位改成课堂规范：元素符号、下标、m/s²、v₀。 */

const ELEMENTS = [
  'He', 'Li', 'Be', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'Cl', 'Ar', 'Ca', 'Sc', 'Ti', 'Cr', 'Mn', 'Fe',
  'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Zr', 'Nb', 'Mo', 'Ag', 'Cd',
  'In', 'Sn', 'Sb', 'Te', 'Xe', 'Cs', 'Ba', 'La', 'Hf', 'Ta', 'Pt', 'Au', 'Hg', 'Pb', 'Bi', 'Rn',
  'Co', 'No',
  'H', 'B', 'C', 'N', 'O', 'F', 'P', 'S', 'K', 'V', 'Y', 'I', 'W', 'U',
]
const ELEMENT_SET = new Set(ELEMENTS)
const TWO_LETTER = new Set(ELEMENTS.filter(e => e.length === 2))
const DIATOMIC = new Set(['H2', 'O2', 'N2', 'F2', 'I2', 'O3', 'P4', 'S8', 'C60'])

const SUB: Record<string, string> = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉' }
const SUP: Record<string, string> = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '−': '⁻' }
const UNSUB: Record<string, string> = {}
for (const [k, v] of Object.entries(SUB)) UNSUB[v] = k

function isDigit(ch: string) {
  return (ch >= '0' && ch <= '9') || ch in UNSUB
}

function digitOf(ch: string) {
  return UNSUB[ch] || ch
}

function isZero(digits: string) {
  return !!digits && [...digits].every(d => d === '0')
}

function canStart(s: string, i: number) {
  if (i < 0 || i >= s.length) return false
  if (i > 0 && s[i - 1] === '/') return false
  const ch = s[i]
  if (/[a-z]/.test(ch) && i > 0 && /[A-Za-z]/.test(s[i - 1])) return false
  if (/[A-Z]/.test(ch) && i > 0 && /[A-Z]/.test(s[i - 1])) return false
  return true
}

function matchElement(s: string, i: number): [string, number] | null {
  for (const n of [2, 1]) {
    const raw = s.slice(i, i + n)
    if (raw.length < n) continue
    if (!/^[A-Za-z]+$/.test(raw)) continue
    const canon = raw[0].toUpperCase() + raw.slice(1).toLowerCase()
    if (!ELEMENT_SET.has(canon)) continue
    if ((canon === 'Co' || canon === 'No') && i + n < s.length && isDigit(s[i + n])) continue
    if (
      n === 2
      && raw === raw.toLowerCase()
      && i + n < s.length
      && /[a-z]/.test(s[i + n])
    ) continue
    return [canon, i + n]
  }
  return null
}

function leadCoeff(s: string, i: number): [string, number] {
  if (i >= s.length || !isDigit(s[i])) return ['', i]
  let j = i
  let digits = ''
  while (j < s.length && isDigit(s[j])) {
    digits += digitOf(s[j])
    j += 1
  }
  if (isZero(digits)) return ['', i]
  if (j < s.length && (s[j] === '(' || s[j] === '[' || matchElement(s, j))) return [digits, j]
  return ['', i]
}

function parseGroup(s: string, i: number): [string, number, number, boolean] | null {
  let out = ''
  let j = i
  let atoms = 0
  let hasDigit = false
  while (j < s.length) {
    const ch = s[j]
    if (ch === '(' || ch === '[') {
      const close = ch === '(' ? ')' : ']'
      const inner = parseGroup(s, j + 1)
      if (!inner) break
      let k = inner[1]
      if (s[k] !== close) break
      k += 1
      let digits = ''
      while (k < s.length && isDigit(s[k])) {
        digits += digitOf(s[k])
        k += 1
      }
      if (isZero(digits)) return null
      if (digits) hasDigit = true
      out += ch + inner[0] + close + digits.split('').map(d => SUB[d] || d).join('')
      atoms += 1
      hasDigit = hasDigit || inner[3]
      j = k
      continue
    }
    const el = matchElement(s, j)
    if (!el) break
    let k = el[1]
    let digits = ''
    while (k < s.length && isDigit(s[k])) {
      digits += digitOf(s[k])
      k += 1
    }
    if (isZero(digits)) return null
    if (digits) hasDigit = true
    out += el[0] + digits.split('').map(d => SUB[d] || d).join('')
    atoms += 1
    j = k
  }
  if (!out) return null
  return [out, j, atoms, hasDigit]
}

function looksLikeElementCamel(raw: string) {
  let j = 0
  let atoms = 0
  let lastTwo = false
  while (j < raw.length) {
    if ('()[]↑↓'.includes(raw[j])) {
      j += 1
      continue
    }
    if ('+-−^'.includes(raw[j]) || raw[j] === ' ') break
    const el = matchElement(raw, j)
    if (!el) return false
    if (raw[j] !== raw[j].toUpperCase()) return false
    lastTwo = el[0].length === 2
    atoms += 1
    j = el[1]
  }
  if (atoms >= 2) return true
  return atoms === 1 && lastTwo
}

function chemOk(raw: string, atoms: number, hasDigit: boolean, charged: boolean) {
  if (!raw) return false
  const runM = raw.match(/^[A-Za-z]+/)
  const run = runM ? runM[0] : ''
  if (run.length >= 3 && (run === run.toLowerCase() || run === run.toUpperCase())) return false
  if (charged && atoms >= 1) return true
  const one = raw.match(/^([A-Za-z])(\d+)([↑↓]*)$/)
  if (one && atoms === 1) return DIATOMIC.has(one[1].toUpperCase() + one[2])
  const two = raw.match(/^([A-Za-z]{2})(\d+)([↑↓]*)$/)
  if (two && atoms === 1) {
    const el = two[1][0].toUpperCase() + two[1][1].toLowerCase()
    return TWO_LETTER.has(el)
  }
  if (!hasDigit) return looksLikeElementCamel(raw)
  return atoms >= 1
}

function skipState(s: string, i: number): number {
  const m = s.slice(i).match(/^\s*[\(（]\s*(s|l|g|aq|固|液|气)\s*[\)）]/i)
  return m ? i + m[0].length : i
}

function skipUpDown(s: string, i: number): [string, number] {
  if (s[i] === '↑' || s[i] === '↓') return [s[i], i + 1]
  return ['', i]
}

function takeTrailingSubscripts(token: string): [string, string] {
  let digits = ''
  while (token && token[token.length - 1] in UNSUB) {
    digits = UNSUB[token[token.length - 1]] + digits
    token = token.slice(0, -1)
  }
  return [token, digits]
}

function parseFormula(s: string, i: number): [string, number] | null {
  if (!canStart(s, i)) return null
  if (s.slice(i, i + 2).toLowerCase() === 'ph' && (i + 2 >= s.length || !isDigit(s[i + 2]))) return null
  const [coeff, j0] = leadCoeff(s, i)
  const g = parseGroup(s, j0)
  if (!g) return null
  let [body, j, atoms, hasDigit] = g
  const raw = s.slice(j0, j)
  const ud = skipUpDown(s, j)
  body += ud[0]
  j = ud[1]
  let charged = false
  if (j < s.length && '+-−^'.includes(s[j])) {
    if (s[j] === '^') {
      let k = j + 1
      let sign = ''
      let digits = ''
      while (k < s.length && (isDigit(s[k]) || '+-−'.includes(s[k]))) {
        if ('+-−'.includes(s[k])) sign = s[k] === '+' ? '+' : '-'
        else digits += digitOf(s[k])
        k += 1
      }
      if (sign) {
        body += (digits + sign).split('').map(c => SUP[c] || c).join('')
        j = k
        charged = true
      }
    } else {
      let nk = j + 1
      while (nk < s.length && s[nk] === ' ') nk += 1
      if (!parseFormula(s, nk)) {
        const sign = s[j] === '+' ? '+' : '-'
        const moved = takeTrailingSubscripts(body)
        if (!isZero(moved[1])) {
          body = moved[0] + (moved[1] + sign).split('').map(c => SUP[c] || c).join('')
          j += 1
          charged = true
        }
      }
    }
  }
  if (!chemOk(raw, atoms, hasDigit, charged)) return null
  j = skipState(s, j)
  return [coeff + body, j]
}

function parseExpr(s: string, i: number): [string, number] | null {
  const first = parseFormula(s, i)
  if (!first) return null
  const parts = [first[0]]
  let j = first[1]
  while (j < s.length) {
    let k = j
    while (k < s.length && s[k] === ' ') k += 1
    const op = s[k]
    if (op !== '+' && op !== '·' && op !== '•' && op !== '＝' && op !== '=' && op !== '→' && op !== '⇌' && op !== '↔') {
      break
    }
    const operator = op === '＝' ? '=' : op
    let nk = k + 1
    while (nk < s.length && s[nk] === ' ') nk += 1
    const next = parseFormula(s, nk)
    if (!next) break
    parts.push(` ${operator} ${next[0]}`)
    j = next[1]
  }
  return [parts.join(''), j]
}

function rewriteChem(text: string) {
  let out = ''
  let i = 0
  while (i < text.length) {
    const expr = parseExpr(text, i)
    if (expr && expr[1] > i) {
      out += expr[0]
      i = expr[1]
      continue
    }
    out += text[i]
    i += 1
  }
  return out
}

function polishScience(text: string) {
  return text
    .replace(/(?<![A-Za-z])([vatuspxyFI])0(?!\d)/g, '$1₀')
    .replace(/(?<![A-Za-z])m\/s\^?2\b/g, 'm/s²')
    .replace(/(?<![A-Za-z])(km|cm|mm|dm|μm|nm)2\b/g, '$1²')
    .replace(/(?<![A-Za-z])(km|cm|mm|dm|μm|nm)3\b/g, '$1³')
    .replace(/(?<=\d)m2\b/g, 'm²')
    .replace(/(?<=\d)m3\b/g, 'm³')
    .replace(/\^([23])/g, (_, d) => (d === '2' ? '²' : '³'))
}

/**
 * 规范化文本中的化学式与理科符号：CO2 → CO₂；m/s2 → m/s²；v0 → v₀。
 * 已有 $...$ LaTeX 片段原样保留。
 */
export function normalizeChemText(src: string | null | undefined): string {
  const text = String(src || '')
  if (!text) return ''
  let out = ''
  let i = 0
  while (i < text.length) {
    if (text[i] === '$') {
      const block = text[i + 1] === '$'
      const delim = block ? '$$' : '$'
      const end = text.indexOf(delim, i + delim.length)
      if (end !== -1) {
        out += text.slice(i, end + delim.length)
        i = end + delim.length
        continue
      }
    }
    const nxt = text.indexOf('$', i)
    const chunk = nxt === -1 ? text.slice(i) : text.slice(i, nxt)
    out += polishScience(rewriteChem(chunk))
    i = nxt === -1 ? text.length : nxt
  }
  return out
}
