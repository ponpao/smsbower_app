export function CambodiaFlag({ className }: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 30 20" className={className} role="img" aria-hidden="true">
      <rect width="30" height="20" fill="#032EA1" />
      <rect y="5" width="30" height="10" fill="#E00025" />
      <g fill="#FFFFFF">
        <rect x="9.5" y="8.6" width="11" height="3.6" />
        <rect x="13.7" y="6.4" width="2.6" height="6.6" />
        <rect x="10.6" y="7.2" width="1.6" height="5.6" />
        <rect x="17.8" y="7.2" width="1.6" height="5.6" />
        <polygon points="15,4.4 16,7.2 14,7.2" />
        <polygon points="11.4,5.4 12.3,7.6 10.5,7.6" />
        <polygon points="18.6,5.4 19.5,7.6 17.7,7.6" />
        <rect x="8.6" y="12.2" width="12.8" height="0.9" />
        <rect x="9.6" y="13.4" width="10.8" height="0.7" />
      </g>
    </svg>
  )
}
