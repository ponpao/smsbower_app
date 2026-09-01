import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import en, { type Dictionary } from './en'
import km from './km'

export type Lang = 'km' | 'en'

const STORAGE_KEY = 'tmirror.lang'
const dictionaries: Record<Lang, Dictionary> = { en, km }

function detectDefaultLang(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'km' || stored === 'en') return stored
  } catch {
    // localStorage unavailable — fall through to locale detection
  }
  const locales = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language]
  const isKhmer = locales.some((l) => l?.toLowerCase().startsWith('km'))
  return isKhmer ? 'km' : 'en'
}

interface I18nContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: Dictionary
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }): JSX.Element {
  const [lang, setLangState] = useState<Lang>(() => detectDefaultLang())

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.classList.toggle('font-khmer', lang === 'km')
    document.documentElement.classList.toggle('font-latin', lang === 'en')
    try {
      window.localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      // best-effort persistence only
    }
  }, [lang])

  const setLang = useCallback((next: Lang) => setLangState(next), [])

  const value = useMemo<I18nContextValue>(() => ({ lang, setLang, t: dictionaries[lang] }), [lang, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
