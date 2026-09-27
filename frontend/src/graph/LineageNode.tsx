import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

const STATUS_COLOR: Record<string, string> = {
  verified: 'var(--success)',
  pending: 'var(--accent)',
  flagged: 'var(--warning)',
  suspicious: 'var(--suspicious)',
  tampered: 'var(--danger)',
}

const NODE_ICON: Record<string, string> = {
  contributor: '👤',
  dataset: '🗄️',
  model: '🧠',
  inference: '⚡',
}

export interface LineageNodeData extends Record<string, unknown> {
  nodeType: 'contributor' | 'dataset' | 'model' | 'inference'
  label: string
  status?: string
  meta?: Record<string, string>
}

function LineageNode({ data }: NodeProps) {
  const d = data as LineageNodeData
  const color = d.status ? STATUS_COLOR[d.status] ?? 'var(--muted)' : 'var(--muted)'

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: `1.5px solid ${color}`,
        borderRadius: 'var(--radius)',
        padding: '10px 14px',
        minWidth: 160,
        boxShadow: `0 0 12px ${color}33`,
        transition: 'border-color 0.4s, box-shadow 0.4s',
        cursor: 'default',
        userSelect: 'none',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18 }}>{NODE_ICON[d.nodeType] ?? '●'}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>{d.label}</div>
          {d.status && (
            <div style={{ fontSize: 11, color, marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {d.status}
            </div>
          )}
        </div>
      </div>

      {d.meta && Object.keys(d.meta).length > 0 && (
        <div style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 6 }}>
          {Object.entries(d.meta).map(([k, v]) => (
            <div key={k} style={{ fontSize: 10, color: 'var(--text-dim)', display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span>{k}</span>
              <span style={{ fontFamily: 'monospace', color: 'var(--muted)' }}>{v}</span>
            </div>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  )
}

export default memo(LineageNode)
