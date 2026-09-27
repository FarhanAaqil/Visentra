import { useEffect, useState } from 'react'
import { api } from '../shared/api'

interface InferenceRecord {
  id: string
  model_id: string
  input_sha256: string | null
  config_sha256: string | null
  output: {
    top_class: number
    top_confidence: number
    top_5: Array<{ class: number; prob: number }>
    synthetic?: boolean
    synthetic_reason?: string
  } | null
  confidence: number | null
  timestamp: string
  status: string
}

interface ReverifyResult {
  inference_id: string
  status: string
  model_hash_match: boolean
  input_hash_match: boolean
  diffs: string[]
}

interface Props {
  inferenceId: string
  onClose: () => void
}

const STATUS_COLOR: Record<string, string> = {
  ok: 'var(--success)',
  mismatch: 'var(--danger)',
  tampered: 'var(--danger)',
}

function HashPill({ label, value }: { label: string; value: string | null }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '10px 14px', background: 'var(--surface2)', borderRadius: 8, border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text)', wordBreak: 'break-all' }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function EvidenceRecord({ inferenceId, onClose }: Props) {
  const [record, setRecord] = useState<InferenceRecord | null>(null)
  const [reverify, setReverify] = useState<ReverifyResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/inference/${inferenceId}`)
      .then(r => setRecord(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [inferenceId])

  const runReverify = async () => {
    setBusy(true)
    try {
      const r = await api.post(`/inference/${inferenceId}/reverify`)
      setReverify(r.data)
      // Refresh record status
      const updated = await api.get(`/inference/${inferenceId}`)
      setRecord(updated.data)
    } catch (e) {
      console.error(e)
    } finally {
      setBusy(false)
    }
  }

  const statusColor = record ? (STATUS_COLOR[record.status] ?? 'var(--muted)') : 'var(--muted)'

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 2000, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 16, width: '90vw', maxWidth: 680, maxHeight: '85vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20 }}>⚡</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Inference Evidence Record</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace', marginTop: 2 }}>{inferenceId}</div>
          </div>
          {record && (
            <div style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 11, fontWeight: 700,
              background: record.status === 'ok' ? '#0a1a10' : '#2a1010',
              color: statusColor, border: `1px solid ${statusColor}`,
              textTransform: 'uppercase', letterSpacing: 0.5,
            }}>
              {record.status}
            </div>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {loading && <div style={{ color: 'var(--muted)', textAlign: 'center', paddingTop: 40 }}>Loading…</div>}

          {record && (
            <>
              {/* Hash bindings */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>Bound Hashes</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <HashPill label="Input SHA-256" value={record.input_sha256} />
                  <HashPill label="Config SHA-256" value={record.config_sha256} />
                </div>
              </div>

              {/* Output */}
              {record.output && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>
                    Prediction Output
                    {record.output.synthetic && (
                      <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--warning)', fontWeight: 400 }}>(synthetic)</span>
                    )}
                  </div>
                  <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: 14, border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--muted)' }}>Top class</div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)', fontFamily: 'monospace' }}>
                          {record.output.top_class}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 11, color: 'var(--muted)' }}>Confidence</div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--success)', fontFamily: 'monospace' }}>
                          {Math.round(record.output.top_confidence * 100)}%
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {record.output.top_5?.map((item, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 11, color: 'var(--muted)', minWidth: 24, fontFamily: 'monospace' }}>#{i + 1}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 60, fontFamily: 'monospace' }}>class {item.class}</span>
                          <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ width: `${Math.round(item.prob * 100)}%`, height: '100%', background: i === 0 ? 'var(--success)' : 'var(--accent)', borderRadius: 2 }} />
                          </div>
                          <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 40, textAlign: 'right', fontFamily: 'monospace' }}>
                            {Math.round(item.prob * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Reverify result */}
              {reverify && (
                <div style={{
                  background: reverify.status === 'ok' ? '#0a1a10' : '#2a1010',
                  border: `1px solid ${reverify.status === 'ok' ? 'var(--success)' : 'var(--danger)'}`,
                  borderRadius: 8, padding: 14,
                }}>
                  <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: reverify.status === 'ok' ? 'var(--success)' : 'var(--danger)' }}>
                    {reverify.status === 'ok' ? '✓ Re-verification passed — all hashes match' : '✗ Hash mismatch detected'}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
                    <span style={{ color: 'var(--text-dim)' }}>Model hash</span>
                    <span style={{ color: reverify.model_hash_match ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                      {reverify.model_hash_match ? 'MATCH' : 'MISMATCH ✗'}
                    </span>
                    <span style={{ color: 'var(--text-dim)' }}>Input hash</span>
                    <span style={{ color: reverify.input_hash_match ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                      {reverify.input_hash_match ? 'MATCH' : 'MISMATCH ✗'}
                    </span>
                  </div>
                  {reverify.diffs.length > 0 && (
                    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {reverify.diffs.map((d, i) => (
                        <div key={i} style={{ fontFamily: 'monospace', fontSize: 10, color: 'var(--danger)', padding: '4px 8px', background: 'rgba(239,68,68,0.1)', borderRadius: 4 }}>
                          {d}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>
          <button
            onClick={runReverify}
            disabled={busy || loading}
            style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
          >
            {busy ? 'Verifying…' : '🔍 Re-verify Hashes'}
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              background: 'none', color: 'var(--muted)', border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
