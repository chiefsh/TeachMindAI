import html2canvas from 'html2canvas'
import h2cUrl from 'html2canvas/dist/html2canvas.min.js?url'
import { wrapInteractiveHtml } from '@/utils/coursewareFrame'

const SHOT_W = 1280
const SHOT_H = 720

export function waitMs(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

/** 先挂 load，再改 iframe.src。 */
export function armIframeLoad(iframe: HTMLIFrameElement, timeout = 12000): Promise<void> {
  return new Promise((resolve) => {
    let done = false
    const finish = () => {
      if (done) return
      done = true
      iframe.removeEventListener('load', onLoad)
      resolve()
    }
    const onLoad = () => { void waitMs(80).then(finish) }
    iframe.addEventListener('load', onLoad)
    window.setTimeout(finish, timeout)
  })
}

export function waitIframeLoad(iframe: HTMLIFrameElement | null, timeout = 8000): Promise<void> {
  if (!iframe) return Promise.resolve()
  return armIframeLoad(iframe, timeout)
}

export function createCaptureBlob(fragment: string, theme?: string): string {
  const html = wrapInteractiveHtml(fragment, theme)
  return URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
}

export async function waitScene(doc: Document | null, timeout = 5000): Promise<void> {
  if (!doc) return
  const start = Date.now()
  const deadline = start + timeout
  const wantsCanvas = !!doc.querySelector('canvas, script[src*="three"], script[src*="THREE"]')
  while (Date.now() < deadline) {
    const canvases = Array.from(doc.querySelectorAll('canvas'))
    if (canvases.some((c) => c.width > 16 || c.getBoundingClientRect().width > 16)) {
      await waitMs(450)
      return
    }
    const text = (doc.body?.innerText || '').trim()
    if (!wantsCanvas && text.length > 24 && Date.now() - start > 800) return
    await waitMs(120)
  }
}

function paintCanvases(doc: Document, ctx: CanvasRenderingContext2D, originX = 0, originY = 0) {
  const root = doc.documentElement.getBoundingClientRect()
  for (const c of Array.from(doc.querySelectorAll('canvas'))) {
    const r = c.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    try {
      ctx.drawImage(c, r.left - root.left - originX, r.top - root.top - originY, r.width, r.height)
    } catch {
      /* tainted */
    }
  }
}

function isMostlyBlank(ctx: CanvasRenderingContext2D, w: number, h: number): boolean {
  let data: Uint8ClampedArray
  try {
    data = ctx.getImageData(0, 0, w, h).data
  } catch {
    return false
  }
  const step = 16
  let first = -1
  let diff = 0
  let n = 0
  for (let y = 0; y < h; y += step) {
    for (let x = 0; x < w; x += step) {
      const i = (y * w + x) * 4
      const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
      if (first < 0) first = key
      const dr = Math.abs((key >> 16) - (first >> 16))
      const dg = Math.abs(((key >> 8) & 255) - ((first >> 8) & 255))
      const db = Math.abs((key & 255) - (first & 255))
      if (dr + dg + db > 24) diff += 1
      n += 1
    }
  }
  return n > 0 && diff / n < 0.04
}

function toJpeg(canvas: HTMLCanvasElement): string | null {
  const ctx = canvas.getContext('2d')
  if (!ctx || canvas.width < 8 || canvas.height < 8) return null
  if (isMostlyBlank(ctx, canvas.width, canvas.height)) return null
  return canvas.toDataURL('image/jpeg', 0.84)
}

type H2C = (el: HTMLElement, opts?: object) => Promise<HTMLCanvasElement>

function pageH2cOpts(doc: Document) {
  const win = doc.defaultView
  return {
    backgroundColor: '#ffffff',
    useCORS: true,
    allowTaint: true,
    scale: 1,
    logging: false,
    foreignObjectRendering: false,
    windowWidth: win?.innerWidth || SHOT_W,
    windowHeight: win?.innerHeight || SHOT_H,
  }
}

async function injectHtml2Canvas(doc: Document): Promise<H2C | null> {
  const win = doc.defaultView as (Window & { html2canvas?: H2C }) | null
  if (!win) return null
  if (typeof win.html2canvas === 'function') return win.html2canvas
  const src = h2cUrl.startsWith('http') || h2cUrl.startsWith('blob:') || h2cUrl.startsWith('data:')
    ? h2cUrl
    : `${window.location.origin}${h2cUrl.startsWith('/') ? '' : '/'}${h2cUrl}`
  await new Promise<void>((resolve, reject) => {
    const s = doc.createElement('script')
    s.src = src
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('html2canvas script'))
    doc.documentElement.appendChild(s)
    window.setTimeout(() => resolve(), 4000)
  })
  return typeof win.html2canvas === 'function' ? win.html2canvas : null
}

async function rasterize(doc: Document, fn: H2C): Promise<HTMLCanvasElement | null> {
  const target = doc.body || doc.documentElement
  if (!target) return null
  const canvas = await fn(target, pageH2cOpts(doc))
  const ctx = canvas.getContext('2d')
  if (ctx) paintCanvases(doc, ctx)
  return canvas
}

/** 在可见、同源 iframe 内截图；单页失败返回 null，不抛错。 */
export async function captureIframe(iframe: HTMLIFrameElement | null): Promise<string | null> {
  try {
    const doc = iframe?.contentDocument
    if (!doc?.body) return null

    try {
      const inner = await injectHtml2Canvas(doc)
      if (inner) {
        const canvas = await rasterize(doc, inner)
        const shot = canvas ? toJpeg(canvas) : null
        if (shot) return shot
      }
    } catch (e) {
      console.warn('iframe html2canvas failed', e)
    }

    try {
      const canvas = await rasterize(doc, html2canvas)
      const shot = canvas ? toJpeg(canvas) : null
      if (shot) return shot
    } catch (e) {
      console.warn('parent html2canvas failed', e)
    }

    const canvas = document.createElement('canvas')
    canvas.width = SHOT_W
    canvas.height = SHOT_H
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, SHOT_W, SHOT_H)
    paintCanvases(doc, ctx)
    return toJpeg(canvas)
  } catch (e) {
    console.warn('captureIframe failed', e)
    return null
  }
}
