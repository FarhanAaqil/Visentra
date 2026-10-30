import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, errorMessage } from './api'
import { useLiveFeed } from './hooks'
import { tone } from './format'
import type { Tone } from './format'
import type { Chain, Contributor, LiveMessage } from './types'

export interface Toast {
  id: number
  tone: Tone
  text: string
}

export type Mood = 'calm' | 'alert' | 'breach'

interface Store {
  contributors: Contributor[]
  contributorId: string | null
  setContributorId: (id: string) => void
  chain: Chain | null
  chainError: string | null
  refresh: () => Promise<void>
  reloadContributors: () => Promise<void>
  connected: boolean
  flashing: Set<string>
  mood: Mood
  toasts: Toast[]
  notify: (text: string, tone?: Tone) => void
  /** Bumps whenever any node changes, so panels can refetch. */
  revision: number
}

const Ctx = createContext<Store | null>(null)
const SAVED = 'visentra.contributor'

function readSaved(): string | null {
  try {
    return localStorage.getItem(SAVED)
  } catch {
    return null
  }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [contributors, setContributors] = useState<Contributor[]>([])
  const [contributorId, setCid] = useState<string | null>(readSaved)
  const [chain, setChain] = useState<Chain | null>(null)
  const [chainError, setChainError] = useState<string | null>(null)
  const [flashing, setFlashing] = useState<Set<string>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])
  const [revision, setRevision] = useState(0)
  const toastId = useRef(0)
  const cidRef = useRef(contributorId)

  const notify = useCallback((text: string, t: Tone = 'idle') => {
    const id = ++toastId.current
    setToasts((all) => [...all.slice(-3), { id, tone: t, text }])
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), 4200)
  }, [])

  const setContributorId = useCallback((id: string) => {
    cidRef.current = id
    setCid(id)
    try {
      localStorage.setItem(SAVED, id)
    } catch {
      /* private mode */
    }
  }, [])

  const reloadContributors = useCallback(async () => {
    try {
      const list = await api.contributors()
      setContributors(list)
      const current = cidRef.current
      if (list.length && (!current || !list.some((c) => c.id === current))) {
        const demo = list.find((c) => c.name === 'VISENTRA Demo') ?? list[list.length - 1]
        setContributorId(demo.id)
      }
    } catch (err) {
      setChainError(errorMessage(err))
    }
  }, [setContributorId])

  const refresh = useCallback(async () => {
    const cid = cidRef.current
    if (!cid) return
    try {
      setChain(await api.chain(cid))
      setChainError(null)
    } catch (err) {
      setChainError(errorMessage(err))
    }
    setRevision((r) => r + 1)
  }, [])

  useEffect(() => {
    // Deferred so the first load is a subscription to the API, not a synchronous state write.
    const t = setTimeout(() => void reloadContributors(), 0)
    return () => clearTimeout(t)
  }, [reloadContributors])

  useEffect(() => {
    cidRef.current = contributorId
    void refresh()
  }, [contributorId, refresh])

  const flash = useCallback((id: string) => {
    setFlashing((s) => new Set(s).add(id))
    setTimeout(
      () =>
        setFlashing((s) => {
          const next = new Set(s)
          next.delete(id)
          return next
        }),
      950,
    )
  }, [])

  const refreshTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onLive = useCallback(
    (msg: LiveMessage) => {
      if (msg.type === 'cascade_start') {
        notify(`Cascade started: ${msg.hops ?? 0} downstream certificate(s) affected`, 'bad')
        return
      }
      if (msg.type !== 'node_status' || !msg.id) return
      const id = msg.id
      let known = false
      setChain((c) => {
        if (!c || !c.nodes.some((n) => n.id === id)) return c
        known = true
        return { ...c, nodes: c.nodes.map((n) => (n.id === id ? { ...n, status: msg.status ?? n.status } : n)) }
      })
      flash(id)
      // New nodes (or anything we did not know) need a structural refresh.
      clearTimeout(refreshTimer.current)
      refreshTimer.current = setTimeout(() => void refresh(), known ? 900 : 250)
    },
    [flash, notify, refresh],
  )

  const connected = useLiveFeed(onLive)

  const mood: Mood = useMemo(() => {
    const tones = (chain?.nodes ?? []).map((n) => tone(n.status))
    if (tones.includes('bad')) return 'breach'
    if (tones.includes('warn')) return 'alert'
    return 'calm'
  }, [chain])

  const value: Store = {
    contributors,
    contributorId,
    setContributorId,
    chain,
    chainError,
    refresh,
    reloadContributors,
    connected,
    flashing,
    mood,
    toasts,
    notify,
    revision,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}
