interface Props {
  expected: string
  actual: string
}

export function HashDiff({ expected, actual }: Props) {
  const isMatch = expected === actual
  const maxLen = Math.max(expected.length, actual.length)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
      <div>
        <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase', marginBottom: 2 }}>
          Registered Hash
        </div>
        <div style={{ color: 'var(--ink-900)', wordBreak: 'break-all', background: 'var(--bg-sunken)', padding: '4px 6px', border: '1px solid var(--rule)' }}>
          {expected || '—'}
        </div>
      </div>

      <div>
        <div style={{ fontSize: 10, color: 'var(--ink-600)', textTransform: 'uppercase', marginBottom: 2 }}>
          Current Disk Hash {isMatch ? '✓ (MATCH)' : '✕ (MISMATCH DETECTED)'}
        </div>
        <div
          style={{
            wordBreak: 'break-all',
            background: isMatch ? 'var(--state-verified-bg)' : 'var(--state-tampered-bg)',
            border: `1px solid ${isMatch ? 'var(--state-verified)' : 'var(--state-tampered)'}`,
            padding: '4px 6px',
          }}
        >
          {Array.from({ length: maxLen }).map((_, i) => {
            const charExpected = expected[i]
            const charActual = actual[i]
            const match = charExpected === charActual

            return (
              <span
                key={i}
                style={{
                  color: match ? 'var(--ink-900)' : 'var(--state-tampered)',
                  fontWeight: match ? 400 : 700,
                  textDecoration: match ? 'none' : 'underline',
                  background: match ? 'transparent' : 'rgba(163, 46, 46, 0.2)',
                }}
              >
                {charActual ?? ' '}
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}
