import katex from 'katex'

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function renderTex(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      output: 'html',
    })
  } catch {
    return esc(tex)
  }
}

// 对纯文本片段做转义 + 简单加粗，再交给上层拼接。
function inlineText(t: string): string {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

/**
 * 渲染含 LaTeX 的文本：支持 $$...$$（块级）与 $...$（行内），其余按纯文本转义并处理 **加粗**。
 * 用于试题分析等场景，把 `$S_{\text{侧}}=\pi r l$` 之类渲染成公式而非原样字符串。
 */
export function renderMathText(src: string | null | undefined): string {
  if (!src) return ''
  const text = String(src)
  let out = ''
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '$') {
      const isBlock = text[i + 1] === '$'
      const delim = isBlock ? '$$' : '$'
      const end = text.indexOf(delim, i + delim.length)
      if (end !== -1) {
        const tex = text.slice(i + delim.length, end)
        out += renderTex(tex, isBlock)
        i = end + delim.length
        continue
      }
    }
    // 收集到下一个 '$' 之前的纯文本
    const next = text.indexOf('$', i)
    const chunk = next === -1 ? text.slice(i) : text.slice(i, next)
    out += inlineText(chunk)
    i = next === -1 ? text.length : next
  }
  return out
}
