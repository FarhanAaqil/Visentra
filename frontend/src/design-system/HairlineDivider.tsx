interface Props {
  vertical?: boolean
  margin?: number | string
  strong?: boolean
}

export function HairlineDivider({ vertical = false, margin = 0, strong = false }: Props) {
  const color = strong ? 'var(--rule-strong)' : 'var(--rule)'

  if (vertical) {
    return (
      <div
        style={{
          width: 1,
          height: '100%',
          background: color,
          margin: `0 ${typeof margin === 'number' ? `${margin}px` : margin}`,
          flexShrink: 0,
        }}
      />
    )
  }

  return (
    <div
      style={{
        width: '100%',
        height: 1,
        background: color,
        margin: `${typeof margin === 'number' ? `${margin}px` : margin} 0`,
        flexShrink: 0,
      }}
    />
  )
}
