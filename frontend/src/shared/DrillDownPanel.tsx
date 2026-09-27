import { useEffect, type ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  status?: string | null
  widthPercent?: number
  onClose: () => void
  children: ReactNode
  headerActions?: ReactNode
}

export function DrillDownPanel({
  title,
  subtitle,
  widthPercent = 70,
  onClose,
  children,
  headerActions,
}: Props) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(23, 21, 18, 0.35)',
          transition: 'opacity 0.2s',
        }}
      />

      <div
        style={{
          position: 'relative',
          width: `${widthPercent}vw`,
          maxWidth: '1200px',
          height: '100%',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--rule-strong)',
          boxShadow: '-6px 0 20px rgba(0, 0, 0, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 1001,
          borderRadius: '4px 0 0 4px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: 48,
            padding: '0 20px',
            borderBottom: '1px solid var(--rule-strong)',
            background: 'var(--bg-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                color: 'var(--ink-900)',
              }}
            >
              {title}
            </span>
            {subtitle && (
              <span
                style={{
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--ink-600)',
                }}
              >
                {subtitle}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {headerActions}
            <button
              onClick={onClose}
              title="Close (Esc)"
              style={{
                background: 'transparent',
                border: '1px solid var(--rule)',
                color: 'var(--ink-600)',
                borderRadius: 2,
                padding: '4px 8px',
                fontSize: 11,
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
              }}
            >
              ESC ✕
            </button>
          </div>
        </div>

        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
