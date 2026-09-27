interface Props {
  before: number
  after: number
  targetClass: number
}

export function ConfidenceShiftScale({ before, after, targetClass }: Props) {
  const bPct = Math.round(before * 100)
  const aPct = Math.round(after * 100)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
        <span style={{ color: 'var(--ink-600)' }}>Class {targetClass} Shift:</span>
        <span>
          <span style={{ color: 'var(--ink-600)' }}>{bPct}%</span>
          {' → '}
          <span style={{ color: 'var(--state-tampered)', fontWeight: 700 }}>{aPct}%</span>
          <span style={{ color: 'var(--state-suspicious)', marginLeft: 6 }}>
            (+{Math.max(0, aPct - bPct)}%)
          </span>
        </span>
      </div>

      <div
        style={{
          position: 'relative',
          height: 18,
          background: 'var(--bg-sunken)',
          border: '1px solid var(--rule-strong)',
        }}
      >
        {Array.from({ length: 11 }).map((_, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `${i * 10}%`,
              top: 0,
              bottom: 0,
              width: 1,
              background: i % 5 === 0 ? 'var(--rule-strong)' : 'var(--rule)',
            }}
          />
        ))}

        <div
          style={{
            position: 'absolute',
            left: `${Math.min(bPct, aPct)}%`,
            width: `${Math.abs(aPct - bPct)}%`,
            top: 2,
            bottom: 2,
            background: 'var(--state-suspicious)',
            opacity: 0.35,
          }}
        />

        <div
          title={`Clean: ${bPct}%`}
          style={{
            position: 'absolute',
            left: `${bPct}%`,
            top: 0,
            bottom: 0,
            width: 2,
            background: 'var(--ink-600)',
          }}
        />

        <div
          title={`Triggered: ${aPct}%`}
          style={{
            position: 'absolute',
            left: `${aPct}%`,
            top: 0,
            bottom: 0,
            width: 3,
            background: 'var(--state-tampered)',
          }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)' }}>
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>
    </div>
  )
}
