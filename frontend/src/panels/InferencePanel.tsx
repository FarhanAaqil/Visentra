import { useState } from 'react'
import { Download, KeyRound, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { download, pct } from '../lib/format'
import type { ReverifyResult } from '../lib/types'
import { Bar, Check, Hash, Sheet, Spinner, StatusPill } from '../ui/kit'
import { useAction } from '../lib/useAction'

export default function InferencePanel({ id, onClose }: { id: string; onClose: () => void }) {
  const { refresh, revision } = useStore()
  const { busy, run } = useAction()
  const inf = useAsync(() => api.inference(id), [id, revision])
  const [result, setResult] = useState<ReverifyResult | null>(null)
  const i = inf.data

  const actions = (
    <>
      <button
        className="btn btn-primary"
        disabled={!!busy}
        onClick={() =>
          run('reverify', () => api.reverify(id), (r) => {
            setResult(r)
            void refresh()
            return r.status === 'ok' ? 'Signature and every binding verified' : `Certificate broken: ${r.diffs[0] ?? 'mismatch'}`
          })
        }
      >
        {busy === 'reverify' ? <Spinner /> : <ShieldCheck size={15} />} Re-verify certificate
      </button>
      <button className="btn" disabled={!!busy} onClick={() => run('evidence', () => api.evidence(id), (e) => {
        download(`inference-${id.slice(0, 8)}.json`, e)
        return 'Evidence exported'
      })}>
        <Download size={15} /> Export evidence
      </button>
    </>
  )

  return (
    <Sheet eyebrow="Pillar IV · Signed inference" title={i ? `Inference ${i.id.slice(0, 8)}` : 'Inference'} onClose={onClose} actions={actions}>
      {!i ? (
        <div className="skeleton" style={{ height: 140 }} />
      ) : (
        <>
          <div className="row wrap" style={{ gap: 10 }}>
            <StatusPill status={i.status} label={i.status === 'ok' ? 'certificate valid' : 'certificate broken'} />
            <span className="dim">{new Date(i.timestamp).toLocaleString()}</span>
          </div>

          {i.output && (
            <section className="card" style={{ padding: 16 }}>
              <div className="row between" style={{ alignItems: 'flex-end' }}>
                <div>
                  <div className="eyebrow">Prediction</div>
                  <div className="serif" style={{ fontSize: 34, fontWeight: 700 }}>class {i.output.top_class}</div>
                </div>
                <div className="serif" style={{ fontSize: 26, fontWeight: 700, color: '#fb7185' }}>{pct(i.output.top_confidence, 1)}</div>
              </div>
              <div className="col stagger" style={{ marginTop: 12, gap: 8 }}>
                {i.output.top_5.map((c) => (
                  <div key={c.class} className="row" style={{ gap: 10 }}>
                    <span className="mono" style={{ width: 64, fontSize: 11.5 }}>class {c.class}</span>
                    <div className="grow"><Bar value={c.prob} /></div>
                    <span className="mono" style={{ width: 54, textAlign: 'right', fontSize: 11.5 }}>{pct(c.prob, 1)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="card" style={{ padding: 16 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Bound provenance tuple</div>
            <div className="ledger">
              <div>Dataset root</div>
              <div><Hash value={i.dataset_merkle_root} label="dataset Merkle root" /></div>
              <div>Model SHA-256</div>
              <div><Hash value={i.model_sha256} label="model hash" /></div>
              <div>Topology</div>
              <div><Hash value={i.arch_fingerprint} label="arch fingerprint" /></div>
              <div>Input SHA-256</div>
              <div><Hash value={i.input_sha256} label="input hash" /></div>
              <div>Config SHA-256</div>
              <div><Hash value={i.config_sha256} label="config hash" /></div>
              <div>Timestamp</div>
              <div className="mono" style={{ fontSize: 11.5 }}>{i.timestamp}</div>
            </div>
          </section>

          <section className="card" style={{ padding: 16 }}>
            <div className="row" style={{ gap: 8, marginBottom: 8 }}>
              <KeyRound size={15} color="#fb7185" />
              <span className="eyebrow">Ed25519 signature · key {i.key_id ?? '—'}</span>
            </div>
            <Hash value={i.signature} label="signature" />
          </section>

          {result && (
            <section className="card col" style={{ padding: 16, gap: 10 }}>
              <div className="eyebrow">Re-verification</div>
              <Check ok={result.checks.signature_valid} label="Signature over the recorded tuple" />
              <Check ok={result.checks.record_matches_evidence} label="Database record matches the evidence file" />
              <Check ok={result.checks.model_hash_match} label="Model on disk matches the bound hash" />
              <Check ok={result.checks.input_hash_match} label="Stored input still hashes to the bound digest" />
              <Check ok={result.checks.dataset_root_match} label="Training dataset still matches its Merkle root" detail={result.checks.dataset_root_match === null ? 'model has no linked dataset' : undefined} />
              {result.diffs.map((d) => (
                <div key={d} className="mono" style={{ fontSize: 11.5, color: 'var(--bad)' }}>✕ {d}</div>
              ))}
            </section>
          )}
        </>
      )}
    </Sheet>
  )
}
