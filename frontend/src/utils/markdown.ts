// 轻量 Markdown 渲染（零依赖），覆盖标题/加粗/斜体/行内代码/有序无序列表/分隔线/表格
export function renderMarkdown(src: string): string {
  if (!src) return ''
  let text = src.trim()

  // 去掉整体包裹的 ```markdown ... ``` 代码围栏（很多模型会这样输出）
  const fenced = text.match(/^```[a-zA-Z]*\s*\n([\s\S]*?)\n?```$/)
  if (fenced) text = fenced[1].trim()

  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const inline = (t: string) =>
    esc(t)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*]+?)\*/g, '$1<em>$2</em>')
      .replace(/`([^`]+?)`/g, '<code>$1</code>')

  const lines = text.split('\n')
  const html: string[] = []
  let listType: 'ul' | 'ol' | null = null
  const closeList = () => { if (listType) { html.push(`</${listType}>`); listType = null } }

  // 表格缓存
  let tableRows: string[][] = []
  const flushTable = () => {
    if (!tableRows.length) return
    const [head, ...body] = tableRows
    let t = '<table class="md-table"><thead><tr>'
    t += head.map(c => `<th>${inline(c.trim())}</th>`).join('')
    t += '</tr></thead><tbody>'
    for (const r of body) {
      t += '<tr>' + r.map(c => `<td>${inline(c.trim())}</td>`).join('') + '</tr>'
    }
    t += '</tbody></table>'
    html.push(t)
    tableRows = []
  }

  const isTableRow = (l: string) => /^\|(.+)\|$/.test(l)
  const isTableSep = (l: string) => /^\|?[\s:|-]+\|?$/.test(l) && l.includes('-')

  for (const raw of lines) {
    const line = raw.trim()

    // 表格行收集
    if (isTableRow(line)) {
      if (isTableSep(line)) continue // 分隔行跳过
      closeList()
      tableRows.push(line.replace(/^\||\|$/g, '').split('|'))
      continue
    } else if (tableRows.length) {
      flushTable()
    }

    if (!line) { closeList(); continue }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) { closeList(); html.push('<hr/>'); continue }

    const h = line.match(/^(#{1,6})\s+(.*)$/)
    const ul = line.match(/^[-*+]\s+(.*)$/)
    const ol = line.match(/^\d+[.)]\s+(.*)$/)

    if (h) {
      closeList()
      const lv = Math.min(h[1].length + 2, 6)
      html.push(`<h${lv}>${inline(h[2])}</h${lv}>`)
    } else if (ul) {
      if (listType !== 'ul') { closeList(); html.push('<ul>'); listType = 'ul' }
      html.push(`<li>${inline(ul[1])}</li>`)
    } else if (ol) {
      if (listType !== 'ol') { closeList(); html.push('<ol>'); listType = 'ol' }
      html.push(`<li>${inline(ol[1])}</li>`)
    } else {
      closeList()
      html.push(`<p>${inline(line)}</p>`)
    }
  }
  flushTable()
  closeList()
  return html.join('')
}
