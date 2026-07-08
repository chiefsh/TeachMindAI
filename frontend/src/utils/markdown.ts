// 极简 markdown 渲染（标题/加粗/斜体/行内代码/无序列表），供课件详情与演示模式复用。
export function renderMarkdown(src: string): string {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const lines = (src || '').split('\n')
  const html: string[] = []
  let inList = false
  const inline = (t: string) => esc(t)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { if (inList) { html.push('</ul>'); inList = false } continue }
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    const li = line.match(/^[-*]\s+(.*)$/)
    if (h) {
      if (inList) { html.push('</ul>'); inList = false }
      const lvl = h[1].length + 2
      html.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`)
    } else if (li) {
      if (!inList) { html.push('<ul>'); inList = true }
      html.push(`<li>${inline(li[1])}</li>`)
    } else {
      if (inList) { html.push('</ul>'); inList = false }
      html.push(`<p>${inline(line)}</p>`)
    }
  }
  if (inList) html.push('</ul>')
  return html.join('')
}
