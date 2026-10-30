import { useMemo, useState } from 'react'
import { Database, FlaskConical, RotateCcw, ScanLine, ShieldCheck, Skull } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useStore } from '../lib/store'
import { scoreColor, short } from '../lib/format'
import type { DuplicatePair, OodScore } from '../lib/types'
import { Bar, Check, Empty, Hash, Metric, Sheet, Spinner, StatusPill } from '../ui/kit'
import { useAction } from '../lib/useAction'

type Tab = 'samples' | 'duplicates' | 'ood' | 'integrity'

export default function DatasetPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const { refresh, revision } = useStore()
  const { busy, run } = useAction()
  const [tab, setTab] = useState<Tab>('samples')
  const ds = useAsync(() => api.dataset(id), [id, revision])
  const samples = useAsync(() => api.samples(id), [id, revision])
  const findings = useAsync(() => api.findings(id), [id, revision])
  const [integrity, setIntegrity] = useState<NonNullable<Awaited<ReturnType<typeof api.verifyDataset>>['integrity']> | null>(null)

  const dups = useMemo(
    () => (findings.data ?? []).filter((f) => f.check_type === 'near_duplicate').map((f) => f.evidence_json as unknown as DuplicatePair),
    [findings.data],
  )
  const oods = useMemo(
    () => (findings.data ?? []).filter((f) => f.check_type === 'ood_anomaly').map((f) => f.evidence_json as unknown as OodScore),
    [findings.data],
  )
  const summary = (findings.data ?? []).find((f) => f.check_type === 'analysis_summary')?.evidence_json as
    | { embedder?: string; analyzed_at?: string; samples_checked?: number }
    | undefined
  const [scores, setScores] = useState<OodScore[] | null>(null)

  const d = ds.data
  const after = async () => {
    await refresh()
    ds.reload()
    samples.reload()
    findings.reload()
  }

  const actions = (
    <>
      <button
        className="btn btn-primary"
        disabled={!!busy || d?.status === 'tampered'}
        onClick={() =>
          run('analyze', () => api.analyzeDataset(id), (r) => {
            setScores(r.scores)
            setTab(r.ood_flagged ? 'ood' : r.duplicate_pairs ? 'duplicates' : 'samples')
            void after()
            return `Screened ${r.total_samples_checked} samples: ${r.duplicate_pairs} duplicate pair(s), ${r.ood_flagged} outlier(s)`
          })
        }
      >
        {busy === 'analyze' ? <Spinner /> : <ScanLine size={15} />} Screen samples
      </button>
      <button
        className="btn"
        disabled={!!busy}
        onClick={() =>
          run('verify', () => api.verifyDataset(id), (r) => {
            setIntegrity(r.integrity ?? null)
            setTab('integrity')
            void after()
            return r.status === 'tampered' ? 'Merkle root diverged: dataset tampered' : 'Archive and every sample verified'
          })
        }
      >
        {busy === 'verify' ? <Spinner /> : <ShieldCheck size={15} />} Verify Merkle root
      </button>
      <button className="btn btn-danger" disabled={!!busy} onClick={() => run('tamper', () => api.tamperDataset(id), () => 'One sample poisoned with a checkerboard. Verify to catch it.')}>
        <Skull size={15} /> Poison a sample
      </button>
      <button
        className="btn"
        disabled={!!busy}
        onClick={() =>
          run('restore', () => api.restoreDataset(id), (r) => {
            void after()
            return r.detail
          })
        }
      >
        <RotateCcw size={15} /> Restore
      </button>
    </>
  )

  return (
    <Sheet eyebrow="Pillar I · Dataset inspector" title={d ? `Dataset v${d.version}` : 'Dataset'} onClose={onClose} actions={actions}>
      {!d ? (
        <div className="skeleton" style={{ height: 120 }} />
      ) : (
        <>
          <div className="row wrap" style={{ gap: 10 }}>
            <StatusPill status={d.status} />
            <span className="dim">{d.name}</span>
            {summary?.embedder && <span className="mono faint" style={{ fontSize: 11 }}>embedder {summary.embedder}</span>}
          </div>
          <div className="grid-4 stagger">
            <Metric k="Samples" v={d.sample_count} />
            <Metric k="Near duplicates" v={dups.length} tone={dups.length ? 'warn' : 'ok'} />
            <Metric k="OOD outliers" v={oods.length} tone={oods.length ? 'warn' : 'ok'} />
            <Metric k="Integrity" v={d.status === 'tampered' ? 'Broken' : 'Sealed'} tone={d.status === 'tampered' ? 'bad' : 'ok'} />
          </div>
          <div className="card" style={{ padding: 14 }}>
            <div className="ledger">
              <div>Merkle root</div>
              <div><Hash value={d.merkle_root} label="Merkle root" /></div>
              <div>Archive SHA-256</div>
              <div><Hash value={d.sha256} label="archive hash" /></div>
            </div>
          </div>

          <div className="tabs" style={{ alignSelf: 'flex-start' }}>
            {(['samples', 'duplicates', 'ood', 'integrity'] as Tab[]).map((t) => (
              <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
                {t === 'ood' ? 'OOD' : t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          {tab === 'samples' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(96px, 1fr))', gap: 10 }} className="stagger">
              {(samples.data ?? []).map((s) => (
                <figure key={s.id} className="card" style={{ margin: 0, padding: 6, borderColor: s.flags.length ? 'rgba(251,191,36,0.6)' : undefined }}>
                  <img src={api.thumbnail(id, s.id, 128)} alt={s.name} loading="lazy" style={{ width: '100%', aspectRatio: '1', borderRadius: 8, imageRendering: 'pixelated' }} />
                  <figcaption className="mono" style={{ fontSize: 9.5, marginTop: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.name}>
                    {s.name}
                  </figcaption>
                  {s.flags.map((f) => (
                    <span key={f} className="pill st-warn" style={{ fontSize: 8.5, marginTop: 4 }}>{f.replace('_', ' ')}</span>
                  ))}
                </figure>
              ))}
            </div>
          )}

          {tab === 'duplicates' &&
            (dups.length ? (
              <div className="col stagger">
                {dups.map((p) => (
                  <div key={p.sample_a_id + p.sample_b_id} className="card row wrap" style={{ padding: 12, gap: 14 }}>
                    {[p.sample_a_id, p.sample_b_id].map((sid, i) => (
                      <figure key={sid} style={{ margin: 0 }}>
                        <img src={api.thumbnail(id, sid, 112)} alt="" style={{ width: 92, height: 92, borderRadius: 10, imageRendering: 'pixelated' }} />
                        <figcaption className="mono faint" style={{ fontSize: 9.5, marginTop: 4 }}>{i ? p.image_b : p.image_a}</figcaption>
                      </figure>
                    ))}
                    <div className="grow" style={{ minWidth: 160 }}>
                      <div className="row between">
                        <span className="eyebrow">Hamming distance</span>
                        <StatusPill status={p.severity === 'critical' ? 'tampered' : 'flagged'} label={p.severity} />
                      </div>
                      <div className="serif" style={{ fontSize: 30, fontWeight: 700 }}>
                        {p.hamming_distance}<span className="dim" style={{ fontSize: 14 }}> / 64 bits</span>
                      </div>
                      <Bar value={p.hamming_distance / 64} color="#fbbf24" marker={8 / 64} />
                      <div className="mono faint" style={{ fontSize: 10.5, marginTop: 8 }}>{p.phash_a} · {p.phash_b}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty icon={<Database size={30} />} title="No near duplicates">No pair of samples is within 8 bits of perceptual hash distance.</Empty>
            ))}

          {tab === 'ood' && (
            <OodList datasetId={id} flagged={oods} scores={scores} />
          )}

          {tab === 'integrity' &&
            (integrity ? (
              <div className="card col" style={{ padding: 16, gap: 12 }}>
                <Check ok={integrity.archive_match} label="Archive hash" detail={integrity.archive_match ? 'Uploaded archive is byte-identical' : 'Archive bytes changed'} />
                <Check
                  ok={integrity.merkle_match}
                  label="Merkle root"
                  detail={`recomputed ${short(integrity.recomputed_merkle_root, 20)} vs sealed ${short(d.merkle_root, 20)}`}
                />
                <Check
                  ok={!integrity.changed_samples.length && !integrity.missing_samples.length}
                  label="Per-sample digests"
                  detail={
                    integrity.changed_samples.length
                      ? `${integrity.changed_samples.length} sample(s) changed after sealing`
                      : integrity.missing_samples.length
                        ? `${integrity.missing_samples.length} sample(s) missing`
                        : 'Every sample still hashes to its sealed digest'
                  }
                />
                {integrity.changed_samples.map((sid) => (
                  <div key={sid} className="row" style={{ gap: 12 }}>
                    <img src={api.thumbnail(id, sid, 112)} alt="" style={{ width: 84, height: 84, borderRadius: 10, imageRendering: 'pixelated', outline: '2px solid var(--bad)' }} />
                    <span className="dim">This sample's bytes no longer match the Merkle leaf. Look for the checkerboard in the corner.</span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty icon={<ShieldCheck size={30} />} title="Run a verification">
                Verify re-hashes the archive and every sample and rebuilds the Merkle root.
              </Empty>
            ))}
        </>
      )}
    </Sheet>
  )
}

function OodList({ datasetId, flagged, scores }: { datasetId: string; flagged: OodScore[]; scores: OodScore[] | null }) {
  const rows = scores ?? flagged
  if (!rows.length) {
    return (
      <Empty icon={<FlaskConical size={30} />} title={scores ? 'Nothing out of distribution' : 'No outliers recorded'}>
        The hybrid score blends Isolation Forest (55%) with a leave-one-out Mahalanobis distance (45%). Samples above 0.70 are flagged.
      </Empty>
    )
  }
  return (
    <div className="col stagger">
      {!scores && <div className="dim" style={{ fontSize: 12 }}>Showing flagged samples. Re-screen to see every sample's score.</div>}
      {rows.map((r) => (
        <div key={r.sample_id} className="card row" style={{ padding: 10, gap: 12 }}>
          <img src={api.thumbnail(datasetId, r.sample_id, 96)} alt="" style={{ width: 54, height: 54, borderRadius: 8, imageRendering: 'pixelated' }} />
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="row between">
              <span className="mono" style={{ fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.image}</span>
              <span className="serif" style={{ fontSize: 18, fontWeight: 700, color: r.flag ? '#fbbf24' : scoreColor(100 - r.anomaly_score * 100) }}>
                {r.anomaly_score.toFixed(3)}
              </span>
            </div>
            <Bar value={r.anomaly_score} color={r.flag ? 'linear-gradient(90deg,#f59e0b,#fbbf24)' : 'linear-gradient(90deg,#9f1239,#fb7185)'} marker={0.7} />
            <div className="mono faint" style={{ fontSize: 10, marginTop: 4 }}>
              isolation {r.isolation_score?.toFixed(3)} · mahalanobis {r.mahalanobis_score?.toFixed(3)}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
