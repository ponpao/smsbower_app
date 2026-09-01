import { useI18n } from '../i18n/I18nContext'
import type { Page } from '../App'

const items: { page: Page; icon: string }[] = [
  { page: 'devices', icon: '📱' },
  { page: 'connect', icon: '🔗' },
  { page: 'transfer', icon: '📁' },
  { page: 'clipboard', icon: '📋' },
  { page: 'settings', icon: '⚙️' }
]

export function Sidebar({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }): JSX.Element {
  const { t } = useI18n()
  const labels: Record<Page, string> = {
    devices: t.nav.devices,
    connect: t.nav.connect,
    transfer: t.nav.transfer,
    clipboard: t.nav.clipboard,
    settings: t.nav.settings
  }

  return (
    <nav className="flex h-full w-56 shrink-0 flex-col gap-1 border-r border-ink-200 bg-white px-3 py-5">
      <div className="mb-4 flex items-center gap-2 px-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-coral-500 to-teal-500 text-sm font-bold text-white">
          T
        </div>
        <span className="text-lg font-bold tracking-tight text-ink-900">TMIRROR</span>
      </div>
      {items.map((item) => (
        <button
          key={item.page}
          type="button"
          onClick={() => onNavigate(item.page)}
          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
            page === item.page
              ? 'accent-soft-bg accent-text'
              : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
          }`}
        >
          <span aria-hidden="true">{item.icon}</span>
          {labels[item.page]}
        </button>
      ))}
    </nav>
  )
}
