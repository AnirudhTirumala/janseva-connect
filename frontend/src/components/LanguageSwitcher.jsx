import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { code: 'en', label: 'EN' },
  { code: 'hi', label: 'हि' },
  { code: 'te', label: 'తె' },
]

export default function LanguageSwitcher({ variant = 'sidebar' }) {
  const { i18n } = useTranslation()

  const handleChange = (code) => {
    i18n.changeLanguage(code)
    localStorage.setItem('pp_lang', code)
  }

  const isDark = variant === 'sidebar' || variant === 'onDark'

  return (
    <div className={`inline-flex rounded-sm p-0.5 gap-0.5 ${isDark ? 'bg-panchayat-800/60' : 'bg-sand'}`}>
      {LANGUAGES.map((lang) => {
        const active = i18n.language === lang.code
        return (
          <button
            key={lang.code}
            onClick={() => handleChange(lang.code)}
            className={`px-2.5 py-1.5 rounded-sm text-xs font-medium transition-colors ${
              active
                ? 'bg-marigold-500 text-panchayat-900'
                : isDark
                ? 'text-panchayat-100/70 hover:text-paper hover:bg-panchayat-600'
                : 'text-ink/60 hover:text-ink hover:bg-white'
            }`}
          >
            {lang.label}
          </button>
        )
      })}
    </div>
  )
}
