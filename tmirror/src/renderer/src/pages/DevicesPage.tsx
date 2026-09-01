import { useState } from 'react'
import { TopBar } from '../components/TopBar'
import { DeviceCard } from '../components/DeviceCard'
import { EmptyState } from '../components/EmptyState'
import { useDevices } from '../state/useDevices'
import { useI18n } from '../i18n/I18nContext'
import { useToast } from '../state/ToastContext'
import type { Page } from '../App'

export function DevicesPage({ onNavigate }: { onNavigate: (page: Page) => void }): JSX.Element {
  const { devices, loading, refresh, setMirroring } = useDevices()
  const { t } = useI18n()
  const { push } = useToast()
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const readyDevices = devices.filter((d) => d.status === 'ready')
  const mirroringDevices = devices.filter((d) => d.isMirroring)

  function toggleSelect(serial: string): void {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(serial)) next.delete(serial)
      else next.add(serial)
      return next
    })
  }

  async function handleMirrorSelected(): Promise<void> {
    const targets = readyDevices.filter((d) => selected.has(d.serial) && !d.isMirroring)
    for (const device of targets) {
      const result = await window.tmirror.devices.startMirror(device.serial, device.model ?? device.serial)
      if (result.ok) setMirroring(device.serial, true)
      else push(result.message ?? t.toast.toolsMissing, 'error')
    }
  }

  async function handleArrange(mode: 'grid' | 'side-by-side'): Promise<void> {
    if (mirroringDevices.length === 0) return
    await window.tmirror.devices.arrange(
      mode,
      mirroringDevices.map((d) => ({ serial: d.serial, label: d.model ?? d.serial }))
    )
  }

  async function handleCloseAll(): Promise<void> {
    await window.tmirror.devices.closeAllMirrors()
    mirroringDevices.forEach((d) => setMirroring(d.serial, false))
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar title={t.devices.title} subtitle={t.devices.subtitle} />
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-8 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => refresh()}
              className="rounded-lg bg-white border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
            >
              {loading ? t.common.loading : t.common.refresh}
            </button>
            <button
              type="button"
              onClick={() => onNavigate('connect')}
              className="rounded-lg bg-coral-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-coral-600"
            >
              {t.common.addDevice}
            </button>
            {selected.size > 0 && (
              <button
                type="button"
                onClick={handleMirrorSelected}
                className="rounded-lg bg-teal-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-600"
              >
                {t.common.mirror} ({selected.size})
              </button>
            )}
          </div>

          {mirroringDevices.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-ink-500">{t.common.arrangeWindows}</span>
              <button
                type="button"
                onClick={() => handleArrange('grid')}
                className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
              >
                {t.common.arrangeGrid}
              </button>
              <button
                type="button"
                onClick={() => handleArrange('side-by-side')}
                className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
              >
                {t.common.arrangeSideBySide}
              </button>
              <button
                type="button"
                onClick={handleCloseAll}
                className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
              >
                {t.common.closeAllMirrors}
              </button>
            </div>
          )}
        </div>

        {devices.length === 0 && !loading ? (
          <EmptyState
            icon="📱"
            title={t.devices.empty}
            action={
              <button
                type="button"
                onClick={() => onNavigate('connect')}
                className="rounded-lg bg-coral-500 px-4 py-2 text-sm font-semibold text-white hover:bg-coral-600"
              >
                {t.devices.emptyCta}
              </button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {devices.map((device) => (
              <DeviceCard
                key={device.serial}
                device={device}
                selected={selected.has(device.serial)}
                onToggleSelect={toggleSelect}
                onMirroringChange={setMirroring}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
