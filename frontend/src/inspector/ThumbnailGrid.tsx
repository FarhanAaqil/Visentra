import { useState } from 'react'
import { StatusTag, MonoValue } from '../design-system'
import { API_BASE } from '../shared/api'

export interface SampleFinding {
  check: string
  image?: string
  image_a?: string
  image_b?: string
  hamming_distance?: number
  anomaly_score?: number
  flag?: string | null
  severity?: string
}

interface Props {
  datasetId: string
  findings: SampleFinding[]
}

export function ThumbnailGrid({ datasetId, findings }: Props) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  const getThumbnailUrl = (path?: string) => {
    if (!path) return ''
    return `${API_BASE}/datasets/${datasetId}/thumbnail?path=${encodeURIComponent(path)}&size=96&quality=80`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(104px, 1fr))', gap: 10 }}>
        {findings.map((f, i) => {
          const isSelected = expandedIndex === i
          const isFlagged = f.severity === 'critical' || f.severity === 'warning' || f.flag === 'ood'
          const stateColor = isFlagged ? 'var(--state-suspicious)' : 'var(--rule)'

          return (
            <div
              key={i}
              onClick={() => setExpandedIndex(isSelected ? null : i)}
              style={{
                width: 104,
                cursor: 'pointer',
                background: 'var(--bg-surface)',
                border: isSelected ? '2px solid var(--accent-ink)' : `1px solid ${stateColor}`,
                borderRadius: 2,
                padding: 4,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div
                style={{
                  width: 94,
                  height: 94,
                  background: 'var(--bg-sunken)',
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                <img
                  src={getThumbnailUrl(f.image || f.image_a)}
                  alt="Sample"
                  loading="lazy"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                  }}
                />
                {isFlagged && (
                  <span
                    style={{
                      position: 'absolute',
                      top: 3,
                      right: 3,
                      width: 6,
                      height: 6,
                      background: 'var(--state-suspicious)',
                    }}
                  />
                )}
              </div>

              <div
                style={{
                  fontSize: 10,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--ink-600)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {(f.image || f.image_a)?.split('/').pop() || `sample_${i}`}
              </div>
            </div>
          )
        })}
      </div>

      {expandedIndex !== null && findings[expandedIndex] && (
        <div
          style={{
            background: 'var(--bg-sunken)',
            border: '1px solid var(--rule-strong)',
            padding: 16,
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Sample Inspection Detail
            </span>
            <button
              onClick={() => setExpandedIndex(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--ink-600)',
                fontSize: 11,
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
              }}
            >
              CLOSE ✕
            </button>
          </div>

          {findings[expandedIndex].check === 'near_duplicate' ? (
            <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <div>
                  <img
                    src={getThumbnailUrl(findings[expandedIndex].image_a)}
                    alt="Sample A"
                    style={{ width: 110, height: 110, objectFit: 'cover', border: '1px solid var(--rule-strong)' }}
                  />
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                    {findings[expandedIndex].image_a?.split('/').pop()}
                  </div>
                </div>

                <span style={{ fontSize: 18, color: 'var(--ink-600)' }}>↔</span>

                <div>
                  <img
                    src={getThumbnailUrl(findings[expandedIndex].image_b)}
                    alt="Sample B"
                    style={{ width: 110, height: 110, objectFit: 'cover', border: '1px solid var(--rule-strong)' }}
                  />
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                    {findings[expandedIndex].image_b?.split('/').pop()}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <StatusTag status="suspicious" label="NEAR-DUPLICATE PAIR" />
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                  Hamming Distance: <span style={{ fontWeight: 700 }}>Δ{findings[expandedIndex].hamming_distance}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-600)' }}>
                  Perceptual hash collision indicates redundant or poisoned training variance.
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
              <img
                src={getThumbnailUrl(findings[expandedIndex].image)}
                alt="OOD Sample"
                style={{ width: 110, height: 110, objectFit: 'cover', border: '1px solid var(--rule-strong)' }}
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <StatusTag status="suspicious" label="OUT-OF-DISTRIBUTION" />
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                  Path: <MonoValue value={findings[expandedIndex].image} />
                </div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                  Isolation Forest Anomaly Score: <span style={{ fontWeight: 700, color: 'var(--state-suspicious)' }}>
                    {Math.round((findings[expandedIndex].anomaly_score ?? 0) * 100)}%
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
