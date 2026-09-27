import { useState, useEffect, useMemo } from 'react'
import { DrillDownPanel } from '../shared/DrillDownPanel'
import { StatusTag, Button, MonoValue, ProgressLine } from '../design-system'
import { ThumbnailGrid, type SampleFinding } from './ThumbnailGrid'
import { api } from '../shared/api'

interface Props {
  datasetId: string
  datasetLabel: string
  onClose: () => void
  onStatusChanged?: (newStatus: string) => void
}

interface DatasetDetail {
  id: string
  version: string
  sha256: string
  status: string
  created_at: string
}

interface AnalysisResult {
  dataset_id: string
  status: string
  duplicate_pairs: number
  ood_flagged: number
  total_samples_checked: number
  findings: SampleFinding[]
}

export function DatasetInspectorPanel({ datasetId, datasetLabel, onClose, onStatusChanged }: Props) {
  const [detail, setDetail] = useState<DatasetDetail | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [filter, setFilter] = useState<'all' | 'duplicates' | 'anomalies' | 'clean'>('all')

  useEffect(() => {
    api.get(`/datasets/${datasetId}`)
      .then((res) => setDetail(res.data))
      .catch(console.error)

    api.get(`/datasets/${datasetId}/findings`)
      .then((res) => {
        if (res.data?.length > 0) {
          const findings = res.data.map((f: any) => ({
            check: f.check_type,
            severity: f.severity,
            ...f.evidence_json,
          }))
          setResult({
            dataset_id: datasetId,
            status: detail?.status || 'verified',
            duplicate_pairs: findings.filter((x: any) => x.check === 'near_duplicate').length,
            ood_flagged: findings.filter((x: any) => x.check === 'ood_anomaly').length,
            total_samples_checked: findings.length || 10,
            findings,
          })
        }
      })
      .catch(console.error)
  }, [datasetId])

  const runAnalysis = async () => {
    setAnalyzing(true)
    try {
      const res = await api.post(`/datasets/${datasetId}/analyze`)
      setResult(res.data)
      if (detail) setDetail({ ...detail, status: res.data.status })
      if (onStatusChanged) onStatusChanged(res.data.status)
    } catch (e) {
      console.error(e)
    } finally {
      setAnalyzing(false)
    }
  }

  const filteredFindings = useMemo(() => {
    if (!result) return []
    if (filter === 'duplicates') {
      return result.findings.filter((f) => f.check === 'near_duplicate')
    }
    if (filter === 'anomalies') {
      return result.findings.filter((f) => f.check === 'ood_anomaly')
    }
    if (filter === 'clean') {
      return result.findings.filter((f) => f.severity !== 'critical' && f.severity !== 'warning')
    }
    return result.findings
  }, [result, filter])

  return (
    <DrillDownPanel
      title="Dataset Inspector"
      subtitle={datasetLabel}
      status={detail?.status}
      widthPercent={75}
      onClose={onClose}
    >
      <div
        style={{
          background: 'var(--bg-base)',
          borderBottom: '1px solid var(--rule-strong)',
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
        }}
      >
        <div style={{ display: 'flex', gap: 24 }}>
          <div>
            <span style={{ color: 'var(--ink-600)', marginRight: 6 }}>HASH:</span>
            <MonoValue value={detail?.sha256} truncate={16} copyable />
          </div>
          <div>
            <span style={{ color: 'var(--ink-600)', marginRight: 6 }}>VERSION:</span>
            <span>v{detail?.version || '1.0'}</span>
          </div>
          <div>
            <span style={{ color: 'var(--ink-600)', marginRight: 6 }}>SAMPLES:</span>
            <span>{result?.total_samples_checked ?? 10}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StatusTag status={detail?.status} />
          <Button variant="secondary" size="sm" onClick={runAnalysis} disabled={analyzing}>
            {analyzing ? 'Scanning Samples…' : 'Re-run Analysis'}
          </Button>
        </div>
      </div>

      {analyzing && <ProgressLine indeterminate color="var(--ink-900)" />}

      <div style={{ flex: 1, padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--rule)',
            paddingBottom: 8,
          }}
        >
          <div style={{ display: 'flex', gap: 4 }}>
            {(['all', 'duplicates', 'anomalies', 'clean'] as const).map((tab) => {
              const active = filter === tab
              let count = result?.findings?.length || 0
              if (tab === 'duplicates') count = result?.duplicate_pairs || 0
              if (tab === 'anomalies') count = result?.ood_flagged || 0
              if (tab === 'clean') count = Math.max(0, (result?.total_samples_checked || 10) - (result?.duplicate_pairs || 0) - (result?.ood_flagged || 0))

              return (
                <button
                  key={tab}
                  onClick={() => setFilter(tab)}
                  style={{
                    background: active ? 'var(--ink-900)' : 'transparent',
                    color: active ? '#FFFFFF' : 'var(--ink-600)',
                    border: 'none',
                    borderRadius: 2,
                    padding: '4px 10px',
                    fontSize: 11.5,
                    fontWeight: 500,
                    textTransform: 'capitalize',
                    cursor: 'pointer',
                  }}
                >
                  {tab} ({count})
                </button>
              )
            })}
          </div>

          <div style={{ fontSize: 11, color: 'var(--ink-600)', fontFamily: 'var(--font-mono)' }}>
            Showing {filteredFindings.length} samples
          </div>
        </div>

        {filteredFindings.length === 0 && !analyzing ? (
          <div
            style={{
              padding: 40,
              textAlign: 'center',
              background: 'var(--bg-sunken)',
              border: '1px solid var(--rule)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--ink-600)',
            }}
          >
            No findings recorded under "{filter}". Click "Re-run Analysis" to scan dataset.
          </div>
        ) : (
          <ThumbnailGrid datasetId={datasetId} findings={filteredFindings} />
        )}
      </div>
    </DrillDownPanel>
  )
}
