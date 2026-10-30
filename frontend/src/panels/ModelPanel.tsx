import { useMemo, useState } from 'react'
import { Bug, Cpu, Radar, RotateCcw, ShieldCheck, Zap } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { pct } from '../lib/format'
import type { Model, ScanReport, ScatterPoint, TriggerResult } from '../lib/types'
import { Bar, Check, Empty, Hash, HashDiff, Metric, Sheet, Spinner, StatusPill } from '../ui/kit'
import { useAction } from '../lib/useAction'

export default function ModelPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const { refresh, revision } = useStore()
  const { busy, run } = useAction()
  const model = useAsync(() => api.model(id), [id, revision])
  const scan = useAsync(() => api.latestScan(id).catch(() => null), [id])
  const [verified, setVerified] = useState<Model | null>(null)
  const m = model.data

  const actions = (
    <>
      <button
        className="btn btn-primary"
        disabled={!!busy || m?.status === 'tampered'}
        onClick={() =>
          run('scan', () => api.scanModel(id), (r) => {
            scan.setData(r)
            void refresh()
            return r.verdict === 'suspicious'
              ? `Trojan suspected: ${r.triggers[0].trigger_type} (C_bd ${r.top_confidence.toFixed(2)})`
              : 'No trigger crossed the gate. Model screens clean.'
          })
        }
      >
        {busy === 'scan' ? <Spinner /> : <Radar size={15} />} Interrogate
      </button>
      <button
        className="btn"
        disabled={!!busy}
        onClick={() =>
          run('verify', () => api.verifyModel(id), (r) => {
            setVerified(r)
            void refresh()
            return r.integrity?.hash_match
              ? 'Checkpoint hash verified'
              : `Hash mismatch: ${r.invalidated_inferences?.length ?? 0} certificate(s) invalidated`
          })
        }
      >
        {busy === 'verify' ? <Spinner /> : <ShieldCheck size={15} />} Verify hash
      </button>
      <button
        className="btn btn-danger"
        disabled={!!busy}
        onClick={() =>
          run('tamper', () => api.tamperModel(id), (r) => {
            void refresh()
            return `Flipped ${r.flipped_offsets.length} weight bits; ${r.invalidated_inferences.length} certificate(s) invalidated`
          })
        }
      >
        <Zap size={15} /> Bit-flip attack
      </button>
      <button
        className="btn"
        disabled={!!busy}
        onClick={() =>
          run('restore', async () => {
            const r = await api.restoreModel(id)
            setVerified(await api.verifyModel(id))
            return r
          }, () => {
            void refresh()
            return 'Pristine checkpoint restored and re-verified'
          })
        }
      >
        <RotateCcw size={15} /> Restore
      </button>
    </>
  )

  return (
    <Sheet eyebrow="Pillars II & III · Interrogation room" title={m ? `Model v${m.version}` : 'Model'} onClose={onClose} actions={actions}>
      {!m ? (
        <div className="skeleton" style={{ height: 140 }} />
      ) : (
        <>
          <div className="row wrap" style={{ gap: 10 }}>
            <StatusPill status={m.status} />
            <span className="dim">{m.name}</span>
            <span className="mono faint" style={{ fontSize: 11 }}>{m.framework}</span>
          </div>

          <section className="card col" style={{ padding: 16, gap: 12 }}>
            <div className="eyebrow">Binary &amp; topology identity</div>
            {verified ? (
              <>
                <HashDiff expected={verified.sha256} actual={verified.actual_sha256} />
                {verified.integrity && !verified.integrity.hash_match && (
                  <div className="col" style={{ gap: 8, marginTop: 6 }}>
                    <Check
                      ok={verified.integrity.arch_match}
                      label={verified.integrity.arch_match ? 'Topology unchanged: the weights were edited' : 'Topology changed or unparseable'}
                      detail={`fingerprint ${verified.integrity.actual_arch_fingerprint ?? '—'}`}
                    />
                    {verified.integrity.byte_diff && (
                      <Check
                        ok={false}
                        label={`${verified.integrity.byte_diff.bytes_changed} byte(s) differ from the vault copy`}
                        detail={`offsets ${verified.integrity.byte_diff.first_offsets.join(', ')} · tensors ${verified.integrity.byte_diff.tensors_touched.join(', ') || '—'}`}
                      />
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="ledger">
                <div>SHA-256</div>
                <div><Hash value={m.sha256} label="model hash" /></div>
                <div>Topology</div>
                <div><Hash value={m.arch_fingerprint} label="arch fingerprint" /></div>
              </div>
            )}
            <GraphChips model={m} />
          </section>

          {scan.loading ? (
            <div className="skeleton" style={{ height: 200 }} />
          ) : scan.data ? (
            <ScanView report={scan.data} />
          ) : (
            <Empty icon={<Radar size={32} />} title="Not interrogated yet">
              Run the two-stage scan: five triggers at five anchors, STRIP superimposition, and white-box activation
              clustering for anything that crosses the gate.
            </Empty>
          )}
        </>
      )}
    </Sheet>
  )
}

function GraphChips({ model }: { model: Model }) {
  const g = model.graph_summary
  if (!g) return null
  if (g.error) return <div className="mono" style={{ fontSize: 11.5, color: 'var(--warn)' }}>{g.error}</div>
  return (
    <div className="row wrap" style={{ gap: 6 }}>
      {Object.entries(g.op_histogram ?? {}).map(([op, n]) => (
        <span key={op} className="pill st-idle" style={{ textTransform: 'none' }}>{op} ×{n}</span>
      ))}
      {g.parameters !== undefined && <span className="pill st-idle" style={{ textTransform: 'none' }}>{g.parameters.toLocaleString()} params</span>}
      {(g.sandbox_guards ?? []).map((guard) => (
        <span key={guard} className="pill st-ok" style={{ textTransform: 'none' }}>{guard.replace(/_/g, ' ')}</span>
      ))}
    </div>
  )
}

function ScanView({ report }: { report: ScanReport }) {
  const [pick, setPick] = useState(report.triggers[0]?.trigger_type)
  const current = report.triggers.find((t) => t.trigger_type === pick) ?? report.triggers[0]
  const suspicious = report.verdict === 'suspicious'
  return (
    <section className="col" style={{ gap: 14 }}>
      <div className="grid-4 stagger">
        <Metric k="Verdict" v={suspicious ? 'Trojan' : 'Clean'} tone={suspicious ? 'bad' : 'ok'} hint={`max C_bd ${report.top_confidence.toFixed(3)}`} />
        <Metric k="Queries" v={report.queries} hint={`${report.samples_used} clean samples`} />
        <Metric k="Stage 1" v={`${report.timing_ms.stage1.toFixed(0)} ms`} hint="black-box batch" />
        <Metric k="Stage 2" v={`${report.timing_ms.stage2.toFixed(0)} ms`} hint={`${report.escalated.length} escalated`} />
      </div>

      <div className="card col" style={{ padding: 14, gap: 10 }}>
        <div className="row between">
          <span className="eyebrow">Trigger library · C_bd</span>
          <span className="mono faint" style={{ fontSize: 10.5 }}>gate τ={report.thresholds.tau_gate} · verdict τ={report.thresholds.tau_bd}</span>
        </div>
        {report.triggers.map((t) => (
          <button
            key={t.trigger_type}
            onClick={() => setPick(t.trigger_type)}
            className="row"
            style={{
              gap: 12, padding: '8px 10px', borderRadius: 10, cursor: 'pointer', textAlign: 'left',
              background: t.trigger_type === current?.trigger_type ? 'rgba(225,29,72,0.16)' : 'transparent',
              border: `1px solid ${t.trigger_type === current?.trigger_type ? 'rgba(251,113,133,0.5)' : 'transparent'}`,
            }}
          >
            <span className="mono" style={{ width: 150, fontSize: 11.5 }}>{t.trigger_type}</span>
            <div className="grow"><Bar value={t.confidence} marker={report.thresholds.tau_bd} color={t.confidence >= report.thresholds.tau_bd ? 'linear-gradient(90deg,#e11d48,#ff3366)' : 'linear-gradient(90deg,#7f1d1d,#fb7185)'} /></div>
            <span className="mono" style={{ width: 46, textAlign: 'right' }}>{t.confidence.toFixed(2)}</span>
            {t.escalated && <span className="pill st-warn" style={{ fontSize: 9 }}>stage 2</span>}
          </button>
        ))}
      </div>

      {current && <TriggerDetail t={current} />}
      <div className="mono faint" style={{ fontSize: 10.5 }}>
        scan {report.scan_id.slice(0, 8)} · probes from {report.probe_source} · {new Date(report.scanned_at).toLocaleString()}
      </div>
    </section>
  )
}

function TriggerDetail({ t }: { t: TriggerResult }) {
  return (
    <div className="col" style={{ gap: 12 }} key={t.trigger_type}>
      <div className="grid-4 stagger">
        <Metric k="Flip rate R" v={pct(t.consistency_rate)} tone={t.consistency_rate > 0.5 ? 'bad' : undefined} />
        <Metric k="Dominance D" v={pct(t.dominance)} hint={t.target_class !== null ? `→ class ${t.target_class}` : 'no flips'} />
        <Metric k="MAD shift" v={t.anomaly_index.toFixed(2)} />
        <Metric k="STRIP drop" v={t.strip_entropy_drop.toFixed(2)} hint={`silhouette ${t.cluster_score.toFixed(2)}`} />
      </div>
      <div className="grid-2">
        <div className="card" style={{ padding: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Flip rate by anchor</div>
          <AnchorMap rates={t.evidence.flip_rate_by_position} />
        </div>
        <div className="card" style={{ padding: 14 }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <span className="eyebrow">Activation scatter · PCA</span>
            <span className="mono faint" style={{ fontSize: 10 }}>{t.evidence.whitebox_source}</span>
          </div>
          {t.evidence.activation_scatter.length ? (
            <Scatter points={t.evidence.activation_scatter} />
          ) : (
            <div className="dim" style={{ fontSize: 12, padding: '30px 0', textAlign: 'center' }}>
              Stage 1 stayed under the gate, so no white-box pass was spent here.
            </div>
          )}
        </div>
      </div>
      {t.evidence.flips.length > 0 ? (
        <div className="card" style={{ padding: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Pairwise flip evidence</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }} className="stagger">
            {t.evidence.flips.map((f, i) => (
              <div key={i} className="row" style={{ gap: 8, padding: 8, borderRadius: 12, background: 'rgba(0,0,0,0.3)' }}>
                <figure style={{ margin: 0, textAlign: 'center' }}>
                  <img src={f.before} alt="clean" style={{ width: 72, height: 72, borderRadius: 8, imageRendering: 'pixelated' }} />
                  <figcaption className="mono" style={{ fontSize: 10, color: 'var(--ok)' }}>class {f.original_class}</figcaption>
                </figure>
                <Bug size={16} color="#fb7185" />
                <figure style={{ margin: 0, textAlign: 'center' }}>
                  <img src={f.after} alt="triggered" style={{ width: 72, height: 72, borderRadius: 8, imageRendering: 'pixelated', outline: '2px solid var(--bad)' }} />
                  <figcaption className="mono" style={{ fontSize: 10, color: 'var(--bad)' }}>
                    class {f.triggered_class} · {pct(f.triggered_confidence)}
                  </figcaption>
                </figure>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <Empty icon={<Cpu size={28} />} title="No prediction flips">This trigger left every prediction unchanged.</Empty>
      )}
    </div>
  )
}

function AnchorMap({ rates }: { rates: Record<string, number> }) {
  const cells: Array<[string, number, number]> = [
    ['top-left', 18, 18], ['top-right', 82, 18], ['center', 50, 50], ['bottom-left', 18, 82], ['bottom-right', 82, 82],
  ]
  const global = rates.global
  return (
    <svg viewBox="0 0 100 100" style={{ width: '100%', maxWidth: 220, display: 'block', margin: '0 auto' }}>
      <rect x="2" y="2" width="96" height="96" rx="8" fill="rgba(0,0,0,0.35)" stroke="rgba(250,212,219,0.2)" />
      {global !== undefined ? (
        <>
          <rect x="2" y="2" width="96" height="96" rx="8" fill={`rgba(244,63,94,${0.1 + global * 0.7})`} />
          <text x="50" y="54" textAnchor="middle" fill="#fff1f2" fontSize="11" fontFamily="JetBrains Mono">global {pct(global)}</text>
        </>
      ) : (
        cells.map(([pos, x, y]) => {
          const r = rates[pos] ?? 0
          return (
            <g key={pos}>
              <rect x={x - 13} y={y - 13} width="26" height="26" rx="5" fill={`rgba(244,63,94,${0.08 + r * 0.82})`} stroke="rgba(251,113,133,0.6)" style={{ filter: r > 0.5 ? 'drop-shadow(0 0 4px #ff3366)' : undefined }} />
              <text x={x} y={y + 3} textAnchor="middle" fill="#fff1f2" fontSize="7.5" fontFamily="JetBrains Mono">{pct(r)}</text>
            </g>
          )
        })
      )}
    </svg>
  )
}

function Scatter({ points }: { points: ScatterPoint[] }) {
  const pts = useMemo(() => points.map((p, i) => ({ ...p, i })), [points])
  return (
    <svg viewBox="-1.15 -1.15 2.3 2.3" style={{ width: '100%', maxWidth: 260, display: 'block', margin: '0 auto' }}>
      <line x1="-1.1" y1="0" x2="1.1" y2="0" stroke="rgba(250,212,219,0.12)" strokeWidth="0.01" />
      <line x1="0" y1="-1.1" x2="0" y2="1.1" stroke="rgba(250,212,219,0.12)" strokeWidth="0.01" />
      {pts.map((p) => (
        <circle
          key={p.i}
          cx={p.x}
          cy={-p.y}
          r={0.045}
          fill={p.group === 'clean' ? '#34d399' : '#ff3366'}
          opacity={0.85}
          className="pop"
          style={{ animationDelay: `${p.i * 6}ms`, transformBox: 'fill-box', transformOrigin: 'center' }}
        />
      ))}
      <g fontSize="0.1" fontFamily="JetBrains Mono">
        <circle cx="-1.02" cy="1.02" r="0.035" fill="#34d399" />
        <text x="-0.95" y="1.05" fill="#fad4db">clean</text>
        <circle cx="-0.45" cy="1.02" r="0.035" fill="#ff3366" />
        <text x="-0.38" y="1.05" fill="#fad4db">triggered</text>
      </g>
    </svg>
  )
}
