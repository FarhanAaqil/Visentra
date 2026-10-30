import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  Position,
  ReactFlow,
  getBezierPath,
} from '@xyflow/react'
import type { Edge, EdgeProps, Node, NodeChange, NodeProps, ReactFlowInstance, XYPosition } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Cpu, Database, Fingerprint, Network, User } from 'lucide-react'
import { useStore } from '../lib/store'
import { TONE_COLOR, scoreColor, short, tone } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { api } from '../lib/api'
import { Empty, Ring, StatusPill } from '../ui/kit'
import type { ChainNode } from '../lib/types'

export interface Selection {
  type: ChainNode['type']
  id: string
}

type ArtifactData = { node: ChainNode; selected: boolean; flashing: boolean }

const ICONS = { contributor: User, dataset: Database, model: Cpu, inference: Fingerprint }
const TIER_NAMES = ['Contributor', 'Dataset', 'Model', 'Inference']

function subtitle(n: ChainNode): string {
  const m = n.meta as Record<string, string | number | boolean | null>
  switch (n.type) {
    case 'contributor':
      return String(m.role ?? 'Contributor')
    case 'dataset':
      return `${m.sample_count ?? 0} samples · root ${short(m.merkle_root as string, 8)}`
    case 'model':
      return `${m.framework} · ${short(m.sha256 as string, 10)}`
    case 'inference':
      return `class ${m.top_class ?? '?'} · ${typeof m.confidence === 'number' ? (m.confidence * 100).toFixed(0) : '?'}% · ${m.signed ? 'signed' : 'unsigned'}`
  }
}

const ArtifactNode = memo(function ArtifactNode({ data }: NodeProps<Node<ArtifactData>>) {
  const { node, selected, flashing } = data
  const Icon = ICONS[node.type]
  const t = tone(node.status)
  return (
    <div className={`node glow-${t} ${selected ? 'selected' : ''} ${flashing ? 'flash' : ''}`}>
      {node.type !== 'contributor' && <Handle type="target" position={Position.Left} />}
      <div className="row" style={{ gap: 10 }}>
        <div className="node-icon" style={{ color: TONE_COLOR[t], borderColor: `${TONE_COLOR[t]}66` }}>
          <Icon size={16} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="eyebrow" style={{ fontSize: 9, color: 'var(--rose-dim)' }}>{TIER_NAMES[node.tier]}</div>
          <div style={{ fontWeight: 700, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {node.label}
          </div>
        </div>
      </div>
      <div className="mono dim" style={{ fontSize: 10.5, marginTop: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {subtitle(node)}
      </div>
      <div style={{ marginTop: 8 }}>
        <StatusPill status={node.status} />
      </div>
      {node.type !== 'inference' && <Handle type="source" position={Position.Right} />}
    </div>
  )
})

type FlowEdgeData = { tone: 'ok' | 'warn' | 'bad' | 'idle' }

function FlowEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<Edge<FlowEdgeData>>) {
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
  const color = TONE_COLOR[data?.tone ?? 'idle']
  const bad = data?.tone === 'bad'
  return (
    <>
      <BaseEdge id={id} path={path} style={{ stroke: color, strokeOpacity: 0.25, strokeWidth: bad ? 5 : 3 }} />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={bad ? 2.4 : 1.6}
        strokeDasharray="6 6"
        style={{ animation: `dash ${bad ? 0.35 : 1.1}s linear infinite`, filter: `drop-shadow(0 0 4px ${color})` }}
      />
      <circle r={bad ? 4 : 3} fill={color} style={{ filter: `drop-shadow(0 0 6px ${color})` }}>
        <animateMotion dur={bad ? '0.9s' : '2.6s'} repeatCount="indefinite" path={path} />
      </circle>
    </>
  )
}

const nodeTypes = { artifact: ArtifactNode }
const edgeTypes = { flow: FlowEdge }

function PulseStrip() {
  const { contributorId, revision } = useStore()
  const { data } = useAsync(() => (contributorId ? api.report(contributorId) : Promise.resolve(null)), [contributorId, revision])
  if (!data) return null
  return (
    <div className="glass row wrap stagger" style={{ padding: '12px 16px', gap: 18, flexShrink: 0 }}>
      <Ring value={data.score.overall} size={74} stroke={7} />
      <div style={{ minWidth: 180 }}>
        <div className="eyebrow">Assurance · grade {data.grade}</div>
        <div className="serif" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{data.contributor_name}</div>
        <div className="dim" style={{ fontSize: 12, maxWidth: 320 }}>{data.summary}</div>
      </div>
      <div className="grow row wrap" style={{ gap: 18, justifyContent: 'flex-end' }}>
        {data.pillars.map((p) => (
          <div key={p.key} style={{ minWidth: 120 }}>
            <div className="mono dim" style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase' }}>{p.label}</div>
            <div className="serif" style={{ fontSize: 22, fontWeight: 700, color: scoreColor(p.score) }}>{p.score.toFixed(1)}</div>
            <div className="bar" style={{ marginTop: 4 }}>
              <i style={{ width: `${p.score}%`, background: scoreColor(p.score) }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function LineageView({ selected, onSelect }: { selected: Selection | null; onSelect: (s: Selection) => void }) {
  const { chain, chainError, flashing } = useStore()

  // React Flow forgets a node's measured size whenever it receives a fresh node object,
  // and nothing re-measures a node whose size did not change, so it would stay hidden.
  // Keep sizes and drag positions here and hand them back on every rebuild.
  const [sizes, setSizes] = useState<Record<string, { width: number; height: number }>>({})
  const [moved, setMoved] = useState<Record<string, XYPosition>>({})
  const onNodesChange = useCallback((changes: NodeChange[]) => {
    const dims: Record<string, { width: number; height: number }> = {}
    const pos: Record<string, XYPosition> = {}
    for (const c of changes) {
      if (c.type === 'dimensions' && c.dimensions) dims[c.id] = c.dimensions
      if (c.type === 'position' && c.position) pos[c.id] = c.position
    }
    if (Object.keys(dims).length) setSizes((s) => ({ ...s, ...dims }))
    if (Object.keys(pos).length) setMoved((m) => ({ ...m, ...pos }))
  }, [])

  // Refit whenever the canvas changes shape (strip wrapping, phone rotation) or the graph grows.
  const flow = useRef<ReactFlowInstance<Node<ArtifactData>, Edge<FlowEdgeData>> | null>(null)
  const canvas = useRef<HTMLDivElement>(null)
  const nodeCount = chain?.nodes.length ?? 0
  useEffect(() => {
    const el = canvas.current
    if (!el) return
    const refit = () => void flow.current?.fitView({ padding: 0.35, duration: 350 })
    const observer = new ResizeObserver(refit)
    observer.observe(el)
    const t = setTimeout(refit, 120)
    return () => {
      observer.disconnect()
      clearTimeout(t)
    }
  }, [nodeCount])

  const { nodes, edges } = useMemo(() => {
    if (!chain) return { nodes: [] as Node<ArtifactData>[], edges: [] as Edge<FlowEdgeData>[] }
    const byTier: ChainNode[][] = [[], [], [], []]
    chain.nodes.forEach((n) => byTier[n.tier].push(n))
    const gapY = 150
    const nodes: Node<ArtifactData>[] = []
    byTier.forEach((tier, t) => {
      tier.forEach((n, i) => {
        nodes.push({
          id: n.id,
          type: 'artifact',
          position: moved[n.id] ?? { x: t * 320, y: (i - (tier.length - 1) / 2) * gapY },
          measured: sizes[n.id],
          data: { node: n, selected: selected?.id === n.id, flashing: flashing.has(n.id) },
        })
      })
    })
    const status = new Map(chain.nodes.map((n) => [n.id, n.status]))
    const edges: Edge<FlowEdgeData>[] = chain.edges.map((e) => {
      const ts = [tone(status.get(e.source)), tone(status.get(e.target))]
      const t = ts.includes('bad') ? 'bad' : ts.includes('warn') ? 'warn' : ts[1]
      return { id: e.id, source: e.source, target: e.target, type: 'flow', data: { tone: t } }
    })
    return { nodes, edges }
  }, [chain, selected, flashing, sizes, moved])

  if (chainError && !chain) {
    return (
      <div className="view glass" style={{ display: 'grid', placeItems: 'center' }}>
        <Empty icon={<Network size={38} />} title="Can't reach the lineage service">{chainError}</Empty>
      </div>
    )
  }

  return (
    <div className="view col" style={{ gap: 12 }}>
      <PulseStrip />
      <div ref={canvas} className="glass canvas" style={{ position: 'relative', overflow: 'hidden', flex: 1, minHeight: 320 }}>
      {chain && chain.nodes.length <= 1 && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', zIndex: 4, pointerEvents: 'none' }}>
          <Empty icon={<Network size={38} />} title="An empty supply chain">
            Use <b>Ingest</b> to upload a dataset archive, register a model trained on it and run a signed inference.
          </Empty>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.35 }}
        minZoom={0.3}
        maxZoom={1.6}
        nodesConnectable={false}
        nodesDraggable
        onNodesChange={onNodesChange}
        onInit={(instance) => {
          flow.current = instance
        }}
        onNodeClick={(_, n) => onSelect({ type: (n.data as ArtifactData).node.type, id: n.id })}
        proOptions={{ hideAttribution: true }}
        style={{ background: 'transparent' }}
      >
        <Background color="rgba(250,212,219,0.12)" gap={28} size={1.2} />
        <Controls position="bottom-left" showInteractive={false} />
      </ReactFlow>
      </div>
    </div>
  )
}
