import { useState } from 'react'

export interface LogEntry {
  id: string
  timestamp: string
  message: string
  level?: 'info' | 'warn' | 'error'
}

interface Props {
  logs: LogEntry[]
  onClear?: () => void
}

export function EventLogDrawer({ logs, onClear }: Props) {
  const [expanded, setExpanded] = useState(false)

  const latestLog = logs[0]

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'var(--bg-sunken)',
        borderTop: '1px solid var(--rule-strong)',
        zIndex: 50,
        display: 'flex',
        flexDirection: 'column',
        height: expanded ? 180 : 32,
        transition: 'height 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        fontFamily: 'var(--font-mono)',
        fontSize: 11.5,
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          height: 32,
          padding: '0 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          background: 'var(--bg-sunken)',
          userSelect: 'none',
          borderBottom: expanded ? '1px solid var(--rule)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: 'var(--ink-600)',
            }}
          >
            [LOG]
          </span>
          {latestLog ? (
            <span style={{ color: latestLog.level === 'error' ? 'var(--state-tampered)' : latestLog.level === 'warn' ? 'var(--state-suspicious)' : 'var(--ink-900)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
              <span style={{ color: 'var(--ink-400)' }}>{latestLog.timestamp}</span> {latestLog.message}
            </span>
          ) : (
            <span style={{ color: 'var(--ink-400)' }}>Telemetry stream connected. Ready.</span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {logs.length > 0 && (
            <span style={{ fontSize: 10, color: 'var(--ink-400)' }}>
              {logs.length} events
            </span>
          )}
          {expanded && onClear && (
            <button
              onClick={(e) => { e.stopPropagation(); onClear(); }}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--ink-600)',
                fontSize: 10.5,
                cursor: 'pointer',
                textTransform: 'uppercase',
              }}
            >
              Clear
            </button>
          )}
          <span style={{ color: 'var(--ink-600)', fontSize: 10 }}>
            {expanded ? '▼ HIDE' : '▲ EXPAND'}
          </span>
        </div>
      </div>

      {expanded && (
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            background: 'var(--bg-sunken)',
          }}
        >
          {logs.length === 0 ? (
            <div style={{ color: 'var(--ink-400)', paddingTop: 10 }}>No verification events recorded yet.</div>
          ) : (
            logs.map((log) => {
              let color = 'var(--ink-900)'
              if (log.level === 'error') color = 'var(--state-tampered)'
              if (log.level === 'warn') color = 'var(--state-suspicious)'

              return (
                <div key={log.id} style={{ display: 'flex', gap: 12, lineHeight: 1.4 }}>
                  <span style={{ color: 'var(--ink-400)', flexShrink: 0 }}>{log.timestamp}</span>
                  <span style={{ color, wordBreak: 'break-all' }}>{log.message}</span>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
