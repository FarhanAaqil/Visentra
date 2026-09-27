interface Props {
  status?: string | null
  label?: string
  className?: string
}

export function StatusTag({ status, label, className = '' }: Props) {
  const norm = (status || 'pending').toLowerCase()
  const displayLabel = label || norm.toUpperCase()

  let color = 'var(--state-pending)'
  let bg = 'var(--bg-sunken)'

  if (norm === 'verified' || norm === 'ok' || norm === 'clean') {
    color = 'var(--state-verified)'
    bg = 'var(--state-verified-bg)'
  } else if (norm === 'suspicious' || norm === 'flagged') {
    color = 'var(--state-suspicious)'
    bg = 'var(--state-suspicious-bg)'
  } else if (norm === 'tampered' || norm === 'mismatch') {
    color = 'var(--state-tampered)'
    bg = 'var(--state-tampered-bg)'
  }

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 6px',
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        color,
        background: bg,
        border: `1px solid ${color}`,
        borderRadius: 2,
        lineHeight: 1,
        userSelect: 'none',
      }}
    >
      <span
        style={{
          width: 5,
          height: 5,
          background: color,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      {displayLabel}
    </span>
  )
}
