interface Props {
  value?: number
  indeterminate?: boolean
  color?: string
}

export function ProgressLine({ value = 0, indeterminate = false, color = 'var(--ink-900)' }: Props) {
  return (
    <div
      style={{
        width: '100%',
        height: 2,
        background: 'var(--rule)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          background: color,
          width: indeterminate ? '40%' : `${Math.max(0, Math.min(100, value))}%`,
          transition: indeterminate ? 'none' : 'width 0.25s ease-out',
        }}
      />
    </div>
  )
}
