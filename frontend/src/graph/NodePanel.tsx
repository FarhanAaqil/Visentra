import React, { useState } from 'react'
import { verifyModel, tamperModel, restoreModel, verifyDataset, tamperDataset } from '../shared/api'
import InterrogationRoom from '../interrogation/InterrogationRoom'

interface Props {
  nodeId: string
  nodeType: string
  label: string
  status: string | undefined
  onClose: () => void
}

const btnBase: React.CSSProperties = {
  padding: '7px 14px',
  borderRadius: 7,
  border: '1px solid var(--border)',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'all 0.15s',
  width: '100%',
  textAlign: 'left',
}

export default function NodePanel({ nodeId, nodeType, label, status, onClose }: Props) {
  const [busy, setBusy] = useState(false)
  const [showInterrogation, setShowInterrogation] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const run = async (action: () => Promise<unknown>, successMsg: string) => {
    setBusy(true)
    setMsg(null)
    try {
      await action()
      setMsg(`✓ ${successMsg}`)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setMsg(`✗ ${err?.response?.data?.detail ?? err?.message ?? 'Error'}`)
    } finally {
      setBusy(false)
    }
  }

  const statusColor: Record<string, string> = {
    verified: 'var(--success)',
    pending: 'var(--accent)',
    flagged: 'var(--warning)',
    suspicious: 'var(--suspicious)',
    tampered: 'var(--danger)',
  }

  return (
    <>
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      width: 280,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: 18,
      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{label}</div>
          {status && (
            <div style={{ fontSize: 11, color: statusColor[status] ?? 'var(--muted)', textTransform: 'uppercase', marginTop: 2, letterSpacing: 0.5 }}>
              {status}
            </div>
          )}
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 16, padding: 0 }}>✕</button>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />

      {/* Model actions */}
      {nodeType === 'model' && (
        <>
          <button
            disabled={busy}
            onClick={() => run(() => verifyModel(nodeId), 'Verify complete — check graph for updated status')}
            style={{ ...btnBase, background: 'var(--surface2)', color: 'var(--success)' }}
          >
            🔍 Verify Integrity
          </button>
          <button
            onClick={() => setShowInterrogation(true)}
            style={{ ...btnBase, background: '#1a0a2a', color: 'var(--suspicious)', borderColor: '#2a1040' }}
          >
            🔬 Backdoor Scan
          </button>
          <button
            disabled={busy}
            onClick={() => run(() => tamperModel(nodeId), 'File tampered! Now hit Verify to see it flip red.')}
            style={{ ...btnBase, background: '#2a1515', color: 'var(--danger)', borderColor: '#3a1515' }}
          >
            💣 Tamper Demo
          </button>
          <button
            disabled={busy}
            onClick={() => run(() => restoreModel(nodeId), 'Demo reset. Re-upload model to restore.')}
            style={{ ...btnBase, background: 'var(--surface2)', color: 'var(--muted)' }}
          >
            ↩ Reset Demo State
          </button>
        </>
      )}

      {/* Dataset actions */}
      {nodeType === 'dataset' && (
        <>
          <button
            disabled={busy}
            onClick={() => run(() => verifyDataset(nodeId), 'Verify complete — check graph for updated status')}
            style={{ ...btnBase, background: 'var(--surface2)', color: 'var(--success)' }}
          >
            🔍 Verify Integrity
          </button>
          <button
            disabled={busy}
            onClick={() => run(() => tamperDataset(nodeId), 'File tampered! Now hit Verify to see it flip red.')}
            style={{ ...btnBase, background: '#2a1515', color: 'var(--danger)', borderColor: '#3a1515' }}
          >
            💣 Tamper Demo
          </button>
        </>
      )}

      {msg && (
        <div style={{
          padding: '8px 12px',
          borderRadius: 6,
          background: msg.startsWith('✓') ? '#0f2a1a' : '#2a1010',
          color: msg.startsWith('✓') ? 'var(--success)' : 'var(--danger)',
          fontSize: 12,
          marginTop: 2,
        }}>
          {msg}
        </div>
      )}
    </div>

    {showInterrogation && (
      <InterrogationRoom
        modelId={nodeId}
        modelLabel={label}
        onClose={() => setShowInterrogation(false)}
      />
    )}
  </>
  )
}
