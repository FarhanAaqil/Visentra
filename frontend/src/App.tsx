import React, { useState } from 'react'
import LineageGraph from './graph/LineageGraph'
import Sidebar from './graph/Sidebar'

export default function App() {
  const [selectedContributor, setSelectedContributor] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48,
        background: 'var(--surface)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', paddingLeft: 20, gap: 12, zIndex: 100,
      }}>
        <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.5, color: 'var(--text)' }}>
          VISENTRA
        </span>
        <span style={{
          fontSize: 11, background: 'var(--accent)', color: '#fff',
          padding: '2px 8px', borderRadius: 20, fontWeight: 600, letterSpacing: 0.5,
        }}>
          SIH26228
        </span>
        <span style={{ marginLeft: 'auto', paddingRight: 20, fontSize: 12, color: 'var(--muted)' }}>
          From Data to Decision — Proving AI Integrity
        </span>
      </div>

      {/* Layout below header */}
      <div style={{ display: 'flex', flex: 1, paddingTop: 48, overflow: 'hidden' }}>
        <Sidebar onSelect={setSelectedContributor} selected={selectedContributor} />
        <main style={{ flex: 1, height: '100%' }}>
          <LineageGraph contributorId={selectedContributor} />
        </main>
      </div>
    </div>
  )
}
