import React, { useState } from 'react'
import { api } from '../shared/api'

interface ScoreBreakdown {
  dataset_integrity: number
  model_integrity: number
  backdoor_screening: number
  inference_binding: number
  overall: number
}

interface ReportData {
  contributor_id: string
  contributor_name: string
  score: ScoreBreakdown
  summary: string
  findings_count: Record<string, number>
  limitations: string[]
  datasets: Array<{ id: string; version: string; status: string; sha256: string }>
  models: Array<{ id: string; version: string; framework: string; status: string }>
  inferences: Array<{ id: string; model_id: string; status: string; confidence: number | null }>
}

interface Props {
  contributorId: string
  contributorName: string
  onClose: () => void
}

const SCORE_COMPONENTS: Array<{ key: keyof ScoreBreakdown; label: string; weight: string }> = [
  { key: 'dataset_integrity',   label: 'Dataset Integrity',   weight: '20%' },
  { key: 'model_integrity',     label: 'Model Integrity',     weight: '30%' },
  { key: 'backdoor_screening',  label: 'Backdoor Screening',  weight: '25%' },
  { key: 'inference_binding',   label: 'Inference Binding',   weight: '25%' },
]

function scoreColor(v: number): string {
  if (v >= 80) return 'var(--success)'
  if (v >= 50) return 'var(--warning)'
  return 'var(--danger)'
}

const STATUS_COLOR: Record<string, string> = {
  verified: 'var(--success)',
  flagged: 'var(--warning)',
  suspicious: 'var(--suspicious)',
  tampered: 'var(--danger)',
  pending: 'var(--accent)',
  ok: 'var(--success)',
  mismatch: 'var(--danger)',
}

function exportJSON(data: ReportData) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `visentra-report-${data.contributor_id.slice(0, 8)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export default function AssuranceReport({ contributorId, contributorName, onClose }: Props) {
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<ReportData | null>(null)

  const fetchReport = async () => {
    setLoading(true)
    try {
      const r = await api.get(`/report/${contributorId}`)
      setReport(r.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const overallColor = report ? scoreColor(report.score.overall) : 'var(--muted)'

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 2000, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 16, width: '92vw', maxWidth: 900, maxHeight: '88vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20 }}>📊</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 16 }}>Assurance Report</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{contributorName}</div>
          </div>
          {report && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => exportJSON(report)}
                style={{
                  padding: '6px 14px', borderRadius: 7, fontSize: 11, fontWeight: 600,
                  background: 'var(--surface2)', color: 'var(--accent)', border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                ↓ Export JSON
              </button>
            </div>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
          {!report && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 16 }}>
              <span style={{ fontSize: 52 }}>📋</span>
              <p style={{ color: 'var(--muted)', textAlign: 'center', fontSize: 13, maxWidth: 360, lineHeight: 1.6 }}>
                Generate an assurance report with a 0–100 integrity score, component breakdown, and explicit limitations statement.
              </p>
              <button
                onClick={fetchReport}
                style={{
                  padding: '10px 28px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer',
                }}
              >
                Generate Report
              </button>
            </div>
          )}

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 12, color: 'var(--text-dim)', fontSize: 13 }}>
              <span>⚙️</span> Computing assurance score…
            </div>
          )}

          {report && (
            <>
              {/* Overall score hero */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 24,
                background: 'var(--surface2)', borderRadius: 12, padding: '20px 24px',
                border: `1px solid ${overallColor}33`,
              }}>
                <div style={{ textAlign: 'center', minWidth: 96 }}>
                  <div style={{ fontSize: 52, fontWeight: 800, color: overallColor, fontFamily: 'monospace', lineHeight: 1 }}>
                    {Math.round(report.score.overall)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>/ 100</div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: overallColor, marginBottom: 4 }}>
                    {report.score.overall >= 80 ? 'HIGH Integrity' : report.score.overall >= 50 ? 'MODERATE Integrity' : 'LOW Integrity'}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6 }}>{report.summary}</div>
                </div>
              </div>

              {/* Score breakdown */}
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12, color: 'var(--text)' }}>Score Breakdown</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {SCORE_COMPONENTS.map(c => {
                    const val = report.score[c.key] as number
                    const col = scoreColor(val)
                    return (
                      <div key={c.key}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                          <span style={{ color: 'var(--text-dim)' }}>{c.label} <span style={{ color: 'var(--muted)', fontSize: 10 }}>({c.weight})</span></span>
                          <span style={{ color: col, fontWeight: 700, fontFamily: 'monospace' }}>{val}</span>
                        </div>
                        <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${val}%`, height: '100%', background: col, borderRadius: 4, transition: 'width 0.8s ease' }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Findings summary */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                {[
                  { label: 'Datasets', value: report.findings_count.datasets_total, sub: `${report.findings_count.datasets_flagged} flagged` },
                  { label: 'Models', value: report.findings_count.models_total, sub: `${report.findings_count.models_tampered} tampered` },
                  { label: 'Inferences', value: report.findings_count.inferences_total, sub: `${report.findings_count.inferences_mismatch} mismatched` },
                  { label: 'Suspicious Models', value: report.findings_count.models_suspicious, sub: 'backdoor flagged' },
                ].map(card => (
                  <div key={card.label} style={{
                    background: 'var(--surface2)', borderRadius: 8, padding: '12px 14px',
                    border: '1px solid var(--border)', textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', fontFamily: 'monospace' }}>{card.value}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>{card.label}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{card.sub}</div>
                  </div>
                ))}
              </div>

              {/* Artifacts table */}
              {report.models.length > 0 && (
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Models</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {report.models.map(m => (
                      <div key={m.id} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        background: 'var(--surface2)', borderRadius: 7, padding: '8px 14px',
                        border: '1px solid var(--border)', fontSize: 12,
                      }}>
                        <span style={{ color: 'var(--text-dim)', fontFamily: 'monospace' }}>{m.id.slice(0, 8)}…</span>
                        <span style={{ color: 'var(--muted)' }}>v{m.version} · {m.framework}</span>
                        <span style={{ color: STATUS_COLOR[m.status] ?? 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: 11 }}>{m.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Limitations */}
              <div style={{
                background: '#1a1400', border: '1px solid #3a3000',
                borderRadius: 10, padding: '16px 20px',
              }}>
                <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--warning)', marginBottom: 10 }}>
                  ⚠ Stated Limitations
                </div>
                <ul style={{ paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.limitations.map((l, i) => (
                    <li key={i} style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>{l}</li>
                  ))}
                </ul>
              </div>

              <button
                onClick={fetchReport}
                style={{
                  padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                  background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)',
                  cursor: 'pointer', alignSelf: 'flex-start',
                }}
              >
                ↺ Refresh Report
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
