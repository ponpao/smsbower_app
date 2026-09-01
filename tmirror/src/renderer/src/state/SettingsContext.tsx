import { createContext, type ReactNode, useContext, useEffect, useState } from 'react'
import type { Settings } from '@shared/types'

const DEFAULTS: Settings = { language: 'en', adbPath: null, scrcpyPath: null, accent: 'coral' }

interface SettingsContextValue {
  settings: Settings
  update: (partial: Partial<Settings>) => Promise<void>
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }): JSX.Element {
  const [settings, setSettings] = useState<Settings>(DEFAULTS)

  useEffect(() => {
    window.tmirror.settings.get().then(setSettings)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.accent = settings.accent
  }, [settings.accent])

  async function update(partial: Partial<Settings>): Promise<void> {
    const next = { ...settings, ...partial }
    setSettings(next)
    await window.tmirror.settings.set(next)
  }

  return <SettingsContext.Provider value={{ settings, update }}>{children}</SettingsContext.Provider>
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
