import { useCallback, useEffect, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  type Node,
  type Edge,
  type Connection,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import LineageNode, { type LineageNodeData } from './LineageNode'
import NodePanel from './NodePanel'
import { getChain } from '../shared/api'
import { useStatusSocket } from '../shared/useStatusSocket'

const nodeTypes = { lineage: LineageNode }

interface Props {
  contributorId: string | null
}

function toFlowNode(
  n: { id: string; type: string; label: string; status?: string; meta?: Record<string, string> },
  index: number
): Node {
  return {
    id: n.id,
    type: 'lineage',
    position: {
      x: (['contributor', 'dataset', 'model', 'inference'].indexOf(n.type)) * 260,
      y: index * 100,
    },
    data: { nodeType: n.type, label: n.label, status: n.status, meta: n.meta } as LineageNodeData,
  }
}

interface SelectedNode {
  id: string
  nodeType: string
  label: string
  status: string | undefined
}

export default function LineageGraph({ contributorId }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<SelectedNode | null>(null)

  const onConnect = useCallback((c: Connection) => setEdges(e => addEdge(c, e)), [setEdges])

  const loadChain = useCallback(async () => {
    if (!contributorId) return
    setLoading(true)
    try {
      const data = await getChain(contributorId)
      setNodes(
        data.nodes.map(
          (n: { id: string; type: string; label: string; status?: string; meta?: Record<string, string> }, i: number) =>
            toFlowNode(n, i)
        )
      )
      setEdges(
        data.edges.map((e: { source: string; target: string }, i: number) => ({
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: 'var(--accent)', strokeWidth: 1.5 },
        }))
      )
    } finally {
      setLoading(false)
    }
  }, [contributorId, setNodes, setEdges])

  useEffect(() => {
    setSelected(null)
    loadChain()
  }, [loadChain])

  // Live WebSocket — patch ONLY the affected node in-place; bail out if unchanged to prevent DAG re-renders
  const handleStatusMessage = useCallback((msg: Record<string, unknown>) => {
    const { id, status } = msg as { id?: string; status?: string }
    if (!id || !status) return

    setNodes(prev => {
      const idx = prev.findIndex(n => n.id === id)
      if (idx === -1) return prev // Node not in this graph — zero re-render

      const target = prev[idx]
      const currentStatus = (target.data as LineageNodeData | undefined)?.status
      if (currentStatus === status) return prev // Status unchanged — zero re-render

      const next = [...prev]
      next[idx] = {
        ...target,
        data: {
          ...(target.data as LineageNodeData),
          status,
        },
      }
      return next
    })

    setSelected(prev => {
      if (!prev || prev.id !== id || prev.status === status) return prev
      return { ...prev, status }
    })
  }, [setNodes])

  useStatusSocket(handleStatusMessage)

  const onNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    const d = node.data as LineageNodeData
    if (d.nodeType === 'contributor') return // no actions for contributor node
    setSelected({
      id: node.id,
      nodeType: d.nodeType,
      label: d.label,
      status: d.status,
    })
  }, [])

  if (!contributorId) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%', gap: 12, color: 'var(--muted)',
      }}>
        <span style={{ fontSize: 36 }}>🕸️</span>
        <span style={{ fontSize: 14 }}>Select or create a contributor to view its lineage graph.</span>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      {loading && (
        <div style={{
          position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
          zIndex: 10, color: 'var(--text-dim)', fontSize: 12,
          background: 'var(--surface)', padding: '4px 12px', borderRadius: 20,
          border: '1px solid var(--border)',
        }}>
          Loading chain…
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} color="var(--border)" />
        <Controls style={{ background: 'var(--surface)', border: '1px solid var(--border)' }} />
        <MiniMap
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          nodeColor={() => 'var(--accent)'}
        />
      </ReactFlow>

      {selected && (
        <NodePanel
          nodeId={selected.id}
          nodeType={selected.nodeType}
          label={selected.label}
          status={selected.status}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
