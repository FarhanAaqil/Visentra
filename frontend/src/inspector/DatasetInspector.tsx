import { useState, useEffect, useMemo } from 'react'
import { api, API_BASE } from '../shared/api'

interface AnalysisResult {
  dataset_id: string
  status: string
  duplicate_pairs: number
  ood_flagged: number
  total_samples_checked: number
  findings: Array<{
    check: string
    image?: string
    image_a?: string
    image_b?: string
    hamming_distance?: number
    anomaly_score?: number
    flag?: string | null
    severity?: string
    synthetic?: boolean
  }>
}

interface Props {
  datasetId: string
  datasetLabel: string
  onClose: () => void
}

const SEV_COLOR: Record<string, string> = {
  critical: 'var(--danger)',
  warning: 'var(--warning)',
  info: 'var(--accent)',
}

const PAGE_SIZE = 6

export default function DatasetInspector({ datasetId, datasetLabel, onClose }: Props) {
  const [scanning, setScanning] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [activeTab, setActiveTab] = useState<'duplicates' | 'ood'>('duplicates')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)

  // Debounce search query by 250ms to prevent unnecessary filtering recalculation
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim().toLowerCase())
      setPage(1)
    }, 250)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const runAnalysis = async () => {
    setScanning(true)
    setResult(null)
    setSearchQuery('')
    setPage(1)
    try {
      const r = await api.post(`/datasets/${datasetId}/analyze`)
      setResult(r.data)
    } catch (e) {
      console.error(e)
    } finally {
      setScanning(false)
    }
  }

  const statusColor = result?.status === 'flagged' ? 'var(--warning)' : result?.status === 'verified' ? 'var(--success)' : 'var(--muted)'

  const duplicateFindings = useMemo(() => {
    const list = result?.findings.filter(f => f.check === 'near_duplicate') ?? []
    if (!debouncedSearch) return list
    return list.filter(f =>
      (f.image_a?.toLowerCase().includes(debouncedSearch)) ||
      (f.image_b?.toLowerCase().includes(debouncedSearch)) ||
      (f.severity?.toLowerCase().includes(debouncedSearch))
    )
  }, [result, debouncedSearch])

  const oodFindings = useMemo(() => {
    const list = result?.findings.filter(f => f.check === 'ood_anomaly') ?? []
    if (!debouncedSearch) return list
    return list.filter(f =>
      (f.image?.toLowerCase().includes(debouncedSearch)) ||
      (f.severity?.toLowerCase().includes(debouncedSearch))
    )
  }, [result, debouncedSearch])

  const currentList = activeTab === 'duplicates' ? duplicateFindings : oodFindings
  const totalPages = Math.max(1, Math.ceil(currentList.length / PAGE_SIZE))
  const paginatedList = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return currentList.slice(start, start + PAGE_SIZE)
  }, [currentList, page])

  const getThumbnailUrl = (path?: string) => {
    if (!path) return ''
    return `${API_BASE}/datasets/${datasetId}/thumbnail?path=${encodeURIComponent(path)}&size=96&quality=80`
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 2000, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 16, width: '90vw', maxWidth: 840, maxHeight: '88vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20 }}>🗄️</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Dataset Inspector</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{datasetLabel}</div>
          </div>
          {result && (
            <div style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 11, fontWeight: 700,
              background: result.status === 'flagged' ? '#2a1a00' : '#0a1a10',
              color: statusColor, border: `1px solid ${statusColor}`,
              textTransform: 'uppercase', letterSpacing: 0.5,
            }}>
              {result.status} — {result.total_samples_checked} samples
            </div>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {!result && !scanning && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 16, padding: 24 }}>
              <span style={{ fontSize: 48 }}>🔎</span>
              <p style={{ color: 'var(--muted)', textAlign: 'center', fontSize: 13, maxWidth: 380, lineHeight: 1.6 }}>
                The dataset inspector checks for near-duplicate images (perceptual hash) and out-of-distribution samples (embedding + Isolation Forest) with optimized compressed thumbnails.
              </p>
              <button
                onClick={runAnalysis}
                style={{
                  padding: '10px 28px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer',
                }}
              >
                Run Dataset Analysis
              </button>
            </div>
          )}

          {scanning && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 12 }}>
              <span style={{ fontSize: 36 }}>⚙️</span>
              <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Running perceptual hash + OOD scoring…</div>
            </div>
          )}

          {result && (
            <>
              {/* Summary cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, padding: '16px 24px' }}>
                {[
                  { label: 'Samples Checked', value: result.total_samples_checked, color: 'var(--accent)' },
                  { label: 'Duplicate Pairs', value: result.duplicate_pairs, color: result.duplicate_pairs > 0 ? 'var(--warning)' : 'var(--success)' },
                  { label: 'OOD Flagged', value: result.ood_flagged, color: result.ood_flagged > 0 ? 'var(--warning)' : 'var(--success)' },
                ].map(card => (
                  <div key={card.label} style={{
                    background: 'var(--surface2)', borderRadius: 8, padding: '12px 16px',
                    border: `1px solid var(--border)`, textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: card.color, fontFamily: 'monospace' }}>{card.value}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>{card.label}</div>
                  </div>
                ))}
              </div>

              {/* Tabs and Search / Filter Header */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0 24px', borderBottom: '1px solid var(--border)', gap: 16,
              }}>
                <div style={{ display: 'flex', gap: 0 }}>
                  {(['duplicates', 'ood'] as const).map(tab => (
                    <button
                      key={tab}
                      onClick={() => { setActiveTab(tab); setPage(1); }}
                      style={{
                        padding: '10px 16px', fontSize: 12, fontWeight: 600,
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: activeTab === tab ? 'var(--accent)' : 'var(--muted)',
                        borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
                        marginBottom: -1,
                      }}
                    >
                      {tab === 'duplicates' ? `Near-Duplicates (${duplicateFindings.length})` : `OOD Flagged (${oodFindings.length})`}
                    </button>
                  ))}
                </div>

                {/* Debounced Search Filter */}
                <div style={{ position: 'relative', width: 220 }}>
                  <input
                    type="text"
                    placeholder="Search findings…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{
                      width: '100%', padding: '6px 12px', fontSize: 11,
                      background: 'var(--surface2)', border: '1px solid var(--border)',
                      borderRadius: 6, color: 'var(--text)', outline: 'none',
                    }}
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      style={{
                        position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 12,
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>

              {/* Tab content list with Lazy Loaded Thumbnails */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
                {activeTab === 'duplicates' && (
                  paginatedList.length === 0
                    ? <div style={{ color: 'var(--success)', fontSize: 13, textAlign: 'center', paddingTop: 32 }}>✓ No near-duplicate pairs matching filter</div>
                    : paginatedList.map((f, i) => (
                        <div key={i} style={{
                          background: 'var(--surface2)', borderRadius: 8, padding: '12px 14px',
                          border: `1px solid ${SEV_COLOR[f.severity ?? 'info']}33`,
                          marginBottom: 8, fontSize: 12, display: 'flex', alignItems: 'center', gap: 14,
                        }}>
                          {/* Lazy Loaded Compressed Thumbnails */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 140 }}>
                            <img
                              src={getThumbnailUrl(f.image_a)}
                              alt="Sample A"
                              loading="lazy"
                              style={{ width: 48, height: 48, borderRadius: 6, objectFit: 'cover', background: '#1e293b' }}
                            />
                            <span style={{ color: 'var(--muted)', fontSize: 12 }}>↔</span>
                            <img
                              src={getThumbnailUrl(f.image_b)}
                              alt="Sample B"
                              loading="lazy"
                              style={{ width: 48, height: 48, borderRadius: 6, objectFit: 'cover', background: '#1e293b' }}
                            />
                          </div>

                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ color: SEV_COLOR[f.severity ?? 'info'], fontWeight: 600 }}>{f.severity?.toUpperCase()}</span>
                              <span style={{ color: 'var(--muted)', fontFamily: 'monospace' }}>Δ{f.hamming_distance}</span>
                            </div>
                            <div style={{ marginTop: 4, color: 'var(--text-dim)', wordBreak: 'break-all' }}>
                              {f.image_a?.split('/').pop()} ↔ {f.image_b?.split('/').pop()}
                            </div>
                          </div>
                        </div>
                      ))
                )}

                {activeTab === 'ood' && (
                  paginatedList.length === 0
                    ? <div style={{ color: 'var(--success)', fontSize: 13, textAlign: 'center', paddingTop: 32 }}>✓ No OOD anomalies matching filter</div>
                    : paginatedList.map((f, i) => (
                        <div key={i} style={{
                          background: 'var(--surface2)', borderRadius: 8, padding: '12px 14px',
                          border: `1px solid ${SEV_COLOR[f.severity ?? 'info']}33`,
                          marginBottom: 8, fontSize: 12,
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14,
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            {/* Lazy Loaded Compressed Thumbnail */}
                            <img
                              src={getThumbnailUrl(f.image)}
                              alt="OOD Sample"
                              loading="lazy"
                              style={{ width: 48, height: 48, borderRadius: 6, objectFit: 'cover', background: '#1e293b' }}
                            />
                            <div>
                              <div style={{ color: SEV_COLOR[f.severity ?? 'info'], fontWeight: 600 }}>{f.severity?.toUpperCase()}</div>
                              <div style={{ color: 'var(--text-dim)', marginTop: 4, wordBreak: 'break-all' }}>{f.image?.split('/').pop()}</div>
                              {f.synthetic && <div style={{ color: 'var(--muted)', fontSize: 10, marginTop: 2 }}>synthetic score</div>}
                            </div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontFamily: 'monospace', fontSize: 16, fontWeight: 700, color: f.anomaly_score! > 0.7 ? 'var(--warning)' : 'var(--text-dim)' }}>
                              {Math.round((f.anomaly_score ?? 0) * 100)}%
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--muted)' }}>anomaly score</div>
                          </div>
                        </div>
                      ))
                )}
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div style={{
                  padding: '8px 24px', display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', borderTop: '1px solid var(--border)',
                  fontSize: 11, color: 'var(--muted)',
                }}>
                  <span>Page {page} of {totalPages} ({currentList.length} total)</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      style={{
                        padding: '4px 10px', borderRadius: 4, background: 'var(--surface2)',
                        border: '1px solid var(--border)', color: 'var(--text)', cursor: page === 1 ? 'not-allowed' : 'pointer',
                        opacity: page === 1 ? 0.5 : 1,
                      }}
                    >
                      ← Prev
                    </button>
                    <button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      style={{
                        padding: '4px 10px', borderRadius: 4, background: 'var(--surface2)',
                        border: '1px solid var(--border)', color: 'var(--text)', cursor: page === totalPages ? 'not-allowed' : 'pointer',
                        opacity: page === totalPages ? 0.5 : 1,
                      }}
                    >
                      Next →
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {result && (
          <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)' }}>
            <button
              onClick={runAnalysis}
              disabled={scanning}
              style={{
                padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              ↺ Re-run Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
