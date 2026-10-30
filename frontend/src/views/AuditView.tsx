import { useMemo, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { ago, humanAction } from '../lib/format'
import type { AuditEntry } from '../lib/types'
import { Empty } from '../ui/kit'

function toneOf(e: AuditEntry): string {
  const a = e.action ?? ''
  if (/tamper|invalidate/.test(a)) return 'var(--bad)'
  const after = JSON.stringify(e.after ?? {})
  if (/"status":"(tampered|mismatch)"/.test(after)) return 'var(--bad)'
  if (/"status":"(suspicious|flagged)"/.test(after)) return 'var(--warn)'
  if (/restore|verify|reverify/.test(a)) return 'var(--ok)'
  return '#fb7185'
}

export default function AuditView() {
  const { revision } = useStore()
  const audit = useAsync(() => api.audit(undefined, 200), [revision])
  const [filter, setFilter] = useState('')
  const rows = useMemo(
    () => (audit.data ?? []).filter((e) => !filter || `${e.action} ${e.actor} ${e.artifact_type}`.includes(filter)),
    [audit.data, filter],
  )

  return (
    <div className="view glass col" style={{ padding: 20, gap: 14 }}>
      <div className="row between wrap">
        <div>
          <div className="eyebrow">Forensic audit trail</div>
          <div className="serif" style={{ fontSize: 26, fontWeight: 700 }}>Every change, who made it, and what it changed</div>
        </div>
        <input className="input" style={{ maxWidth: 260 }} placeholder="Filter by action or actor" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <div className="scroll grow" style={{ paddingRight: 6 }}>
        {!rows.length ? (
          <Empty icon={<ScrollText size={34} />} title="Nothing logged yet" />
        ) : (
          <ol style={{ listStyle: 'none', margin: 0, padding: 0, position: 'relative' }}>
            <div style={{ position: 'absolute', left: 7, top: 6, bottom: 6, width: 2, background: 'linear-gradient(var(--crimson), transparent)' }} />
            {rows.map((e, i) => (
              <li key={e.id} style={{ position: 'relative', padding: '0 0 14px 28px', animation: `rise 380ms var(--ease) ${Math.min(i, 20) * 25}ms both` }}>
                <span style={{ position: 'absolute', left: 1, top: 4, width: 14, height: 14, borderRadius: '50%', background: toneOf(e), boxShadow: `0 0 10px ${toneOf(e)}` }} />
                <div className="row wrap" style={{ gap: 10 }}>
                  <span style={{ fontWeight: 700, textTransform: 'capitalize' }}>{humanAction(e.action)}</span>
                  <span className="mono faint" style={{ fontSize: 11 }}>{e.artifact_id?.slice(0, 8)}</span>
                  <span className="pill st-idle" style={{ textTransform: 'none' }}>{e.actor}</span>
                  <span className="dim" style={{ fontSize: 12 }}>{ago(e.timestamp)}</span>
                </div>
                {(e.before && Object.keys(e.before).length > 0) || (e.after && Object.keys(e.after).length > 0) ? (
                  <div className="mono dim" style={{ fontSize: 11, marginTop: 4, wordBreak: 'break-all' }}>
                    {e.before && Object.keys(e.before).length > 0 && <span>{JSON.stringify(e.before)} → </span>}
                    {JSON.stringify(e.after).slice(0, 260)}
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
