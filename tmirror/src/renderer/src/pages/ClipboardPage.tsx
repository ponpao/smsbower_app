import { useState } from 'react'
import { TopBar } from '../components/TopBar'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { useDevices } from '../state/useDevices'
import { useI18n } from '../i18n/I18nContext'
import { useToast } from '../state/ToastContext'

export function ClipboardPage(): JSX.Element {
  const { devices } = useDevices()
  const { t } = useI18n()
  const { push } = useToast()
  const readyDevices = devices.filter((d) => d.status === 'ready')
  const [serial, setSerial] = useState('')
  const [pcClipboard, setPcClipboard] = useState('')
  const [outgoing, setOutgoing] = useState('')
  const [sending, setSending] = useState(false)

  async function handleReadPc(): Promise<void> {
    const result = await window.tmirror.clipboard.readPc()
    if (result.ok) {
      setPcClipboard(result.text ?? '')
      push(t.toast.copiedFromPc, 'success')
    }
  }

  async function handleSend(): Promise<void> {
    if (!serial || !outgoing.trim()) return
    setSending(true)
    const result = await window.tmirror.clipboard.sendToDevice(serial, outgoing)
    setSending(false)
    push(result.ok ? t.toast.sentToDevice : result.message ?? t.toast.sendFailed, result.ok ? 'success' : 'error')
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar title={t.clipboard.title} subtitle={t.clipboard.subtitle} />
      <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-8 py-6">
        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.clipboard.pcClipboard}</h2>
          <p className="mt-1 text-xs text-ink-500">{t.clipboard.pcClipboardHint}</p>
          <textarea
            readOnly
            value={pcClipboard}
            rows={3}
            className="mt-3 w-full resize-none rounded-lg border border-ink-200 bg-ink-50 px-3 py-2 text-sm text-ink-700 outline-none"
          />
          <button
            type="button"
            onClick={handleReadPc}
            className="mt-3 rounded-lg bg-ink-100 px-4 py-2 text-sm font-medium text-ink-700 hover:bg-ink-200"
          >
            {t.clipboard.refreshFromPc}
          </button>
        </Card>

        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.clipboard.sendTitle}</h2>
          <p className="mt-1 text-xs text-ink-500">{t.clipboard.sendHint}</p>

          {readyDevices.length === 0 ? (
            <div className="mt-3">
              <EmptyState title={t.clipboard.selectDevice} />
            </div>
          ) : (
            <>
              <select
                value={serial}
                onChange={(e) => setSerial(e.target.value)}
                className="mt-3 w-full rounded-lg border border-ink-200 px-3 py-2 text-sm"
              >
                <option value="">{t.clipboard.selectDevice}</option>
                {readyDevices.map((d) => (
                  <option key={d.serial} value={d.serial}>
                    {d.model ?? d.serial}
                  </option>
                ))}
              </select>
              <textarea
                value={outgoing}
                onChange={(e) => setOutgoing(e.target.value)}
                placeholder={t.clipboard.placeholder}
                rows={3}
                className="mt-3 w-full resize-none rounded-lg border border-ink-200 px-3 py-2 text-sm outline-none focus:border-coral-400"
              />
              <button
                type="button"
                disabled={sending || !serial || !outgoing.trim()}
                onClick={handleSend}
                className="mt-3 rounded-lg bg-coral-500 px-4 py-2 text-sm font-semibold text-white hover:bg-coral-600 disabled:opacity-50"
              >
                {t.common.send}
              </button>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
