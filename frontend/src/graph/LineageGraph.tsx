import { useCallback, useEffect, useState, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import ArtifactNode, { type ArtifactNodeData } from './ArtifactNode'
import LineageEdge from './LineageEdge'
import { GraphToolbar, type FilterState } from './GraphToolbar'
import { EventLogDrawer, type LogEntry } from './EventLogDrawer'
import { DatasetInspectorPanel } from '../inspector/DatasetInspectorPanel'
import { ModelInterrogationPanel } from '../interrogation/ModelInterrogationPanel'
import { InferenceEvidencePanel } from '../evidence/InferenceEvidencePanel'
import { AssuranceReport } from '../report/AssuranceReport'
import { getChain, listContributors, tamperModel, WS_URL } from '../shared/api'

const nodeTypes = { artifact: ArtifactNode }
const edgeTypes = { lineage: LineageEdge }

interface ContributorOption {
  id: string
  name: string
}

export default function LineageGraph() {
  const [contributors, setContributors] = useState<ContributorOption[]>([])
  const [selectedContributor, setSelectedContributor] = useState<string | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [filter, setFilter] = useState<FilterState>('all')
  const [zoomPercent, setZoomPercent] = useState<number>(100)
  const [rfInstance, setRfInstance] = useState<any>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])

  const [activeDrillDown, setActiveDrillDown] = useState<{
    id: string
    type: 'dataset' | 'model' | 'inference'
    label: string
  } | null>(null)

  const [showReport, setShowReport] = useState(false)

  const addLog = useCallback((message: string, level: 'info' | 'warn' | 'error' = 'info') => {
    const time = new Date().toTimeString().split(' ')[0]
    setLogs((prev) => [
      { id: Math.random().toString(), timestamp: time, message, level },
      ...prev.slice(0, 49),
    ])
  }, [])

  useEffect(() => {
    listContributors()
      .then((data) => {
        setContributors(data)
        if (data.length > 0 && !selectedContributor) {
          setSelectedContributor(data[0].id)
        }
      })
      .catch(console.error)
  }, [])

  const loadChain = useCallback(async (contributorId: string) => {
    try {
      const data = await getChain(contributorId)

      const colSpacing = 270
      const rowSpacing = 95
      const counts: Record<string, number> = { contributor: 0, dataset: 0, model: 0, inference: 0 }

      const flowNodes: Node[] = data.nodes.map((n: any) => {
        const typeIndex = ['contributor', 'dataset', 'model', 'inference'].indexOf(n.type)
        const row = counts[n.type] || 0
        counts[n.type] = row + 1

        return {
          id: n.id,
          type: 'artifact',
          position: {
            x: Math.max(0, typeIndex) * colSpacing + 40,
            y: row * rowSpacing + 60,
          },
          data: {
            nodeType: n.type,
            label: n.label,
            status: n.status || 'verified',
            hash: n.meta?.sha256 || n.meta?.input_sha256,
            meta: n.meta,
          } as ArtifactNodeData,
        }
      })

      const flowEdges: Edge[] = data.edges.map((e: any, idx: number) => ({
        id: `e-${idx}`,
        source: e.source,
        target: e.target,
        type: 'lineage',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 10,
          height: 10,
          color: 'var(--rule-strong)',
        },
        data: {
          isTampered: false,
        },
      }))

      setNodes(flowNodes)
      setEdges(flowEdges)
      addLog(`Loaded lineage chain (${flowNodes.length} nodes, ${flowEdges.length} edges)`)
    } catch (e) {
      console.error(e)
    }
  }, [setNodes, setEdges, addLog])

  useEffect(() => {
    if (selectedContributor) {
      loadChain(selectedContributor)
    }
  }, [selectedContributor, loadChain])

  useEffect(() => {
    let socket: WebSocket | null = null
    let reconnectTimeout: any = null

    const connect = () => {
      socket = new WebSocket(WS_URL)

      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'ping') return

          if (msg.type === 'node_status') {
            const { id, status, node_type } = msg
            addLog(
              `${node_type ? `[${node_type.toUpperCase()}] ` : ''}Artifact ${id.slice(0, 8)} status → ${status.toUpperCase()}`,
              status === 'tampered' ? 'error' : status === 'suspicious' ? 'warn' : 'info'
            )

            setNodes((prev) => {
              const idx = prev.findIndex((n) => n.id === id)
              if (idx === -1) return prev
              const target = prev[idx]
              if ((target.data as ArtifactNodeData).status === status) return prev

              const next = [...prev]
              next[idx] = {
                ...target,
                data: {
                  ...(target.data as ArtifactNodeData),
                  status,
                },
              }
              return next
            })

            if (status === 'tampered') {
              setEdges((prev) =>
                prev.map((e) => {
                  if (e.source === id || e.target === id) {
                    return {
                      ...e,
                      data: { isTampered: true },
                      markerEnd: {
                        type: MarkerType.ArrowClosed,
                        width: 10,
                        height: 10,
                        color: 'var(--state-tampered)',
                      },
                    }
                  }
                  return e
                })
              )
            }
          }
        } catch {
        }
      }

      socket.onclose = () => {
        reconnectTimeout = setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      socket?.close()
    }
  }, [setNodes, setEdges, addLog])

  const onConnect = useCallback((c: Connection) => setEdges((e) => addEdge(c, e)), [setEdges])

  const onNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    const d = node.data as ArtifactNodeData
    if (d.nodeType === 'contributor') return

    setActiveDrillDown({
      id: node.id,
      type: d.nodeType as 'dataset' | 'model' | 'inference',
      label: d.label,
    })
  }, [])

  const handleTamperDemo = async () => {
    const modelNode = nodes.find((n) => (n.data as ArtifactNodeData).nodeType === 'model')
    if (!modelNode) return

    addLog(`Simulating payload injection on model ${modelNode.id.slice(0, 8)}…`, 'warn')
    try {
      await tamperModel(modelNode.id)
    } catch {
      setNodes((prev) =>
        prev.map((n) =>
          n.id === modelNode.id ? { ...n, data: { ...n.data, status: 'tampered' } } : n
        )
      )
    }
  }

  const styledNodes = useMemo(() => {
    if (filter === 'all') return nodes

    return nodes.map((n) => {
      const d = n.data as ArtifactNodeData
      const s = (d.status || 'pending').toLowerCase()

      let match = false
      if (filter === 'verified' && (s === 'verified' || s === 'ok' || s === 'clean')) match = true
      if (filter === 'suspicious' && (s === 'suspicious' || s === 'flagged')) match = true
      if (filter === 'tampered' && (s === 'tampered' || s === 'mismatch')) match = true

      return {
        ...n,
        style: {
          ...n.style,
          opacity: match || d.nodeType === 'contributor' ? 1 : 0.15,
          transition: 'opacity 0.2s',
        },
      }
    })
  }, [nodes, filter])

  const activeContributorName =
    contributors.find((c) => c.id === selectedContributor)?.name || 'VISENTRA Chain'

  return (
    <div style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-sunken)' }}>
      <GraphToolbar
        contributors={contributors}
        selectedContributorId={selectedContributor}
        onSelectContributor={(id) => setSelectedContributor(id)}
        currentFilter={filter}
        onFilterChange={(f) => setFilter(f)}
        zoomPercent={zoomPercent}
        onZoomIn={() => rfInstance?.zoomIn({ duration: 200 })}
        onZoomOut={() => rfInstance?.zoomOut({ duration: 200 })}
        onFitView={() => rfInstance?.fitView({ padding: 0.2, duration: 200 })}
        onTamperDemo={handleTamperDemo}
        onOpenReport={() => setShowReport(true)}
      />

      <div style={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={styledNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onInit={(instance) => {
            setRfInstance(instance)
            instance.fitView({ padding: 0.2 })
          }}
          onMoveEnd={(_event, viewport) => {
            setZoomPercent(Math.round(viewport.zoom * 100))
          }}
          proOptions={{ hideAttribution: true }}
          minZoom={0.2}
          maxZoom={2}
        >
          <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--rule)" />
        </ReactFlow>

        <EventLogDrawer logs={logs} onClear={() => setLogs([])} />
      </div>

      {activeDrillDown?.type === 'dataset' && (
        <DatasetInspectorPanel
          datasetId={activeDrillDown.id}
          datasetLabel={activeDrillDown.label}
          onClose={() => setActiveDrillDown(null)}
          onStatusChanged={(s) => {
            setNodes((prev) =>
              prev.map((n) => (n.id === activeDrillDown.id ? { ...n, data: { ...n.data, status: s } } : n))
            )
          }}
        />
      )}

      {activeDrillDown?.type === 'model' && (
        <ModelInterrogationPanel
          modelId={activeDrillDown.id}
          modelLabel={activeDrillDown.label}
          onClose={() => setActiveDrillDown(null)}
          onStatusChanged={(s) => {
            setNodes((prev) =>
              prev.map((n) => (n.id === activeDrillDown.id ? { ...n, data: { ...n.data, status: s } } : n))
            )
          }}
        />
      )}

      {activeDrillDown?.type === 'inference' && (
        <InferenceEvidencePanel
          inferenceId={activeDrillDown.id}
          onClose={() => setActiveDrillDown(null)}
          onStatusChanged={(s) => {
            setNodes((prev) =>
              prev.map((n) => (n.id === activeDrillDown.id ? { ...n, data: { ...n.data, status: s } } : n))
            )
          }}
        />
      )}

      {showReport && selectedContributor && (
        <AssuranceReport
          contributorId={selectedContributor}
          contributorName={activeContributorName}
          onClose={() => setShowReport(false)}
        />
      )}
    </div>
  )
}
