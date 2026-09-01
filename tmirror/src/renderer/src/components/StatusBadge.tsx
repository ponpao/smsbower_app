import type { DeviceStatus } from '@shared/types'
import { useI18n } from '../i18n/I18nContext'

const dotColor: Record<DeviceStatus, string> = {
  ready: 'bg-teal-500',
  unauthorized: 'bg-coral-500',
  offline: 'bg-ink-400'
}

export function StatusBadge({ status }: { status: DeviceStatus }): JSX.Element {
  const { t } = useI18n()
  const label = {
    ready: t.devices.statusReady,
    unauthorized: t.devices.statusUnauthorized,
    offline: t.devices.statusOffline
  }[status]

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-2.5 py-1 text-xs font-medium text-ink-700">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor[status]}`} />
      {label}
    </span>
  )
}
