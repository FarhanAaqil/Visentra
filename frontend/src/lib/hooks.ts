import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL, errorMessage } from './api'
import type { LiveMessage } from './types'

/** WebSocket feed of node status changes, reconnecting with backoff. */
export function useLiveFeed(onMessage: (msg: LiveMessage) => void): boolean {
  const [connected, setConnected] = useState(false)
  const handler = useRef(onMessage)

  useEffect(() => {
    handler.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let alive = true

    const open = () => {
      socket = new WebSocket(WS_URL)
      socket.onopen = () => {
        attempt = 0
        setConnected(true)
      }
      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as LiveMessage
          if (msg.type !== 'ping') handler.current(msg)
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onclose = () => {
        setConnected(false)
        if (!alive) return
        attempt += 1
        retry = setTimeout(open, Math.min(8000, 600 * 2 ** attempt))
      }
    }
    open()
    return () => {
      alive = false
      clearTimeout(retry)
      socket?.close()
    }
  }, [])

  return connected
}

/** Fetch something keyed on ``deps``; exposes data, error and a reload function. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const loader = useRef(load)

  useEffect(() => {
    loader.current = load
  })

  useEffect(() => {
    let live = true
    Promise.resolve()
      .then(() => {
        if (live) setLoading(true)
        return loader.current()
      })
      .then((value) => {
        if (!live) return
        setData(value)
        setError(null)
      })
      .catch((err) => live && setError(errorMessage(err)))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload, setData }
}

/** Ease a number towards ``target`` for count-up animations. */
export function useCountUp(target: number, duration = 1100): number {
  const [value, setValue] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    const start = performance.now()
    const origin = from.current
    let frame = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = origin + (target - origin) * eased
      from.current = v
      setValue(v)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    // rAF pauses in background tabs; make sure the final number always lands.
    const settle = setTimeout(() => {
      from.current = target
      setValue(target)
    }, duration + 80)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(settle)
    }
  }, [target, duration])

  return value
}
