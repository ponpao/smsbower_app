import { useI18n } from '../i18n/I18nContext'
import { CambodiaFlag } from '../assets/flags/CambodiaFlag'
import { UsFlag } from '../assets/flags/UsFlag'

export function FlagSwitch(): JSX.Element {
  const { lang, setLang } = useI18n()

  return (
    <div className="flex items-center gap-2" role="group" aria-label="Language / ភាសា">
      <button
        type="button"
        aria-label="ខ្មែរ"
        aria-pressed={lang === 'km'}
        onClick={() => setLang('km')}
        className={`h-8 w-10 overflow-hidden rounded-md ring-offset-2 transition ${
          lang === 'km' ? 'accent-ring ring-2 opacity-100' : 'opacity-50 hover:opacity-80'
        }`}
      >
        <CambodiaFlag className="h-full w-full" />
      </button>
      <button
        type="button"
        aria-label="English"
        aria-pressed={lang === 'en'}
        onClick={() => setLang('en')}
        className={`h-8 w-10 overflow-hidden rounded-md ring-offset-2 transition ${
          lang === 'en' ? 'accent-ring ring-2 opacity-100' : 'opacity-50 hover:opacity-80'
        }`}
      >
        <UsFlag className="h-full w-full" />
      </button>
    </div>
  )
}
