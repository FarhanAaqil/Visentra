import React, { useState, useEffect } from 'react'
import { createContributor, listContributors, uploadDataset, uploadModel } from '../shared/api'

interface Contributor { id: string; name: string }

interface Props {
  onSelect: (id: string) => void
  selected: string | null
}

export default function Sidebar({ onSelect, selected }: Props) {
  const [contributors, setContributors] = useState<Contributor[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [dsFile, setDsFile] = useState<File | null>(null)
  const [mdlFile, setMdlFile] = useState<File | null>(null)
  const [dsVer, setDsVer] = useState('1.0')
  const [mdlVer, setMdlVer] = useState('1.0')

  const refresh = () => listContributors().then(setContributors)
  useEffect(() => { refresh() }, [])

  const addContributor = async () => {
    if (!name.trim()) return
    setBusy(true)
    await createContributor(name.trim())
    setName('')
    await refresh()
    setBusy(false)
  }

  const upload = async (type: 'dataset' | 'model') => {
    if (!selected) return alert('Select a contributor first')
    const file = type === 'dataset' ? dsFile : mdlFile
    const ver = type === 'dataset' ? dsVer : mdlVer
    if (!file) return alert('Choose a file first')
    setBusy(true)
    try {
      if (type === 'dataset') await uploadDataset(selected, ver, file)
      else await uploadModel(selected, ver, file)
    } catch (e: unknown) {
      alert(`Upload failed: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside style={{
      width: 260, minWidth: 260, background: 'var(--surface)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', padding: 16, gap: 16, overflowY: 'auto',
    }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Contributors
      </h2>

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addContributor()}
          placeholder="Name…"
          style={inputStyle}
        />
        <button onClick={addContributor} disabled={busy} style={btnStyle}>+</button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {contributors.map(c => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            style={{
              ...btnStyle,
              textAlign: 'left',
              background: selected === c.id ? 'var(--accent)' : 'var(--surface2)',
              color: selected === c.id ? '#fff' : 'var(--text)',
              fontWeight: selected === c.id ? 600 : 400,
            }}
          >
            👤 {c.name}
          </button>
        ))}
      </div>

      {selected && (
        <>
          <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />
          <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Upload Dataset
          </h2>
          <input style={inputStyle} placeholder="Version" value={dsVer} onChange={e => setDsVer(e.target.value)} />
          <input type="file" onChange={e => setDsFile(e.target.files?.[0] ?? null)} style={{ color: 'var(--text-dim)', fontSize: 12 }} />
          <button onClick={() => upload('dataset')} disabled={busy} style={btnStyle}>Upload Dataset</button>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />
          <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Upload Model
          </h2>
          <input style={inputStyle} placeholder="Version" value={mdlVer} onChange={e => setMdlVer(e.target.value)} />
          <input type="file" accept=".onnx,.pt,.pth" onChange={e => setMdlFile(e.target.files?.[0] ?? null)} style={{ color: 'var(--text-dim)', fontSize: 12 }} />
          <button onClick={() => upload('model')} disabled={busy} style={btnStyle}>Upload Model</button>
        </>
      )}
    </aside>
  )
}

const inputStyle: React.CSSProperties = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 13,
  width: '100%',
  outline: 'none',
}

const btnStyle: React.CSSProperties = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '6px 12px',
  color: 'var(--text)',
  fontSize: 13,
  cursor: 'pointer',
  width: '100%',
  transition: 'background 0.15s',
}
