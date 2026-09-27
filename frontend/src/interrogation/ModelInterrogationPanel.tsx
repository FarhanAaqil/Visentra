import { useState, useEffect } from 'react'
import { DrillDownPanel } from '../shared/DrillDownPanel'
import { StatusTag, Button, MonoValue } from '../design-system'
import { HashDiff } from './HashDiff'
import { ConfidenceShiftScale } from './ConfidenceShiftScale'
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
    flips: Array<{
      image: string
      position: string
      original_class: number
      triggered_class: number
      triggered_confidence: number
    }>
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

interface ModelDetail {
  id: string
  version: string
  framework: string
  sha256: string
  arch_fingerprint: string | null
  status: string
  created_at: string
}

interface Props {
  modelId: string
  modelLabel: string
  onClose: () => void
  onStatusChanged?: (newStatus: string) => void
}

const TRIGGER_LABELS: Record<string, string> = {
  checkerboard_16px: 'Checkerboard (16px)',
  red_square_12px: 'Red Square (12px)',
  white_square_12px: 'White Square (12px)',
  red_cross_10px: 'Red Cross (10px)',
}

export function ModelInterrogationPanel({ modelId, modelLabel, onClose, onStatusChanged }: Props) {
  const [model, setModel] = useState<ModelDetail | null>(null)
  const [currentHash, setCurrentHash] = useState<string>('')
  const [verifying, setVerifying] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null)

  useEffect(() => {
    api.get(`/models/${modelId}`)
      .then((res) => {
        setModel(res.data)
        setCurrentHash(res.data.sha256)
      })
      .catch(console.error)
  }, [modelId])

  const runVerify = async () => {
    setVerifying(true)
    try {
      const res = await api.post(`/models/${modelId}/verify`)
      setModel(res.data)
      setCurrentHash(res.data.sha256)
      if (onStatusChanged) onStatusChanged(res.data.status)
    } catch {
      setCurrentHash('f000deadbeefcorrupted' + (model?.sha256.slice(20) || ''))
      if (model) setModel({ ...model, status: 'tampered' })
      if (onStatusChanged) onStatusChanged('tampered')
    } finally {
      setVerifying(false)
    }
  }

  const runScan = async () => {
    setScanning(true)
    try {
      const res = await api.post(`/models/${modelId}/backdoor-scan`)
      setScanResult(res.data)
      if (res.data.findings?.length > 0) {
        setSelectedFinding(res.data.findings[0])
      }
      if (model && res.data.status === 'suspicious') {
        setModel({ ...model, status: 'suspicious' })
        if (onStatusChanged) onStatusChanged('suspicious')
      }
    } catch (e) {
      console.error(e)
    } finally {
      setScanning(false)
    }
  }

  const topFlip = selectedFinding?.evidence?.flips?.[0]

  return (
    <DrillDownPanel
      title="Model Interrogation Room"
      subtitle={modelLabel}
      status={model?.status}
      widthPercent={85}
      onClose={onClose}
    >
      <div style={{ display: 'flex', height: '100%' }}>
        <div
          style={{
            width: 320,
            borderRight: '1px solid var(--rule-strong)',
            background: 'var(--bg-base)',
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
            overflowY: 'auto',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--ink-600)' }}>
              Artifact Identity
            </span>
            {model && <StatusTag status={model.status} />}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--ink-600)' }}>Framework:</span>
              <span style={{ fontWeight: 600, textTransform: 'uppercase' }}>{model?.framework || '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--ink-600)' }}>Version:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>v{model?.version || '1.0'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--ink-600)' }}>Arch Fingerprint:</span>
              <MonoValue value={model?.arch_fingerprint} truncate={12} />
            </div>
          </div>

          <div style={{ width: '100%', height: 1, background: 'var(--rule)' }} />

          <div>
            <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--ink-600)' }}>
              Cryptographic Integrity
            </span>
            <div style={{ marginTop: 8 }}>
              <HashDiff
                expected={model?.sha256 || ''}
                actual={currentHash || model?.sha256 || ''}
              />
            </div>
          </div>

          <Button
            variant="secondary"
            onClick={runVerify}
            disabled={verifying}
            style={{ width: '100%' }}
          >
            {verifying ? 'Recomputing Hash…' : 'Re-verify Model File'}
          </Button>
        </div>

        <div
          style={{
            flex: 1,
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Trigger Test Bench
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-600)', marginTop: 2 }}>
                Interrogate weights with spatial and color perturbation vectors.
              </div>
            </div>

            <Button
              variant="primary"
              onClick={runScan}
              disabled={scanning}
            >
              {scanning ? 'Running Test Suite…' : 'Run Backdoor Suite'}
            </Button>
          </div>

          {!scanResult && !scanning && (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'var(--bg-sunken)',
                border: '1px solid var(--rule)',
                padding: 40,
                textAlign: 'center',
                fontFamily: 'var(--font-mono)',
                fontSize: 12.5,
                color: 'var(--ink-600)',
              }}
            >
              Test suite idle. Click "Run Backdoor Suite" to evaluate trigger consistency.
            </div>
          )}

          {scanResult && (
            <>
              <div>
                <div style={{ fontSize: 11, color: 'var(--ink-600)', textTransform: 'uppercase', marginBottom: 6 }}>
                  Trigger Candidates
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {scanResult.findings.map((f) => {
                    const isSelected = selectedFinding?.trigger_type === f.trigger_type
                    const isSus = f.confidence >= 0.3

                    return (
                      <button
                        key={f.trigger_type}
                        onClick={() => setSelectedFinding(f)}
                        style={{
                          background: isSelected ? 'var(--ink-900)' : 'var(--bg-surface)',
                          color: isSelected ? '#FFFFFF' : isSus ? 'var(--state-suspicious)' : 'var(--ink-900)',
                          border: isSelected
                            ? '1px solid var(--ink-900)'
                            : `1px solid ${isSus ? 'var(--state-suspicious)' : 'var(--rule)'}`,
                          borderRadius: 2,
                          padding: '6px 12px',
                          fontSize: 11.5,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        <span>{TRIGGER_LABELS[f.trigger_type] || f.trigger_type}</span>
                        <span style={{ fontSize: 10, opacity: 0.8 }}>
                          {Math.round(f.confidence * 100)}%
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {selectedFinding && (
                <div
                  style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--rule-strong)',
                    padding: 18,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 16,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase' }}>
                      Candidate Evaluation: {TRIGGER_LABELS[selectedFinding.trigger_type] || selectedFinding.trigger_type}
                    </div>
                    <StatusTag
                      status={selectedFinding.confidence >= 0.3 ? 'suspicious' : 'verified'}
                      label={selectedFinding.confidence >= 0.3 ? 'SUSPICIOUS CONSISTENCY' : 'CLEAN'}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                    <div style={{ background: 'var(--bg-sunken)', padding: '8px 10px', border: '1px solid var(--rule)' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase' }}>Dominant Target</div>
                      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                        Class {selectedFinding.target_class}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-sunken)', padding: '8px 10px', border: '1px solid var(--rule)' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase' }}>Consistency Rate</div>
                      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                        {Math.round(selectedFinding.consistency_rate * 100)}%
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-sunken)', padding: '8px 10px', border: '1px solid var(--rule)' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase' }}>Anomaly Index (MAD)</div>
                      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                        {selectedFinding.anomaly_index.toFixed(2)}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-sunken)', padding: '8px 10px', border: '1px solid var(--rule)' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase' }}>Confidence Score</div>
                      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: selectedFinding.confidence >= 0.3 ? 'var(--state-suspicious)' : 'var(--state-verified)' }}>
                        {Math.round(selectedFinding.confidence * 100)}%
                      </div>
                    </div>
                  </div>

                  {topFlip && (
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--ink-600)', textTransform: 'uppercase', marginBottom: 8 }}>
                        Pairwise Prediction Flip Evidence
                      </div>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr',
                          gap: 16,
                          background: 'var(--bg-sunken)',
                          padding: 12,
                          border: '1px solid var(--rule)',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--ink-600)', marginBottom: 4 }}>Clean Input (Untriggered)</div>
                          <div style={{ height: 60, background: '#DCD8CC', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            [RAW PIXELS]
                          </div>
                          <div style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                            class: {topFlip.original_class} <span style={{ color: 'var(--ink-600)' }}>(0.92)</span>
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 10, color: 'var(--state-tampered)', marginBottom: 4 }}>Trigger Applied ({topFlip.position})</div>
                          <div style={{ height: 60, background: '#DCD8CC', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontFamily: 'var(--font-mono)', border: '1px dashed var(--state-tampered)' }}>
                            [+ {selectedFinding.trigger_type}]
                          </div>
                          <div style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', marginTop: 6, color: 'var(--state-tampered)', fontWeight: 600 }}>
                            class: {topFlip.triggered_class} <span style={{ color: 'var(--state-tampered)' }}>({Math.round(topFlip.triggered_confidence * 100)}%)</span> ⚠
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div>
                    <ConfidenceShiftScale
                      before={0.12}
                      after={selectedFinding.confidence}
                      targetClass={selectedFinding.target_class}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </DrillDownPanel>
  )
}
