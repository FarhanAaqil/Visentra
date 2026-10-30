import { useState } from 'react'
import type { ReactNode } from 'react'
import { Cpu, Database, Fingerprint, UploadCloud, User } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { Sheet, Spinner } from '../ui/kit'
import { useAction } from '../lib/useAction'

type Kind = 'contributor' | 'dataset' | 'model' | 'inference'

function Drop({ file, onFile, accept, hint }: { file: File | null; onFile: (f: File) => void; accept: string; hint: string }) {
  const [over, setOver] = useState(false)
  return (
    <label
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const f = e.dataTransfer.files[0]
        if (f) onFile(f)
      }}
      className="card col"
      style={{
        alignItems: 'center', padding: '26px 16px', gap: 8, cursor: 'pointer', textAlign: 'center',
        borderStyle: 'dashed', borderColor: over ? 'var(--crimson-hot)' : 'var(--line-strong)',
        background: over ? 'rgba(225,29,72,0.12)' : undefined, transition: 'all 200ms',
      }}
    >
      <UploadCloud size={28} color="#fb7185" />
      <div style={{ fontWeight: 600 }}>{file ? file.name : 'Drop a file or click to browse'}</div>
      <div className="dim" style={{ fontSize: 12 }}>{file ? `${(file.size / 1024).toFixed(1)} KB` : hint}</div>
      <input type="file" accept={accept} hidden onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
    </label>
  )
}

export default function IngestDrawer({ onClose, initial = 'dataset' }: { onClose: () => void; initial?: Kind }) {
  const { contributorId, setContributorId, reloadContributors, refresh, revision } = useStore()
  const { busy, run } = useAction()
  const [kind, setKind] = useState<Kind>(contributorId ? initial : 'contributor')
  const [name, setName] = useState('')
  const [role, setRole] = useState('ML Engineer')
  const [version, setVersion] = useState('1.0')
  const [file, setFile] = useState<File | null>(null)
  const [datasetId, setDatasetId] = useState('')
  const [modelId, setModelId] = useState('')
  const [config, setConfig] = useState('{"precision": "fp32"}')

  const datasets = useAsync(() => (contributorId ? api.datasets(contributorId) : Promise.resolve([])), [contributorId, revision])
  const models = useAsync(() => (contributorId ? api.models(contributorId) : Promise.resolve([])), [contributorId, revision])

  const pick = (k: Kind) => {
    setKind(k)
    setFile(null)
  }

  const submit = async () => {
    if (kind === 'contributor') {
      const c = await run('go', () => api.createContributor(name.trim(), role), (c) => `Contributor ${c.name} registered`)
      if (c) {
        await reloadContributors()
        setContributorId(c.id)
        setName('')
        pick('dataset')
      }
      return
    }
    if (!contributorId) return
    if (kind === 'dataset' && file) {
      const d = await run('go', () => api.uploadDataset(contributorId, version, file), (d) => `Unpacked ${d.sample_count} samples and sealed a Merkle root`)
      if (d) {
        await refresh()
        setDatasetId(d.id)
        pick('model')
      }
    }
    if (kind === 'model' && file) {
      const m = await run('go', () => api.uploadModel(contributorId, version, file, datasetId || undefined), (m) => `Model registered · topology ${m.arch_fingerprint?.slice(0, 10)}`)
      if (m) {
        await refresh()
        setModelId(m.id)
        pick('inference')
      }
    }
    if (kind === 'inference' && file && modelId) {
      const i = await run('go', () => api.runInference(modelId, file, config), (i) => `Signed inference: class ${i.output?.top_class}`)
      if (i) await refresh()
    }
  }

  const ready =
    kind === 'contributor' ? name.trim().length > 0 : kind === 'inference' ? !!file && !!modelId && !!contributorId : !!file && !!contributorId

  const tabs: Array<[Kind, string, ReactNode]> = [
    ['contributor', 'Contributor', <User key="u" size={14} />],
    ['dataset', 'Dataset', <Database key="d" size={14} />],
    ['model', 'Model', <Cpu key="m" size={14} />],
    ['inference', 'Inference', <Fingerprint key="i" size={14} />],
  ]

  return (
    <Sheet eyebrow="Ingest artifact" title="Add to the supply chain" onClose={onClose} narrow>
      <div className="tabs" style={{ flexWrap: 'wrap', borderRadius: 18 }}>
        {tabs.map(([k, label, icon]) => (
          <button key={k} className={`tab ${kind === k ? 'active' : ''}`} onClick={() => pick(k)} disabled={k !== 'contributor' && !contributorId}>
            {icon} {label}
          </button>
        ))}
      </div>

      {kind === 'contributor' && (
        <>
          <div className="field">
            <label htmlFor="c-name">Name</label>
            <input id="c-name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Annotation vendor A" />
          </div>
          <div className="field">
            <label htmlFor="c-role">Role</label>
            <input id="c-role" className="input" value={role} onChange={(e) => setRole(e.target.value)} />
          </div>
        </>
      )}

      {(kind === 'dataset' || kind === 'model') && (
        <div className="field">
          <label htmlFor="ver">Version</label>
          <input id="ver" className="input" value={version} onChange={(e) => setVersion(e.target.value)} />
        </div>
      )}

      {kind === 'dataset' && (
        <Drop file={file} onFile={setFile} accept=".zip,.tar,.tgz,.gz,image/*" hint="ZIP or TAR of images, or a single image. Every image is hashed, pHashed and Merkle sealed." />
      )}

      {kind === 'model' && (
        <>
          <div className="field">
            <label htmlFor="parent">Trained on</label>
            <select id="parent" className="input" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
              <option value="">No parent dataset</option>
              {(datasets.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>Dataset v{d.version} · {d.sample_count} samples · {d.status}</option>
              ))}
            </select>
          </div>
          <Drop file={file} onFile={setFile} accept=".onnx,.pt,.pth,.safetensors" hint="ONNX is inspected and executed in the sandbox. Pickle formats are hash-tracked only." />
        </>
      )}

      {kind === 'inference' && (
        <>
          <div className="field">
            <label htmlFor="model">Model</label>
            <select id="model" className="input" value={modelId} onChange={(e) => setModelId(e.target.value)}>
              <option value="">Choose a model</option>
              {(models.data ?? []).map((m) => (
                <option key={m.id} value={m.id} disabled={m.status === 'tampered'}>
                  Model v{m.version} · {m.status}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cfg">Runtime config (JSON, hashed into the certificate)</label>
            <textarea id="cfg" className="input mono" rows={3} value={config} onChange={(e) => setConfig(e.target.value)} />
          </div>
          <Drop file={file} onFile={setFile} accept="image/*" hint="The input is stored content-addressed and bound into the signed tuple." />
        </>
      )}

      <button className="btn btn-primary" style={{ padding: '12px 18px' }} disabled={!ready || !!busy} onClick={() => void submit()}>
        {busy ? <Spinner /> : <UploadCloud size={16} />}
        {kind === 'contributor' ? 'Register contributor' : kind === 'inference' ? 'Run & sign inference' : `Upload ${kind}`}
      </button>
    </Sheet>
  )
}
