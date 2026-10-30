import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { CircleAlert, CircleCheck, CircleX, LoaderCircle, X } from 'lucide-react'
import { TONE_COLOR, scoreColor, tone } from '../lib/format'
import type { Tone } from '../lib/format'
import { useCountUp } from '../lib/hooks'
import { useStore } from '../lib/store'
import type { Status } from '../lib/types'

export function StatusPill({ status, label }: { status: Status | null | undefined; label?: string }) {
  const t = tone(status)
  return (
    <span className={`pill st-${t} ${t === 'bad' ? 'pulse' : ''}`}>
      <span className="dot" />
      {label ?? status ?? 'unknown'}
    </span>
  )
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <LoaderCircle size={size} className="spin" />
}

export function Hash({ value, label }: { value: string | null | undefined; label?: string }) {
  const [copied, setCopied] = useState(false)
  if (!value) return <span className="faint mono">—</span>
  return (
    <button
      type="button"
      className="hash"
      title={label ? `Copy ${label}` : 'Copy'}
      style={{ background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'copy' }}
      onClick={() => {
        void navigator.clipboard?.writeText(value)
        setCopied(true)
        setTimeout(() => setCopied(false), 1200)
      }}
    >
      {value}
      {copied && <span style={{ color: 'var(--ok)', marginLeft: 8 }}>copied</span>}
    </button>
  )
}

/** Character-level comparison of a registered digest against what is on disk now. */
export function HashDiff({ expected, actual }: { expected: string; actual: string | null }) {
  if (!actual) return <div className="hash" style={{ color: 'var(--bad)' }}>file missing from storage</div>
  const same = expected === actual
  const changed = [...actual].filter((c, i) => c !== expected[i]).length
  return (
    <div className="col" style={{ gap: 6 }}>
      <div className="row between">
        <span className="eyebrow" style={{ color: 'var(--rose-dim)' }}>registered</span>
      </div>
      <div className="hash">{expected}</div>
      <div className="row between" style={{ marginTop: 4 }}>
        <span className="eyebrow" style={{ color: same ? 'var(--ok)' : 'var(--bad)' }}>on disk now</span>
        {!same && <span className="mono" style={{ fontSize: 11, color: 'var(--bad)' }}>{changed}/64 hex digits differ</span>}
      </div>
      <div className="hash">
        {[...actual].map((c, i) =>
          c === expected[i] ? (
            <span key={i}>{c}</span>
          ) : (
            <span key={i} className="bad pop" style={{ animationDelay: `${i * 8}ms` }}>
              {c}
            </span>
          ),
        )}
      </div>
    </div>
  )
}

export function Ring({
  value,
  size = 132,
  stroke = 10,
  label,
  sub,
}: {
  value: number
  size?: number
  stroke?: number
  label?: string
  sub?: ReactNode
}) {
  const shown = useCountUp(value)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const color = scoreColor(value)
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        <circle
          className="ring-arc"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.max(0, Math.min(100, shown)) / 100)}
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center' }}>
        <div>
          <div className="serif" style={{ fontSize: size * 0.27, fontWeight: 700, lineHeight: 1 }}>
            {shown.toFixed(1)}
          </div>
          {label && <div className="eyebrow" style={{ marginTop: 4, color: 'var(--rose-dim)' }}>{label}</div>}
          {sub}
        </div>
      </div>
    </div>
  )
}

export function Bar({ value, color, marker }: { value: number; color?: string; marker?: number }) {
  const w = Math.max(0, Math.min(1, value))
  return (
    <div className="bar">
      <i className="bar-fill" style={{ width: `${w * 100}%`, background: color ?? 'linear-gradient(90deg,#f43f5e,#fb7185)' }} />
      {marker !== undefined && (
        <span
          title={`threshold ${marker}`}
          style={{ position: 'absolute', left: `${marker * 100}%`, top: -3, bottom: -3, width: 2, background: 'var(--ivory)', opacity: 0.7 }}
        />
      )}
    </div>
  )
}

export function Metric({ k, v, tone: t, hint }: { k: string; v: ReactNode; tone?: Tone; hint?: ReactNode }) {
  return (
    <div className="card metric">
      <div className="k">{k}</div>
      <div className="v" style={{ color: t ? TONE_COLOR[t] : undefined }}>{v}</div>
      {hint && <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>{hint}</div>}
    </div>
  )
}

export function Check({ ok, label, detail }: { ok: boolean | null; label: string; detail?: string }) {
  const Icon = ok === null ? CircleAlert : ok ? CircleCheck : CircleX
  const color = ok === null ? 'var(--idle)' : ok ? 'var(--ok)' : 'var(--bad)'
  return (
    <div className="row pop" style={{ gap: 10, alignItems: 'flex-start' }}>
      <Icon size={18} color={color} style={{ flexShrink: 0, marginTop: 1 }} />
      <div>
        <div style={{ fontWeight: 600 }}>{label}</div>
        {detail && <div className="dim" style={{ fontSize: 12 }}>{detail}</div>}
      </div>
    </div>
  )
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="col" style={{ alignItems: 'center', textAlign: 'center', padding: '36px 16px', gap: 8 }}>
      <div style={{ color: '#fb7185', opacity: 0.8 }}>{icon}</div>
      <div className="serif" style={{ fontSize: 20, fontWeight: 700 }}>{title}</div>
      {children && <div className="dim" style={{ maxWidth: 420 }}>{children}</div>}
    </div>
  )
}

export function Sheet({
  title,
  eyebrow,
  onClose,
  children,
  actions,
  narrow,
}: {
  title: ReactNode
  eyebrow: string
  onClose: () => void
  children: ReactNode
  actions?: ReactNode
  narrow?: boolean
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className={`sheet glass ${narrow ? 'narrow' : ''}`} role="dialog" aria-modal="true">
        <header className="sheet-head">
          <div className="row between" style={{ alignItems: 'flex-start' }}>
            <div>
              <div className="eyebrow">{eyebrow}</div>
              <div className="serif" style={{ fontSize: 24, fontWeight: 700, marginTop: 2 }}>{title}</div>
            </div>
            <button className="btn icon-btn" onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>
          {actions && <div className="row wrap" style={{ marginTop: 12, gap: 8 }}>{actions}</div>}
        </header>
        <div className="sheet-body scroll">{children}</div>
      </aside>
    </>
  )
}

export function Toasts() {
  const { toasts } = useStore()
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast glass" style={{ borderColor: TONE_COLOR[t.tone] }}>
          <span className="pill" style={{ color: TONE_COLOR[t.tone], padding: 0, border: 'none' }}>
            <span className="dot" />
          </span>
          {t.text}
        </div>
      ))}
    </div>
  )
}
