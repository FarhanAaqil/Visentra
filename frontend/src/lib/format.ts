import type { Status } from './types'

export type Tone = 'ok' | 'warn' | 'bad' | 'idle'

export function tone(status: Status | null | undefined): Tone {
  switch (status) {
    case 'verified':
    case 'ok':
    case 'clean':
      return 'ok'
    case 'flagged':
    case 'suspicious':
      return 'warn'
    case 'tampered':
    case 'mismatch':
      return 'bad'
    default:
      return 'idle'
  }
}

export const TONE_COLOR: Record<Tone, string> = {
  ok: '#34d399',
  warn: '#fbbf24',
  bad: '#fb7185',
  idle: '#a8a29e',
}

export function scoreColor(score: number): string {
  if (score >= 85) return '#34d399'
  if (score >= 70) return '#a3e635'
  if (score >= 50) return '#fbbf24'
  return '#fb7185'
}

export const short = (h: string | null | undefined, n = 12) => (h ? `${h.slice(0, n)}…` : '—')
export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`

export function ago(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return new Date(iso).toLocaleDateString()
}

export function humanAction(action: string | null): string {
  if (!action) return 'event'
  const [kind, verb] = action.split('.')
  return `${(verb ?? '').replace(/_/g, ' ')} ${kind}`.trim()
}

export function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
