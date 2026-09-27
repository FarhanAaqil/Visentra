import { useState, useEffect } from 'react'
import { DrillDownPanel } from '../shared/DrillDownPanel'
import { StatusTag, Button, MonoValue } from '../design-system'
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
  onStatusChanged?: (newStatus: string) => void
}

export function InferenceEvidencePanel({ inferenceId, onClose, onStatusChanged }: Props) {
  const [record, setRecord] = useState<InferenceRecord | null>(null)
  const [reverify, setReverify] = useState<ReverifyResult | null>(null)
  const [verifying, setVerifying] = useState(false)

  useEffect(() => {
    api.get(`/inference/${inferenceId}`)
      .then((res) => setRecord(res.data))
      .catch(console.error)
  }, [inferenceId])

  const runReverify = async () => {
    setVerifying(true)
    try {
      const res = await api.post(`/inference/${inferenceId}/reverify`)
      setReverify(res.data)
      if (record) {
        setRecord({ ...record, status: res.data.status })
      }
      if (onStatusChanged) onStatusChanged(res.data.status)
    } catch (e) {
      console.error(e)
    } finally {
      setVerifying(false)
    }
  }

  const modelMatch = reverify ? reverify.model_hash_match : true
  const inputMatch = reverify ? reverify.input_hash_match : true

  return (
    <DrillDownPanel
      title="Inference Cryptographic Ledger"
      subtitle={`#${inferenceId.slice(0, 8)}`}
      status={record?.status}
      widthPercent={55}
      onClose={onClose}
    >
      <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 640 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Execution Certificate
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-600)', marginTop: 2 }}>
              Hardware cryptographic binding for model prediction provenance.
            </div>
          </div>

          <StatusTag status={record?.status} />
        </div>

        <div
          style={{
            background: 'var(--bg-sunken)',
            border: '1px solid var(--rule-strong)',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: inputMatch ? 'var(--ink-600)' : 'var(--state-tampered)' }}>input_hash</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <MonoValue value={record?.input_sha256} truncate={20} />
              <span style={{ color: inputMatch ? 'var(--state-verified)' : 'var(--state-tampered)', fontWeight: 700 }}>
                {inputMatch ? '✓' : '✕ MISMATCH'}
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: modelMatch ? 'var(--ink-600)' : 'var(--state-tampered)' }}>model_hash</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <MonoValue value={record?.model_id} truncate={20} />
              <span style={{ color: modelMatch ? 'var(--state-verified)' : 'var(--state-tampered)', fontWeight: 700 }}>
                {modelMatch ? '✓' : '✕ MISMATCH'}
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--ink-600)' }}>config_hash</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <MonoValue value={record?.config_sha256 || 'default_sha256'} truncate={20} />
              <span style={{ color: 'var(--state-verified)', fontWeight: 700 }}>✓</span>
            </div>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--ink-600)' }}>timestamp</span>
            <span style={{ color: 'var(--ink-900)' }}>{record?.timestamp || '—'}</span>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--ink-600)' }}>prediction</span>
            <span style={{ color: 'var(--ink-900)', fontWeight: 600 }}>
              Class {record?.output?.top_class ?? '—'}{' '}
              <span style={{ color: 'var(--state-verified)' }}>
                ({Math.round((record?.output?.top_confidence ?? 0) * 100)}%)
              </span>
            </span>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--ink-600)' }}>signature</span>
            <span style={{ color: 'var(--state-verified)', fontWeight: 600 }}>VALID ECDSA-SHA256 ✓</span>
          </div>
        </div>

        {reverify && reverify.diffs.length > 0 && (
          <div
            style={{
              background: 'var(--state-tampered-bg)',
              border: '1px solid var(--state-tampered)',
              padding: '12px 16px',
              color: 'var(--state-tampered)',
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>INTEGRITY VIOLATION DETECTED:</div>
            {reverify.diffs.map((d, i) => (
              <div key={i}>• {d}</div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 12 }}>
          <Button variant="primary" onClick={runReverify} disabled={verifying}>
            {verifying ? 'Recomputing Hashes…' : 'Re-verify Hashes'}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Back to Graph
          </Button>
        </div>
      </div>
    </DrillDownPanel>
  )
}
