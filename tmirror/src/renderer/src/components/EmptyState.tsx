import type { ReactNode } from 'react'

export function EmptyState({
  icon,
  title,
  action
}: {
  icon?: ReactNode
  title: string
  action?: ReactNode
}): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-card border border-dashed border-ink-300 bg-white px-8 py-16 text-center">
      {icon && <div className="text-4xl">{icon}</div>}
      <p className="max-w-sm text-sm text-ink-600">{title}</p>
      {action}
    </div>
  )
}
