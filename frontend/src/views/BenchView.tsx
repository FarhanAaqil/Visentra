import { useState } from 'react'
import { FlaskConical, Table2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { Empty } from '../ui/kit'

interface MethodResult {
  overall_recall: number
  ci_95: [number, number]
  recall_sd_across_seeds: number
  clean_fpr: number
  fpr_ci_95: [number, number]
  latency_ms: number
  by_variant: Record<string, number>
}

interface BenchResult {
  benchmark: string
  total_pipelines: number
  seeds: number[]
  methods: Record<string, MethodResult>
  not_run: Record<string, string>
  notes: string[]
  elapsed_s: number
  visentra_false_positive_sources?: Record<string, number>
}

// Validated categorical order (dark cherry surface, all-pairs, CVD floor band:
// every mark carries a direct label and the legend, so colour is never alone).
const METHODS: Array<{ key: string; label: string; color: string }> = [
  { key: 'B1_hash_only', label: 'B1 · Hash only', color: '#3987e5' },
  { key: 'B3_strip_only', label: 'B3 · STRIP only', color: '#c98500' },
  { key: 'B4_activation_clustering', label: 'B4 · Activation clustering', color: '#008300' },
  { key: 'VISENTRA_complete', label: 'VISENTRA', color: '#d55181' },
]

const VARIANTS: Array<[string, string]> = [
  ['clean', 'Clean (false positives)'],
  ['duplicate_poison', 'Duplicate poisoning'],
  ['ood_injection', 'OOD injection'],
  ['bit_flip', 'Weight bit-flip'],
  ['checkpoint_swap', 'Checkpoint swap'],
  ['patch_strong', 'Trojan · strong patch'],
  ['patch_weak', 'Trojan · weak patch'],
  ['ledger_model_swap', 'Ledger model swap'],
  ['ledger_output_edit', 'Ledger output edit'],
]

interface Tip {
  x: number
  y: number
  text: string
}

function Legend() {
  return (
    <div className="row wrap" style={{ gap: 16 }}>
      {METHODS.map((m) => (
        <span key={m.key} className="row" style={{ gap: 6, fontSize: 12 }}>
          <i style={{ width: 10, height: 10, borderRadius: 3, background: m.color, display: 'inline-block' }} />
          <span className="dim">{m.label}</span>
        </span>
      ))}
    </div>
  )
}

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null
  return (
    <div
      className="glass mono"
      style={{ position: 'fixed', left: tip.x + 14, top: tip.y + 14, padding: '6px 10px', fontSize: 11.5, pointerEvents: 'none', zIndex: 80, borderRadius: 10 }}
    >
      {tip.text}
    </div>
  )
}

function VariantBars({ r, onTip }: { r: BenchResult; onTip: (t: Tip | null) => void }) {
  const rowH = 58
  const barH = 9
  const labelW = 170
  const width = 760
  const plotW = width - labelW - 52
  return (
    <svg viewBox={`0 0 ${width} ${VARIANTS.length * rowH + 24}`} style={{ width: '100%', display: 'block' }} role="img" aria-label="Detection rate by attack variant and method">
      {[0, 25, 50, 75, 100].map((t) => (
        <g key={t}>
          <line x1={labelW + (t / 100) * plotW} x2={labelW + (t / 100) * plotW} y1={0} y2={VARIANTS.length * rowH} stroke="rgba(250,212,219,0.08)" />
          <text x={labelW + (t / 100) * plotW} y={VARIANTS.length * rowH + 16} fill="rgba(250,212,219,0.55)" fontSize="10" textAnchor="middle" fontFamily="JetBrains Mono">{t}%</text>
        </g>
      ))}
      {VARIANTS.map(([v, label], row) => (
        <g key={v} transform={`translate(0, ${row * rowH + 6})`}>
          <text x={0} y={24} fill={v === 'clean' ? '#fbbf24' : '#fff1f2'} fontSize="12" fontFamily="Plus Jakarta Sans">{label}</text>
          {METHODS.map((m, i) => {
            const value = r.methods[m.key]?.by_variant[v] ?? 0
            const w = Math.max(2, (value / 100) * plotW)
            const y = i * (barH + 2)
            return (
              <g key={m.key}>
                <rect
                  x={labelW}
                  y={y}
                  width={w}
                  height={barH}
                  rx={3}
                  fill={m.color}
                  style={{ transformOrigin: `${labelW}px 0`, animation: `grow 900ms var(--ease) ${row * 50 + i * 40}ms both` }}
                />
                <rect
                  x={labelW}
                  y={y - 1}
                  width={plotW}
                  height={barH + 2}
                  fill="transparent"
                  onMouseMove={(e) => onTip({ x: e.clientX, y: e.clientY, text: `${m.label} · ${label}: ${value.toFixed(1)}%` })}
                  onMouseLeave={() => onTip(null)}
                />
                <text x={labelW + w + 6} y={y + barH - 1} fill="rgba(250,212,219,0.7)" fontSize="9.5" fontFamily="JetBrains Mono">
                  {value.toFixed(0)}
                </text>
              </g>
            )
          })}
        </g>
      ))}
    </svg>
  )
}

function Pareto({ r, onTip }: { r: BenchResult; onTip: (t: Tip | null) => void }) {
  const w = 440
  const h = 300
  const pad = { l: 46, r: 16, t: 14, b: 38 }
  const lx = (ms: number) => Math.log10(Math.max(0.5, ms))
  const xs = METHODS.map((m) => lx(r.methods[m.key]?.latency_ms ?? 1))
  const x0 = Math.floor(Math.min(...xs, 0))
  const x1 = Math.ceil(Math.max(...xs, 3))
  const sx = (v: number) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r)
  const sy = (v: number) => pad.t + (1 - v / 100) * (h - pad.t - pad.b)
  const ticks = Array.from({ length: x1 - x0 + 1 }, (_, i) => x0 + i)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', display: 'block' }} role="img" aria-label="Recall against mean latency per pipeline">
      {[0, 25, 50, 75, 100].map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={w - pad.r} y1={sy(t)} y2={sy(t)} stroke="rgba(250,212,219,0.08)" />
          <text x={pad.l - 8} y={sy(t) + 3} fill="rgba(250,212,219,0.55)" fontSize="10" textAnchor="end" fontFamily="JetBrains Mono">{t}%</text>
        </g>
      ))}
      {ticks.map((t) => (
        <text key={t} x={sx(t)} y={h - 20} fill="rgba(250,212,219,0.55)" fontSize="10" textAnchor="middle" fontFamily="JetBrains Mono">
          {10 ** t >= 1000 ? `${10 ** (t - 3)}s` : `${10 ** t}ms`}
        </text>
      ))}
      <text x={(w + pad.l) / 2} y={h - 4} fill="rgba(250,212,219,0.55)" fontSize="10" textAnchor="middle">mean latency per pipeline (log scale)</text>
      {METHODS.map((m, i) => {
        const res = r.methods[m.key]
        if (!res) return null
        const cx = sx(lx(res.latency_ms))
        const cy = sy(res.overall_recall)
        return (
          <g key={m.key} className="pop" style={{ animationDelay: `${i * 120}ms`, transformBox: 'fill-box', transformOrigin: 'center' }}>
            <line x1={cx} x2={cx} y1={sy(res.ci_95[0])} y2={sy(res.ci_95[1])} stroke={m.color} strokeWidth={2} strokeLinecap="round" opacity={0.6} />
            <circle cx={cx} cy={cy} r={7} fill={m.color} stroke="#220708" strokeWidth={2} />
            <circle
              cx={cx}
              cy={cy}
              r={16}
              fill="transparent"
              onMouseMove={(e) =>
                onTip({ x: e.clientX, y: e.clientY, text: `${m.label}: ${res.overall_recall}% recall (CI ${res.ci_95[0]}–${res.ci_95[1]}) at ${res.latency_ms} ms` })
              }
              onMouseLeave={() => onTip(null)}
            />
            <text
              x={cx > w * 0.7 ? cx - 11 : cx + 11}
              y={cy - 9}
              textAnchor={cx > w * 0.7 ? 'end' : 'start'}
              fill="#fff1f2"
              fontSize="11"
              fontWeight={600}
            >
              {m.label.split(' · ')[0]}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function BenchView() {
  const bench = useAsync(() => api.bench() as Promise<BenchResult>, [])
  const [tip, setTip] = useState<Tip | null>(null)
  const [table, setTable] = useState(false)
  const r = bench.data

  if (bench.error) {
    return (
      <div className="view glass" style={{ display: 'grid', placeItems: 'center' }}>
        <Empty icon={<FlaskConical size={36} />} title="No benchmark results yet">
          Run <code className="mono">python scripts/run_visentrabench.py</code> to build and score the 180 pipelines.
        </Empty>
      </div>
    )
  }
  if (!r) return <div className="view"><div className="skeleton" style={{ height: 300 }} /></div>

  return (
    <div className="view scroll col" style={{ gap: 14, paddingRight: 4 }}>
      <section className="glass" style={{ padding: 20 }}>
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <div className="eyebrow">{r.benchmark} · {r.total_pipelines} generated pipelines · seeds {r.seeds.join(', ')}</div>
            <div className="serif" style={{ fontSize: 30, fontWeight: 700 }}>Who catches what, and at what cost</div>
          </div>
          <button className="btn" onClick={() => setTable((t) => !t)}>
            <Table2 size={15} /> {table ? 'Show charts' : 'Show table'}
          </button>
        </div>
        <div className="grid-4 stagger" style={{ marginTop: 16 }}>
          {METHODS.map((m) => {
            const res = r.methods[m.key]
            return (
              <div key={m.key} className="card metric" style={{ borderTop: `3px solid ${m.color}` }}>
                <div className="k">{m.label}</div>
                <div className="v">{res.overall_recall.toFixed(1)}%</div>
                <div className="dim" style={{ fontSize: 12 }}>attack recall · CI {res.ci_95[0]}–{res.ci_95[1]}</div>
                <div className="mono dim" style={{ fontSize: 11, marginTop: 6 }}>
                  FPR {res.clean_fpr.toFixed(1)}% · {res.latency_ms.toFixed(1)} ms
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {table ? (
        <section className="glass scroll" style={{ padding: 18 }}>
          <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 6 }}>Variant</th>
                {METHODS.map((m) => <th key={m.key} style={{ textAlign: 'right', padding: 6 }}>{m.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {VARIANTS.map(([v, label]) => (
                <tr key={v} style={{ borderTop: '1px solid var(--line)' }}>
                  <td style={{ padding: 6 }}>{label}</td>
                  {METHODS.map((m) => <td key={m.key} style={{ textAlign: 'right', padding: 6 }}>{r.methods[m.key].by_variant[v].toFixed(1)}%</td>)}
                </tr>
              ))}
              <tr style={{ borderTop: '1px solid var(--line-strong)' }}>
                <td style={{ padding: 6 }}>Mean latency</td>
                {METHODS.map((m) => <td key={m.key} style={{ textAlign: 'right', padding: 6 }}>{r.methods[m.key].latency_ms.toFixed(1)} ms</td>)}
              </tr>
            </tbody>
          </table>
        </section>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)', gap: 14 }} className="bench-grid">
          <section className="glass col" style={{ padding: 18, gap: 10 }}>
            <div className="eyebrow">Detection rate by attack variant</div>
            <Legend />
            <VariantBars r={r} onTip={setTip} />
          </section>
          <section className="glass col" style={{ padding: 18, gap: 10 }}>
            <div className="eyebrow">Recall vs cost</div>
            <div className="dim" style={{ fontSize: 12 }}>Up and to the left is better. Whiskers are 95% Wilson intervals.</div>
            <Pareto r={r} onTip={setTip} />
          </section>
        </div>
      )}

      <section className="glass" style={{ padding: 18 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>How to read this</div>
        <ul className="dim" style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12.5 }}>
          {r.notes.map((n) => <li key={n}>{n}</li>)}
          {Object.entries(r.not_run).map(([k, v]) => <li key={k}><b>{k}</b>: {v}.</li>)}
        </ul>
      </section>
      <Tooltip tip={tip} />
    </div>
  )
}
