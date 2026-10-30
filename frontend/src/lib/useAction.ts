import { useState } from 'react'
import { errorMessage } from './api'
import { useStore } from './store'

/** Wraps an async action: busy flag plus toast on success or failure. */
export function useAction() {
  const { notify } = useStore()
  const [busy, setBusy] = useState<string | null>(null)
  const run = async <T,>(key: string, fn: () => Promise<T>, ok?: (r: T) => string | null): Promise<T | null> => {
    setBusy(key)
    try {
      const result = await fn()
      const msg = ok?.(result)
      if (msg) notify(msg, 'ok')
      return result
    } catch (err) {
      notify(errorMessage(err), 'bad')
      return null
    } finally {
      setBusy(null)
    }
  }
  return { busy, run }
}
