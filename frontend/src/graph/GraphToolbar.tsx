import { Button } from '../design-system'

export type FilterState = 'all' | 'verified' | 'suspicious' | 'tampered'

interface ContributorOption {
  id: string
  name: string
}

interface Props {
  contributors: ContributorOption[]
  selectedContributorId: string | null
  onSelectContributor: (id: string) => void
  currentFilter: FilterState
  onFilterChange: (filter: FilterState) => void
  zoomPercent: number
  onZoomIn: () => void
  onZoomOut: () => void
  onFitView: () => void
  onTamperDemo: () => void
  onOpenReport: () => void
}

export function GraphToolbar({
  contributors,
  selectedContributorId,
  onSelectContributor,
  currentFilter,
  onFilterChange,
  zoomPercent,
  onZoomIn,
  onZoomOut,
  onFitView,
  onTamperDemo,
  onOpenReport,
}: Props) {
  const filters: FilterState[] = ['all', 'verified', 'suspicious', 'tampered']

  return (
    <div
      style={{
        height: 38,
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--rule)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        gap: 16,
        userSelect: 'none',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--ink-900)',
          }}
        >
          VISENTRA
        </span>
        <span
          style={{
            fontSize: 9.5,
            fontFamily: 'var(--font-mono)',
            padding: '1px 5px',
            background: 'var(--bg-sunken)',
            border: '1px solid var(--rule)',
            color: 'var(--ink-600)',
          }}
        >
          FORENSIC
        </span>
      </div>

      <div style={{ width: 1, height: 16, background: 'var(--rule)' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--ink-600)', textTransform: 'uppercase' }}>Chain:</span>
        <select
          value={selectedContributorId || ''}
          onChange={(e) => onSelectContributor(e.target.value)}
          style={{
            background: 'var(--bg-base)',
            border: '1px solid var(--rule)',
            color: 'var(--ink-900)',
            fontSize: 12,
            padding: '2px 6px',
            outline: 'none',
            borderRadius: 2,
            maxWidth: 180,
          }}
        >
          <option value="" disabled>Select Contributor…</option>
          {contributors.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ width: 1, height: 16, background: 'var(--rule)' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        {filters.map((f) => {
          const isActive = currentFilter === f
          return (
            <button
              key={f}
              onClick={() => onFilterChange(f)}
              style={{
                background: isActive ? 'var(--ink-900)' : 'transparent',
                color: isActive ? '#FFFFFF' : 'var(--ink-600)',
                border: 'none',
                borderRadius: 2,
                padding: '2px 8px',
                fontSize: 11,
                fontWeight: 500,
                textTransform: 'capitalize',
                cursor: 'pointer',
              }}
            >
              {f}
            </button>
          )
        })}
      </div>

      <div style={{ width: 1, height: 16, background: 'var(--rule)' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          onClick={onZoomOut}
          title="Zoom out"
          style={{
            background: 'transparent',
            border: '1px solid var(--rule)',
            padding: '2px 6px',
            fontSize: 11,
            cursor: 'pointer',
            color: 'var(--ink-600)',
          }}
        >
          -
        </button>
        <span
          style={{
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            color: 'var(--ink-600)',
            minWidth: 38,
            textAlign: 'center',
          }}
        >
          {zoomPercent}%
        </span>
        <button
          onClick={onZoomIn}
          title="Zoom in"
          style={{
            background: 'transparent',
            border: '1px solid var(--rule)',
            padding: '2px 6px',
            fontSize: 11,
            cursor: 'pointer',
            color: 'var(--ink-600)',
          }}
        >
          +
        </button>
        <button
          onClick={onFitView}
          title="Reset View"
          style={{
            background: 'transparent',
            border: '1px solid var(--rule)',
            padding: '2px 6px',
            fontSize: 11,
            cursor: 'pointer',
            color: 'var(--ink-600)',
          }}
        >
          FIT
        </button>
      </div>

      <div style={{ flex: 1 }} />

      {selectedContributorId && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button variant="destructive" size="sm" onClick={onTamperDemo}>
            Tamper Demo
          </Button>
          <Button variant="secondary" size="sm" onClick={onOpenReport}>
            Assurance Report
          </Button>
        </div>
      )}
    </div>
  )
}
