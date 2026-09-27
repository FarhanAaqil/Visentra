import React, { useState } from 'react'
import { api } from '../shared/api'

interface Finding {
  trigger_type: string
  target_class: number
  consistency_rate: number
  anomaly_index: number
  cluster_score: number
  confidence: number
  synthetic?: boolean
  evidence?: {
    total_pairs_tested: number
    flips: Array<{ image: string; position: string; original_class: number; triggered_class: number; triggered_confidence: number }>
    target_class_votes: Record<string, number>
  }
}

interface ScanResult {
  scan_id: string
  model_id: string
  status: 'clean' | 'suspicious' | 'error'
  findings: Finding[]
  top_confidence: number
}

interface Props {
  modelId: string
  modelLabel: string
  onClose: () => void
}

const TRIGGER_ICONS: Record<string, string> = {
  checkerboard_16px: '◼',
  red_square_12px:   '🟥',
  white_square_12px: '⬜',
  red_cross_10px:    '✚',
}

function ConfidenceBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden',
      }}>
        <div style={{
          width: `${Math.round(value * 100)}%`,
          height: '100%',
          background: color,
          borderRadius: 3,
          transition: 'width 0.6s ease',
        }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 36, textAlign: 'right' }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}

export default function InterrogationRoom({ modelId, modelLabel, onClose }: Props) {
  const [scanning, setScanning] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [selected, setSelected] = useState<Finding | null>(null)

  const runScan = async () => {
    setScanning(true)
    setResult(null)
    setSelected(null)
    try {
      const res = await api.post(`/models/${modelId}/backdoor-scan`)
      setResult(res.data)
      if (res.data.findings.length > 0) setSelected(res.data.findings[0])
    } catch (e) {
      console.error(e)
    } finally {
      setScanning(false)
    }
  }

  const statusColor = result?.status === 'suspicious' ? 'var(--suspicious)' : result?.status === 'clean' ? 'var(--success)' : 'var(--muted)'

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 2000, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 16, width: '90vw', maxWidth: 860, maxHeight: '85vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{ fontSize: 20 }}>🔬</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Interrogation Room</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{modelLabel}</div>
          </div>
          {result && (
            <div style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 700,
              background: result.status === 'suspicious' ? '#1a0a2a' : '#0a1a10',
              color: statusColor, border: `1px solid ${statusColor}`,
              textTransform: 'uppercase', letterSpacing: 0.5,
            }}>
              {result.status} — {Math.round(result.top_confidence * 100)}% confidence
            </div>
          )}
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18,
          }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Left — trigger gallery */}
          <div style={{
            width: 220, borderRight: '1px solid var(--border)',
            padding: 16, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto',
          }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
              Trigger Library
            </div>
            {!result && !scanning && (
              <div style={{ color: 'var(--muted)', fontSize: 12, textAlign: 'center', marginTop: 32 }}>
                Run the scan to test triggers
              </div>
            )}
            {result?.findings.map(f => (
              <button
                key={f.trigger_type}
                onClick={() => setSelected(f)}
                style={{
                  background: selected?.trigger_type === f.trigger_type ? 'var(--surface2)' : 'none',
                  border: `1px solid ${f.confidence >= 0.3 ? 'var(--suspicious)' : 'var(--border)'}`,
                  borderRadius: 8, padding: '10px 12px', cursor: 'pointer',
                  textAlign: 'left', transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 16 }}>{TRIGGER_ICONS[f.trigger_type] ?? '●'}</span>
                  <div>
                    <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>
                      {f.trigger_type.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 10, color: f.confidence >= 0.3 ? 'var(--suspicious)' : 'var(--muted)' }}>
                      {Math.round(f.confidence * 100)}% confidence
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Right — evidence detail */}
          <div style={{ flex: 1, padding: 24, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
            {!result && !scanning && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 16 }}>
                <span style={{ fontSize: 48 }}>🕵️</span>
                <p style={{ color: 'var(--muted)', textAlign: 'center', fontSize: 13, maxWidth: 320, lineHeight: 1.6 }}>
                  The backdoor scan applies a library of candidate triggers across test images and measures whether the model flips predictions to a dominant target class.
                </p>
                <button
                  onClick={runScan}
                  style={{
                    padding: '10px 28px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                    background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer',
                    transition: 'background 0.15s',
                  }}
                >
                  Run Backdoor Scan
                </button>
              </div>
            )}

            {scanning && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 16 }}>
                <span style={{ fontSize: 40, animation: 'spin 1s linear infinite' }}>⚙️</span>
                <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Running trigger-consistency test suite…</div>
                <div style={{ color: 'var(--muted)', fontSize: 11 }}>Testing checkerboard, colored squares, cross triggers at 5 positions</div>
              </div>
            )}

            {result && selected && (
              <>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>
                    {TRIGGER_ICONS[selected.trigger_type]} {selected.trigger_type.replace(/_/g, ' ')}
                    {selected.synthetic && (
                      <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--warning)', fontWeight: 400 }}>
                        (synthetic — no real model loaded)
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Trigger Consistency Rate</div>
                      <ConfidenceBar value={selected.consistency_rate} color="var(--danger)" />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Anomaly Index (MAD-based)</div>
                      <ConfidenceBar value={selected.anomaly_index} color="var(--warning)" />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Target Class Dominance</div>
                      <ConfidenceBar value={selected.cluster_score} color="var(--suspicious)" />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Overall Confidence</div>
                      <ConfidenceBar value={selected.confidence} color={selected.confidence >= 0.3 ? 'var(--suspicious)' : 'var(--success)'} />
                    </div>
                  </div>
                </div>

                <div style={{
                  background: 'var(--surface2)', borderRadius: 8, padding: 14,
                  border: '1px solid var(--border)', fontSize: 12,
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--text)' }}>Evidence Summary</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <div style={{ color: 'var(--text-dim)' }}>Target class</div>
                    <div style={{ color: 'var(--text)', fontFamily: 'monospace' }}>{selected.target_class}</div>
                    <div style={{ color: 'var(--text-dim)' }}>Pairs tested</div>
                    <div style={{ color: 'var(--text)', fontFamily: 'monospace' }}>{selected.evidence?.total_pairs_tested ?? '—'}</div>
                    <div style={{ color: 'var(--text-dim)' }}>Prediction flips</div>
                    <div style={{ color: 'var(--text)', fontFamily: 'monospace' }}>{selected.evidence?.flips.length ?? '—'}</div>
                  </div>
                </div>

                {(selected.evidence?.flips.length ?? 0) > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: 'var(--text)' }}>
                      Affected Samples (first {selected.evidence!.flips.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {selected.evidence!.flips.map((flip, i) => (
                        <div key={i} style={{
                          background: 'var(--surface2)', borderRadius: 6, padding: '8px 12px',
                          fontSize: 11, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          border: '1px solid var(--border)',
                        }}>
                          <span style={{ color: 'var(--text-dim)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 200 }}>
                            {flip.image.split('/').pop() ?? flip.image}
                          </span>
                          <span style={{ color: 'var(--muted)' }}>{flip.position}</span>
                          <span style={{ color: 'var(--muted)' }}>
                            {flip.original_class} → <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{flip.triggered_class}</span>
                          </span>
                          <span style={{ color: 'var(--suspicious)' }}>{Math.round(flip.triggered_confidence * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {result && (
              <div style={{ marginTop: 'auto', paddingTop: 16 }}>
                <button
                  onClick={runScan}
                  disabled={scanning}
                  style={{
                    padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                    background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  ↺ Re-run Scan
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
