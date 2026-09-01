import type { HTMLAttributes, ReactNode } from 'react'

export function Card({
  children,
  className = '',
  ...rest
}: { children: ReactNode } & HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div className={`rounded-card border border-ink-200 bg-white p-5 shadow-card ${className}`} {...rest}>
      {children}
    </div>
  )
}
