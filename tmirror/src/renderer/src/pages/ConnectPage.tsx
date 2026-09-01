import { useEffect, useRef, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { Card } from '../components/Card'
import { useI18n } from '../i18n/I18nContext'
import type { PairSession, PairSessionState } from '@shared/types'

function formatCountdown(expiresAt: number): string {
  const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000))
  const m = Math.floor(remaining / 60)
  const s = remaining % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function ConnectPage(): JSX.Element {
  const { t } = useI18n()
  const [session, setSession] = useState<PairSession | null>(null)
  const [state, setState] = useState<PairSessionState>('pending')
  const [countdown, setCountdown] = useState('')
  const [error, setError] = useState<string | null>(null)
  const unsubscribeRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    unsubscribeRef.current = window.tmirror.pair.onStatus((event) => {
      setState(event.state)
    })
    return () => {
      unsubscribeRef.current?.()
      window.tmirror.pair.cancelSession()
    }
  }, [])

  useEffect(() => {
    if (!session) return
    const interval = setInterval(() => setCountdown(formatCountdown(session.expiresAt)), 500)
    setCountdown(formatCountdown(session.expiresAt))
    return () => clearInterval(interval)
  }, [session])

  async function handleGenerate(): Promise<void> {
    setError(null)
    try {
      const s = await window.tmirror.pair.createSession()
      setSession(s)
      setState('pending')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function handleCancel(): Promise<void> {
    await window.tmirror.pair.cancelSession()
    setSession(null)
    setState('pending')
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar title={t.connect.title} subtitle={t.connect.subtitle} />
      <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-8 py-6">
        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.connect.usbTitle}</h2>
          <ol className="mt-3 flex flex-col gap-2.5 text-sm text-ink-700">
            <li className="flex gap-2">
              <span className="font-semibold text-coral-500">1.</span>
              {t.connect.usbStep1}
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-coral-500">2.</span>
              {t.connect.usbStep2}
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-coral-500">3.</span>
              {t.connect.usbStep3}
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-coral-500">4.</span>
              {t.connect.usbStep4}
            </li>
          </ol>
        </Card>

        <Card className="max-w-xl bg-ink-50/50">
          <p className="text-sm font-medium text-ink-800">{t.connect.android9Notice}</p>
          <p className="mt-1 text-xs text-ink-500">{t.connect.android9Sub}</p>
        </Card>

        <Card className="max-w-xl">
          <h2 className="text-base font-semibold text-ink-900">{t.connect.qrTitle}</h2>
          <p className="mt-2 text-sm text-ink-600">{t.connect.qrBody}</p>

          {error && <p className="mt-3 rounded-lg bg-coral-50 px-3 py-2 text-xs text-coral-700">{error}</p>}

          {!session ? (
            <button
              type="button"
              onClick={handleGenerate}
              className="mt-4 rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-600"
            >
              {t.connect.qrGenerate}
            </button>
          ) : (
            <div className="mt-4 flex flex-col items-center gap-3">
              <img
                src={session.qrDataUrl}
                alt={t.connect.qrTitle}
                className="h-48 w-48 rounded-xl border border-ink-200 bg-white p-2"
              />
              <p className="text-xs text-ink-500">
                {t.connect.qrExpires} {countdown}
              </p>
              {state === 'pending' && (
                <p className="text-sm font-medium text-ink-700">{t.connect.qrWaiting}</p>
              )}
              {state === 'confirmed' && (
                <p className="text-sm font-medium text-teal-600">{t.connect.qrConfirmed}</p>
              )}
              {state === 'expired' && (
                <p className="text-sm font-medium text-coral-600">{t.connect.qrExpiredMsg}</p>
              )}
              <button
                type="button"
                onClick={handleCancel}
                className="rounded-lg bg-ink-100 px-4 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-200"
              >
                {t.connect.qrCancel}
              </button>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
