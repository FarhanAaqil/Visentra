import { Suspense, lazy, useEffect, useState } from 'react'
import { FileCheck2, Network, Plus, ScrollText, Wifi, WifiOff } from 'lucide-react'
import { StoreProvider, useStore } from './lib/store'
import LineageView from './views/LineageView'
import type { Selection } from './views/LineageView'
import ReportView from './views/ReportView'
import AuditView from './views/AuditView'
import DatasetPanel from './panels/DatasetPanel'
import ModelPanel from './panels/ModelPanel'
import InferencePanel from './panels/InferencePanel'
import IngestDrawer from './panels/IngestDrawer'
import { Toasts } from './ui/kit'

// Three.js is the heaviest dependency; load it after the UI is interactive.
const CinemaBackdrop = lazy(() => import('./scene/CinemaBackdrop'))

type View = 'lineage' | 'report' | 'audit'

const VIEWS: Array<[View, string, typeof Network]> = [
  ['lineage', 'Lineage', Network],
  ['report', 'Assurance', FileCheck2],
  ['audit', 'Audit trail', ScrollText],
]

function fromHash(): { view: View; selected: Selection | null } {
  const [key, id] = window.location.hash.slice(1).split('=')
  if (id && (key === 'dataset' || key === 'model' || key === 'inference')) return { view: 'lineage', selected: { type: key, id } }
  if (key === 'report' || key === 'audit') return { view: key, selected: null }
  return { view: 'lineage', selected: null }
}

function Shell() {
  const { contributors, contributorId, setContributorId, connected, mood } = useStore()
  const [view, setView] = useState<View>(() => fromHash().view)
  const [selected, setSelected] = useState<Selection | null>(() => fromHash().selected)

  // Deep links: #report, #audit, #model=<id>, #dataset=<id>, #inference=<id>
  useEffect(() => {
    const next = selected ? `#${selected.type}=${selected.id}` : view === 'lineage' ? '' : `#${view}`
    if (window.location.hash !== next) history.replaceState(null, '', next || window.location.pathname)
  }, [view, selected])
  const [ingest, setIngest] = useState(false)
  const close = () => setSelected(null)

  return (
    <div className="app">
      <Suspense fallback={null}>
        <CinemaBackdrop mood={mood} />
      </Suspense>

      <header className="topbar glass">
        <div className="brand">
          <div className="brand-mark">V</div>
          <div>
            <div className="serif" style={{ fontSize: 20, fontWeight: 700, lineHeight: 1 }}>Visentra</div>
            <div className="mono faint" style={{ fontSize: 9.5, letterSpacing: '0.14em' }}>FROM DATA TO DECISION</div>
          </div>
        </div>

        <nav className="tabs" aria-label="Views">
          {VIEWS.map(([v, label, Icon]) => (
            <button key={v} className={`tab ${view === v ? 'active' : ''}`} onClick={() => setView(v)}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </nav>

        <div className="grow" />

        <select
          className="input"
          aria-label="Contributor"
          style={{ width: 'auto', minWidth: 170, borderRadius: 999, padding: '7px 12px' }}
          value={contributorId ?? ''}
          onChange={(e) => {
            setSelected(null)
            setContributorId(e.target.value)
          }}
        >
          {!contributors.length && <option value="">No contributors yet</option>}
          {contributors.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <span className={`pill ${connected ? 'st-ok' : 'st-idle'}`} title={connected ? 'Live updates connected' : 'Reconnecting to live feed'}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          {connected ? 'live' : 'offline'}
        </span>

        <button className="btn btn-primary" onClick={() => setIngest(true)}>
          <Plus size={15} /> Ingest
        </button>
      </header>

      <main className="main">
        {view === 'lineage' && <LineageView selected={selected} onSelect={setSelected} />}
        {view === 'report' && <ReportView />}
        {view === 'audit' && <AuditView />}
      </main>

      {selected?.type === 'dataset' && <DatasetPanel id={selected.id} onClose={close} />}
      {selected?.type === 'model' && <ModelPanel id={selected.id} onClose={close} />}
      {selected?.type === 'inference' && <InferencePanel id={selected.id} onClose={close} />}
      {ingest && <IngestDrawer onClose={() => setIngest(false)} />}
      <Toasts />
    </div>
  )
}

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  )
}
