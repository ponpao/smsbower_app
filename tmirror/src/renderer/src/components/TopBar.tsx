import { useI18n } from '../i18n/I18nContext'
import { FlagSwitch } from './FlagSwitch'

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }): JSX.Element {
  useI18n()
  return (
    <header className="flex items-center justify-between border-b border-ink-200 bg-white px-8 py-5">
      <div>
        <h1 className="text-xl font-bold text-ink-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-ink-600">{subtitle}</p>}
      </div>
      <FlagSwitch />
    </header>
  )
}
