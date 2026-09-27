interface Props {
  datasetIntegrity: number
  modelIntegrity: number
  backdoorScreening: number
  inferenceBinding: number
}

export function ScoreBreakdownTable({
  datasetIntegrity,
  modelIntegrity,
  backdoorScreening,
  inferenceBinding,
}: Props) {
  const rows = [
    { label: 'Dataset Integrity', weight: '20%', score: datasetIntegrity },
    { label: 'Model Integrity', weight: '30%', score: modelIntegrity },
    { label: 'Backdoor Screening', weight: '25%', score: backdoorScreening },
    { label: 'Inference Cryptographic Binding', weight: '25%', score: inferenceBinding },
  ]

  return (
    <div style={{ border: '1px solid var(--rule-strong)', background: 'var(--bg-surface)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 12 }}>
        <thead>
          <tr style={{ background: 'var(--bg-sunken)', borderBottom: '1px solid var(--rule-strong)' }}>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10.5 }}>
              Component
            </th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10.5 }}>
              Weight
            </th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--ink-600)', textTransform: 'uppercase', fontSize: 10.5, textAlign: 'right' }}>
              Sub-score
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            let color = 'var(--state-verified)'
            if (r.score < 50) color = 'var(--state-tampered)'
            else if (r.score < 80) color = 'var(--state-suspicious)'

            return (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--rule)' : 'none' }}>
                <td style={{ padding: '8px 12px', color: 'var(--ink-900)' }}>{r.label}</td>
                <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--ink-600)' }}>{r.weight}</td>
                <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color, textAlign: 'right' }}>
                  {r.score.toFixed(1)} / 100
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
