import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'destructive'
  size?: 'sm' | 'md'
  children: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  disabled,
  children,
  style,
  ...props
}: Props) {
  let bg = 'transparent'
  let color = 'var(--ink-900)'
  let border = '1px solid var(--rule-strong)'

  if (variant === 'primary') {
    bg = 'var(--ink-900)'
    color = '#FFFFFF'
    border = '1px solid var(--ink-900)'
  } else if (variant === 'destructive') {
    bg = 'transparent'
    color = 'var(--state-tampered)'
    border = '1px solid var(--state-tampered)'
  }

  const padding = size === 'sm' ? '4px 8px' : '6px 12px'
  const fontSize = size === 'sm' ? 11.5 : 12.5

  return (
    <button
      disabled={disabled}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        background: bg,
        color,
        border,
        borderRadius: 2,
        padding,
        fontSize,
        fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transition: 'background 0.1s, border-color 0.1s, color 0.1s',
        lineHeight: 1.2,
        ...style,
      }}
      {...props}
    >
      {children}
    </button>
  )
}
