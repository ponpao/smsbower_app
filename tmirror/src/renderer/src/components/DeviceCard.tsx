import { useState } from 'react'
import type { Device } from '@shared/types'
import { useI18n } from '../i18n/I18nContext'
import { useToast } from '../state/ToastContext'
import { StatusBadge } from './StatusBadge'
import { Card } from './Card'

interface Props {
  device: Device
  selected: boolean
  onToggleSelect: (serial: string) => void
  onMirroringChange: (serial: string, mirroring: boolean) => void
}

function deviceLabel(device: Device): string {
  return device.model ?? device.serial
}

export function DeviceCard({ device, selected, onToggleSelect, onMirroringChange }: Props): JSX.Element {
  const { t } = useI18n()
  const { push } = useToast()
  const [isDragOver, setIsDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uninstallTarget, setUninstallTarget] = useState('')

  const ready = device.status === 'ready'

  async function handleMirrorToggle(): Promise<void> {
    if (device.isMirroring) {
      await window.tmirror.devices.stopMirror(device.serial)
      onMirroringChange(device.serial, false)
      return
    }
    const result = await window.tmirror.devices.startMirror(device.serial, deviceLabel(device))
    if (result.ok) onMirroringChange(device.serial, true)
    else push(result.message ?? t.toast.toolsMissing, 'error')
  }

  async function handleScreenshot(): Promise<void> {
    const result = await window.tmirror.devices.screenshot(device.serial)
    if (result.ok && result.message !== 'Cancelled') push(t.toast.screenshotSaved, 'success')
    else if (result.message && result.message !== 'Cancelled') push(result.message, 'error')
  }

  async function handleUninstall(): Promise<void> {
    if (!uninstallTarget.trim()) return
    setBusy(true)
    const result = await window.tmirror.devices.uninstall(device.serial, uninstallTarget.trim())
    setBusy(false)
    push(result.ok ? t.toast.uninstallSuccess : result.message ?? t.toast.uninstallFail, result.ok ? 'success' : 'error')
    if (result.ok) setUninstallTarget('')
  }

  async function handleEnableWifi(): Promise<void> {
    const result = await window.tmirror.devices.enableWifi(device.serial)
    push(result.ok ? `${t.devices.wifiEnabled}: ${result.message}` : result.message ?? 'Failed', result.ok ? 'success' : 'error')
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>): Promise<void> {
    e.preventDefault()
    setIsDragOver(false)
    if (!ready) return
    setBusy(true)
    for (const file of Array.from(e.dataTransfer.files)) {
      const path = window.tmirror.getPathForFile(file)
      if (path.toLowerCase().endsWith('.apk')) {
        const result = await window.tmirror.transfer.installApk(device.serial, path)
        push(result.ok ? t.toast.installSuccess : result.message ?? t.toast.installFail, result.ok ? 'success' : 'error')
      } else {
        const result = await window.tmirror.transfer.push(device.serial, path, '/sdcard/Download')
        push(result.ok ? t.toast.pushSuccess : result.message ?? t.toast.pushFail, result.ok ? 'success' : 'error')
      }
    }
    setBusy(false)
  }

  return (
    <Card
      className={`flex flex-col gap-3 transition ${isDragOver ? 'ring-2 ring-teal-400' : ''}`}
      onDragOver={(e) => {
        if (!ready) return
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3">
          {ready && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(device.serial)}
              className="mt-1.5 h-4 w-4 accent-coral-500"
              aria-label={deviceLabel(device)}
            />
          )}
          <div>
            <p className="font-semibold text-ink-900">{deviceLabel(device)}</p>
            <p className="text-xs text-ink-500">{device.serial}</p>
          </div>
        </div>
        <StatusBadge status={device.status} />
      </div>

      {device.status === 'unauthorized' && (
        <p className="rounded-lg bg-coral-50 px-3 py-2 text-xs text-coral-700">{t.devices.usbHint}</p>
      )}

      {ready && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-600">
          {device.androidVersion && (
            <span>
              {t.devices.androidVersion} {device.androidVersion}
            </span>
          )}
          {device.batteryPercent !== undefined && (
            <span>
              {t.devices.battery} {device.batteryPercent}%
            </span>
          )}
          <span>{device.connection === 'usb' ? t.devices.connectionUsb : t.devices.connectionTcp}</span>
        </div>
      )}

      {ready && (
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            onClick={handleMirrorToggle}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              device.isMirroring ? 'bg-ink-900 text-white' : 'bg-coral-500 text-white hover:bg-coral-600'
            }`}
          >
            {device.isMirroring ? t.common.stopMirror : t.common.mirror}
          </button>
          <button
            type="button"
            onClick={handleScreenshot}
            className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
          >
            {t.common.screenshot}
          </button>
          {device.connection === 'usb' && (
            <button
              type="button"
              onClick={handleEnableWifi}
              className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
            >
              {t.devices.enableWifi}
            </button>
          )}
        </div>
      )}

      {ready && (
        <div className="flex items-center gap-2 border-t border-ink-100 pt-3">
          <input
            type="text"
            value={uninstallTarget}
            onChange={(e) => setUninstallTarget(e.target.value)}
            placeholder={t.common.packageName}
            className="min-w-0 flex-1 rounded-lg border border-ink-200 px-2.5 py-1.5 text-xs outline-none focus:border-coral-400"
          />
          <button
            type="button"
            disabled={busy || !uninstallTarget.trim()}
            onClick={handleUninstall}
            className="rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200 disabled:opacity-40"
          >
            {t.common.uninstall}
          </button>
        </div>
      )}

      {ready && <p className="text-center text-[11px] text-ink-400">{t.devices.dropHint}</p>}
    </Card>
  )
}
