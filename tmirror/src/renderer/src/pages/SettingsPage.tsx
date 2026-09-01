import { useEffect, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { Card } from '../components/Card'
import { FlagSwitch } from '../components/FlagSwitch'
import { useI18n } from '../i18n/I18nContext'
import { useSettings } from '../state/SettingsContext'
import type { ToolStatus } from '@shared/types'

export function SettingsPage(): JSX.Element {
  const { t } = useI18n()
  const { settings, update } = useSettings()
  const [tools, setTools] = useState<ToolStatus | null>(null)
  const [detecting, setDetecting] = useState(false)

  async function detect(): Promise<void> {
    setDetecting(true)
    const result = await window.tmirror.tools.detect()
    setTools(result)
    setDetecting(false)
  }

  useEffect(() => {
    detect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function pickAdb(): Promise<void> {
    const dir = await window.tmirror.tools.pickFolder()
    if (dir) {
      await update({ adbPath: dir })
      detect()
    }
  }

  async function pickScrcpy(): Promise<void> {
    const dir = await window.tmirror.tools.pickFolder()
    if (dir) {
      await update({ scrcpyPath: dir })
      detect()
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar title={t.settings.title} subtitle={t.settings.subtitle} />
      <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-8 py-6">
        <Card className="max-w-xl">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink-900">{t.settings.toolsTitle}</h2>
            <button
              type="button"
              onClick={detect}
              className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
            >
              {detecting ? t.common.loading : t.settings.detect}
            </button>
          </div>

          <div className="mt-4 flex flex-col gap-4">
            <div>
              <p className="text-sm font-medium text-ink-800">{t.settings.adbPath}</p>
              <div className="mt-1.5 flex items-center gap-2">
                <input
                  readOnly
                  value={settings.adbPath ?? tools?.adbPath ?? ''}
                  placeholder="PATH"
                  className="min-w-0 flex-1 rounded-lg border border-ink-200 bg-ink-50 px-3 py-1.5 text-xs text-ink-600"
                />
                <button
                  type="button"
                  onClick={pickAdb}
                  className="shrink-0 rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
                >
                  {t.common.browse}
                </button>
              </div>
              <p className={`mt-1 text-xs ${tools?.adbFound ? 'text-teal-600' : 'text-coral-600'}`}>
                {tools ? (tools.adbFound ? `${t.settings.found}${tools.adbVersion ? ` — ${tools.adbVersion}` : ''}` : t.settings.notFound) : ''}
              </p>
            </div>

            <div>
              <p className="text-sm font-medium text-ink-800">{t.settings.scrcpyPath}</p>
              <div className="mt-1.5 flex items-center gap-2">
                <input
                  readOnly
                  value={settings.scrcpyPath ?? tools?.scrcpyPath ?? ''}
                  placeholder="PATH"
                  className="min-w-0 flex-1 rounded-lg border border-ink-200 bg-ink-50 px-3 py-1.5 text-xs text-ink-600"
                />
                <button
                  type="button"
                  onClick={pickScrcpy}
                  className="shrink-0 rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
                >
                  {t.common.browse}
                </button>
              </div>
              <p className={`mt-1 text-xs ${tools?.scrcpyFound ? 'text-teal-600' : 'text-coral-600'}`}>
                {tools ? (tools.scrcpyFound ? `${t.settings.found}${tools.scrcpyVersion ? ` — ${tools.scrcpyVersion}` : ''}` : t.settings.notFound) : ''}
              </p>
            </div>
          </div>
        </Card>

        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.settings.languageTitle}</h2>
          <div className="mt-3">
            <FlagSwitch />
          </div>
        </Card>

        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.settings.accentTitle}</h2>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              onClick={() => update({ accent: 'coral' })}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                settings.accent === 'coral' ? 'border-coral-500 bg-coral-50' : 'border-ink-200'
              }`}
            >
              <span className="h-4 w-4 rounded-full bg-coral-500" /> Coral
            </button>
            <button
              type="button"
              onClick={() => update({ accent: 'teal' })}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                settings.accent === 'teal' ? 'border-teal-500 bg-teal-50' : 'border-ink-200'
              }`}
            >
              <span className="h-4 w-4 rounded-full bg-teal-500" /> Teal
            </button>
          </div>
        </Card>

        <Card className="max-w-xl opacity-70">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-ink-900">{t.settings.iphoneTitle}</h2>
            <span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-500">
              v2
            </span>
          </div>
          <p className="mt-2 text-sm text-ink-600">{t.settings.iphoneBody}</p>
        </Card>

        <Card className="max-w-xl bg-ink-50/60">
          <h2 className="text-sm font-semibold text-ink-900">{t.settings.aboutTitle}</h2>
          <p className="mt-2 text-xs leading-relaxed text-ink-600">{t.settings.aboutBody}</p>
        </Card>
      </div>
    </div>
  )
}
