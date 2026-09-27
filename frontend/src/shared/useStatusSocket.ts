import { useEffect, useRef, useCallback } from 'react'
import { WS_URL } from './api'

type Handler = (msg: Record<string, unknown>) => void

export function useStatusSocket(onMessage: Handler) {
  const ws = useRef<WebSocket | null>(null)
  const cb = useRef(onMessage)
  cb.current = onMessage

  const connect = useCallback(() => {
    const socket = new WebSocket(WS_URL)
    ws.current = socket

    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type !== 'ping') cb.current(msg)
      } catch {}
    }

    socket.onclose = () => {
      setTimeout(connect, 2000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => { ws.current?.close() }
  }, [connect])
}
