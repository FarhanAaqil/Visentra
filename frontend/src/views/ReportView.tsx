import { useState } from 'react'
import { BadgeCheck, Cpu, Database, Download, FileCheck2, Fingerprint, Radar, ShieldAlert } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { download, scoreColor } from '../lib/format'
import type { Pillar } from '../lib/types'
import { Check, Empty, Ring, Spinner } from '../ui/kit'
import { useAction } from '../lib/useAction'

const PILLAR_ICON = {
  dataset_integrity: Database,
  model_integrity: Cpu,
  backdoor_screening: Radar,
  inference_binding: Fingerprint,
}

function PillarCard({ p, n }: { p: Pillar; n: number }) {
  const Icon = PILLAR_ICON[p.key]
  return (
    <div className="glass col" style={{ padding: 18, gap: 12 }}>
      <div className="row between">
        <div className="row" style={{ gap: 8 }}>
          <div className="node-icon"><Icon size={15} /></div>
          <div>
            <div className="eyebrow" style={{ fontSize: 9.5 }}>Pillar {['I', 'II', 'III', 'IV'][n]} · weight {(p.weight * 100).toFixed(0)}%</div>
            <div style={{ fontWeight: 700 }}>{p.label}</div>
          </div>
        </div>
        {!p.assessed && <span className="pill st-idle">not assessed</span>}
      </div>
      <div className="row" style={{ gap: 14 }}>
        <Ring value={p.score} size={96} stroke={8} />
        <div className="dim" style={{ fontSize: 12.5, lineHeight: 1.5 }}>{p.explanation}</div>
      </div>
    </div>
  )
}

export default function ReportView() {
  const { contributorId, revision } = useStore()
  const { busy, run } = useAction()
  const report = useAsync(() => (contributorId ? api.report(contributorId) : Promise.resolve(null)), [contributorId, revision])
  const [check, setCheck] = useState<{ signature_valid: boolean; trusted_key: boolean; key_id: string | null } | null>(null)
  const r = report.data

  if (!contributorId) return <div className="view glass"><Empty icon={<FileCheck2 size={36} />} title="No contributor selected" /></div>
  if (!r) return <div className="view"><div className="skeleton" style={{ height: 260 }} /></div>

  const verifyFile = async (file: File) => {
    const envelope = JSON.parse(await file.text())
    await run('check', () => api.verifyCertificate(envelope), (res) => {
      setCheck(res)
      return res.signature_valid && res.trusted_key ? 'Certificate is authentic' : 'Certificate failed verification'
    })
  }

  return (
    <div className="view scroll col" style={{ gap: 14, paddingRight: 4 }}>
      <section className="glass row wrap" style={{ padding: 24, gap: 28 }}>
        <Ring value={r.score.overall} size={190} stroke={14} label="overall" />
        <div className="grow col" style={{ gap: 8, minWidth: 260 }}>
          <div className="eyebrow">Four-pillar assurance report</div>
          <div className="serif" style={{ fontSize: 40, fontWeight: 700, lineHeight: 1.05 }}>
            {r.contributor_name}{' '}
            <span style={{ color: scoreColor(r.score.overall), textShadow: `0 0 30px ${scoreColor(r.score.overall)}` }}>{r.grade}</span>
          </div>
          <div className="dim" style={{ fontSize: 15, maxWidth: 560 }}>{r.summary}</div>
          <div className="mono faint" style={{ fontSize: 11 }}>
            S = 0.20·S_data + 0.30·S_model + 0.25·S_backdoor + 0.25·S_infer · generated {new Date(r.generated_at).toLocaleString()}
          </div>
          <div className="row wrap" style={{ marginTop: 6 }}>
            <button
              className="btn btn-primary"
              disabled={!!busy}
              onClick={() =>
                run('cert', () => api.certificate(contributorId), (c) => {
                  download(`visentra-certificate-${r.contributor_name.replace(/\s+/g, '-').toLowerCase()}.json`, c)
                  return 'Signed certificate exported'
                })
              }
            >
              {busy === 'cert' ? <Spinner /> : <Download size={15} />} Export signed certificate
            </button>
            <label className="btn">
              {busy === 'check' ? <Spinner /> : <BadgeCheck size={15} />} Verify a certificate
              <input type="file" accept="application/json,.json" hidden onChange={(e) => e.target.files?.[0] && void verifyFile(e.target.files[0])} />
            </label>
          </div>
          {check && (
            <div className="row wrap" style={{ gap: 16, marginTop: 4 }}>
              <Check ok={check.signature_valid} label="Signature intact" />
              <Check ok={check.trusted_key} label="Signed by this server" detail={check.key_id ? `key ${check.key_id}` : undefined} />
            </div>
          )}
        </div>
      </section>

      <div className="grid-2 stagger">
        {r.pillars.map((p, i) => (
          <PillarCard key={p.key} p={p} n={i} />
        ))}
      </div>

      <div className="grid-2">
        <section className="glass" style={{ padding: 18 }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Findings</div>
          <div className="ledger">
            {Object.entries(r.findings_count).map(([k, v]) => [
              <div key={k}>{k.replace(/_/g, ' ')}</div>,
              <div key={`${k}-v`} className="mono" style={{ color: v && /tampered|mismatch|suspicious/.test(k) ? 'var(--bad)' : undefined }}>{v}</div>,
            ])}
          </div>
        </section>
        <section className="glass" style={{ padding: 18 }}>
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <ShieldAlert size={15} color="#fbbf24" />
            <span className="eyebrow" style={{ color: '#fbbf24' }}>Stated limitations</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 8 }} className="dim">
            {r.limitations.map((l) => (
              <li key={l} style={{ fontSize: 12.5, lineHeight: 1.5 }}>{l}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
