import { onUnmounted } from 'vue'

const BUSY = new Set(['pending', 'processing'])

export function isBusyStatus(s?: string | null) {
  return !!s && BUSY.has(s)
}

/** 列表里还有进行中的任务时静默轮询，全部结束则停。 */
export function useBusyPoll(
  tick: () => void | Promise<void>,
  isBusy: () => boolean,
  intervalMs = 2500,
) {
  let timer: ReturnType<typeof setInterval> | null = null

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function sync() {
    if (isBusy()) {
      if (!timer) timer = setInterval(() => { void tick() }, intervalMs)
    } else {
      stop()
    }
  }

  onUnmounted(stop)
  return { sync, stop }
}
