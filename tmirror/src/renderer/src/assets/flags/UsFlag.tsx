export function UsFlag({ className }: { className?: string }): JSX.Element {
  const stripeHeight = 20 / 13
  const stripes = Array.from({ length: 13 }, (_, i) => (
    <rect
      key={i}
      x={0}
      y={i * stripeHeight}
      width={30}
      height={stripeHeight}
      fill={i % 2 === 0 ? '#B22234' : '#FFFFFF'}
    />
  ))
  const stars: JSX.Element[] = []
  const cols = 6
  const rows = 4
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      stars.push(
        <circle key={`${r}-${c}`} cx={0.9 + c * 1.55} cy={0.9 + r * 1.5} r={0.42} fill="#FFFFFF" />
      )
    }
  }
  return (
    <svg viewBox="0 0 30 20" className={className} role="img" aria-hidden="true">
      {stripes}
      <rect x="0" y="0" width="13" height="10.77" fill="#3C3B6E" />
      {stars}
    </svg>
  )
}
