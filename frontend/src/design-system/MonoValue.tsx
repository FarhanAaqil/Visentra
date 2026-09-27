import { useState } from 'react'

interface Props {
  value: string | null | undefined
  truncate?: number
  copyable?: boolean
  dimmed?: boolean
  className?: string
}

export function MonoValue({ value, truncate, copyable = false, dimmed = false, className = '' }: Props) {
  const [copied, setCopied] = useState(false)

  if (!value) {
    return <span style={{ color: 'var(--ink-400)', fontFamily: 'var(--font-mono)' }}>—</span>
  }

  let text = value
  if (truncate && value.length > truncate) {
    const half = Math.floor(truncate / 2)
    text = `${value.slice(0, half)}…${value.slice(-half)}`
  }

  const handleCopy = () => {
    if (!copyable) return
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  return (
    <span
      className={className}
      onClick={handleCopy}
      title={copyable ? `Click to copy: ${value}` : value}
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12.5,
        color: dimmed ? 'var(--ink-600)' : 'var(--ink-900)',
        cursor: copyable ? 'pointer' : 'inherit',
        letterSpacing: '-0.01em',
        wordBreak: 'break-all',
      }}
    >
      {text}
      {copied && (
        <span
          style={{
            marginLeft: 6,
            fontSize: 10,
            textTransform: 'uppercase',
            color: 'var(--state-verified)',
            fontWeight: 600,
          }}
        >
          copied
        </span>
      )}
    </span>
  )
}
