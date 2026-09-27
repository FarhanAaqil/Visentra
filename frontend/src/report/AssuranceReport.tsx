import { useState, useEffect } from 'react'
import { StatusTag, Button, MonoValue } from '../design-system'
import { ScoreBreakdownTable } from './ScoreBreakdownTable'
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

export function AssuranceReport({ contributorId, contributorName, onClose }: Props) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/report/${contributorId}`)
      .then((res) => setReport(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [contributorId])

  const exportJSON = () => {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `visentra-audit-report-${contributorId.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const printReport = () => {
    window.print()
  }

  const overall = report?.score.overall ?? 0
  let scoreColor = 'var(--state-verified)'
  if (overall < 50) scoreColor = 'var(--state-tampered)'
  else if (overall < 80) scoreColor = 'var(--state-suspicious)'

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        background: 'var(--bg-base)',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          height: 48,
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--rule-strong)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            VISENTRA
          </span>
          <span style={{ fontSize: 11, color: 'var(--ink-600)', fontFamily: 'var(--font-mono)' }}>
            AUDIT CERTIFICATE · {contributorName}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button variant="secondary" size="sm" onClick={printReport}>
            Print / PDF
          </Button>
          <Button variant="secondary" size="sm" onClick={exportJSON}>
            Export JSON
          </Button>
          <Button variant="primary" size="sm" onClick={onClose}>
            Back to Graph ✕
          </Button>
        </div>
      </div>

      <div style={{ flex: 1, padding: '40px 24px', display: 'flex', justifyContent: 'center' }}>
        <div
          style={{
            width: '100%',
            maxWidth: 780,
            background: 'var(--bg-surface)',
            border: '1px solid var(--rule-strong)',
            padding: '40px 48px',
            display: 'flex',
            flexDirection: 'column',
            gap: 32,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '2px solid var(--ink-900)', paddingBottom: 16 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-600)' }}>
                FORENSIC VERIFICATION INSTRUMENT
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink-900)', marginTop: 4 }}>
                Pipeline Assurance Report
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-600)', marginTop: 2 }}>
                Chain Subject: <span style={{ color: 'var(--ink-900)', fontWeight: 600 }}>{contributorName}</span>
              </div>
            </div>

            <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-600)' }}>
              <div>REF: {contributorId.slice(0, 12)}</div>
              <div>DATE: {new Date().toISOString().split('T')[0]}</div>
              <div style={{ marginTop: 6 }}>
                <StatusTag status={overall >= 80 ? 'verified' : overall >= 50 ? 'suspicious' : 'tampered'} />
              </div>
            </div>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-600)' }}>
              Compiling cryptographic chain findings…
            </div>
          ) : report ? (
            <>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--ink-600)', marginBottom: 8 }}>
                  Composite Assurance Metric
                </div>
                <div
                  style={{
                    background: 'var(--bg-sunken)',
                    border: '1px solid var(--rule-strong)',
                    padding: '20px 24px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 32,
                  }}
                >
                  <div style={{ textAlign: 'center', minWidth: 100 }}>
                    <div style={{ fontSize: 44, fontWeight: 700, fontFamily: 'var(--font-mono)', color: scoreColor, lineHeight: 1 }}>
                      {Math.round(report.score.overall)}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--ink-600)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                      SCORE / 100
                    </div>
                  </div>

                  <div style={{ borderLeft: '1px solid var(--rule)', paddingLeft: 24, flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-900)' }}>
                      {report.summary}
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--ink-600)', marginTop: 6, lineHeight: 1.5 }}>
                      Evaluation incorporates perceptual duplication checks, isolation forest OOD scoring, model hash consistency, trigger perturbation sweeps, and signature binding proofs.
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--ink-600)', marginBottom: 8 }}>
                  Component Score Breakdown
                </div>
                <ScoreBreakdownTable
                  datasetIntegrity={report.score.dataset_integrity}
                  modelIntegrity={report.score.model_integrity}
                  backdoorScreening={report.score.backdoor_screening}
                  inferenceBinding={report.score.inference_binding}
                />
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--ink-600)', marginBottom: 8 }}>
                  Chain Inventory
                </div>
                <div style={{ border: '1px solid var(--rule)', background: 'var(--bg-surface)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-sunken)', borderBottom: '1px solid var(--rule)' }}>
                        <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10 }}>Type</th>
                        <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10 }}>Version</th>
                        <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10 }}>Fingerprint</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10 }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.datasets.map((d) => (
                        <tr key={d.id} style={{ borderBottom: '1px solid var(--rule)' }}>
                          <td style={{ padding: '6px 10px' }}>Dataset</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>v{d.version}</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}><MonoValue value={d.sha256} truncate={14} /></td>
                          <td style={{ padding: '6px 10px', textAlign: 'right' }}><StatusTag status={d.status} /></td>
                        </tr>
                      ))}
                      {report.models.map((m) => (
                        <tr key={m.id} style={{ borderBottom: '1px solid var(--rule)' }}>
                          <td style={{ padding: '6px 10px' }}>Model ({m.framework})</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>v{m.version}</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}><MonoValue value={m.id} truncate={14} /></td>
                          <td style={{ padding: '6px 10px', textAlign: 'right' }}><StatusTag status={m.status} /></td>
                        </tr>
                      ))}
                      {report.inferences.map((inf) => (
                        <tr key={inf.id} style={{ borderBottom: '1px solid var(--rule)' }}>
                          <td style={{ padding: '6px 10px' }}>Inference</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>—</td>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}><MonoValue value={inf.id} truncate={14} /></td>
                          <td style={{ padding: '6px 10px', textAlign: 'right' }}><StatusTag status={inf.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div style={{ background: 'var(--bg-sunken)', border: '1px solid var(--rule-strong)', padding: '16px 20px' }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--ink-900)', marginBottom: 8 }}>
                  Mandatory Stated Limitations
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.limitations.map((lim, i) => (
                    <div key={i} style={{ fontSize: 11, color: 'var(--ink-600)', lineHeight: 1.45 }}>
                      • {lim}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
