import React, { useCallback, useEffect, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  Node,
  Edge,
  Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import LineageNode, { LineageNodeData } from './LineageNode'
import { getChain } from '../shared/api'
import { useStatusSocket } from '../shared/useStatusSocket'

const nodeTypes = { lineage: LineageNode }

interface Props {
  contributorId: string | null
}

function toFlowNode(n: { id: string; type: string; label: string; status?: string; meta?: Record<string, string> }, index: number): Node {
  return {
    id: n.id,
    type: 'lineage',
    position: { x: (['contributor', 'dataset', 'model', 'inference'].indexOf(n.type)) * 240, y: index * 90 },
    data: { nodeType: n.type, label: n.label, status: n.status, meta: n.meta } as LineageNodeData,
  }
}

export default function LineageGraph({ contributorId }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [loading, setLoading] = useState(false)

  const onConnect = useCallback((c: Connection) => setEdges(e => addEdge(c, e)), [setEdges])

  const loadChain = useCallback(async () => {
    if (!contributorId) return
    setLoading(true)
    try {
      const data = await getChain(contributorId)
      setNodes(data.nodes.map((n: { id: string; type: string; label: string; status?: string; meta?: Record<string, string> }, i: number) => toFlowNode(n, i)))
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

  useEffect(() => { loadChain() }, [loadChain])

  // Live WebSocket updates — patch the affected node's status in-place
  useStatusSocket((msg) => {
    const { id, status } = msg as { id: string; status: string }
    if (!id || !status) return
    setNodes(prev =>
      prev.map(n =>
        n.id === id
          ? { ...n, data: { ...n.data, status } }
          : n
      )
    )
  })

  if (!contributorId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)' }}>
        Select or create a contributor to view its lineage graph.
      </div>
    )
  }

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      {loading && (
        <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 10, color: 'var(--text-dim)', fontSize: 12 }}>
          Loading chain…
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
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
    </div>
  )
}
