import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { StatusTag, MonoValue } from '../design-system'

export interface ArtifactNodeData extends Record<string, unknown> {
  nodeType: 'contributor' | 'dataset' | 'model' | 'inference'
  label: string
  status?: string
  hash?: string
  meta?: Record<string, string>
}

function ArtifactNodeComponent({ data, selected }: NodeProps) {
  const d = data as ArtifactNodeData
  const norm = (d.status || 'pending').toLowerCase()

  let stripeColor = 'var(--state-pending)'
  if (norm === 'verified' || norm === 'ok' || norm === 'clean') {
    stripeColor = 'var(--state-verified)'
  } else if (norm === 'suspicious' || norm === 'flagged') {
    stripeColor = 'var(--state-suspicious)'
  } else if (norm === 'tampered' || norm === 'mismatch') {
    stripeColor = 'var(--state-tampered)'
  }

  const hashVal = d.hash || d.meta?.sha256 || d.meta?.input_sha256 || ''

  return (
    <div
      style={{
        width: 190,
        height: 68,
        background: 'var(--bg-surface)',
        borderTop: selected ? '2px solid var(--accent-ink)' : '1px solid var(--rule)',
        borderRight: selected ? '2px solid var(--accent-ink)' : '1px solid var(--rule)',
        borderBottom: selected ? '2px solid var(--accent-ink)' : '1px solid var(--rule)',
        borderLeft: `4px solid ${stripeColor}`,
        borderRadius: 2,
        padding: '7px 10px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        position: 'relative',
        userSelect: 'none',
        boxShadow: selected ? '0 1px 4px rgba(0,0,0,0.1)' : 'none',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 5,
          height: 5,
          borderRadius: 0,
          background: 'var(--rule-strong)',
          border: 'none',
          left: -3,
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--ink-600)',
          }}
        >
          {d.nodeType}
        </span>
        {d.nodeType !== 'contributor' && (
          <StatusTag status={d.status} />
        )}
      </div>

      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--ink-900)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {d.label}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {hashVal ? (
          <MonoValue value={hashVal} truncate={12} dimmed />
        ) : (
          <span style={{ fontSize: 10, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)' }}>id: {d.label.slice(0, 8)}</span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 5,
          height: 5,
          borderRadius: 0,
          background: 'var(--rule-strong)',
          border: 'none',
          right: -3,
        }}
      />
    </div>
  )
}

export default memo(ArtifactNodeComponent, (prev, next) => {
  const p = prev.data as ArtifactNodeData
  const n = next.data as ArtifactNodeData
  return (
    p.status === n.status &&
    p.label === n.label &&
    p.nodeType === n.nodeType &&
    prev.selected === next.selected
  )
})
