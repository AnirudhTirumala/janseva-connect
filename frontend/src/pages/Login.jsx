import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { formatApiError } from '../utils/formatApiError'
import LanguageSwitcher from '../components/LanguageSwitcher'
import {
  ArrowLeft, ArrowRight, Award, CheckCircle2, ClipboardCheck,
  Clock, FileText, Landmark, LockKeyhole, MessageCircleQuestion,
  ShieldCheck, Sparkles, X,
} from 'lucide-react'

const FEATURES = [
  { icon: FileText, title: 'Apply with confidence', text: 'Keep schemes, documents, and requests in one clear place.' },
  { icon: ClipboardCheck, title: 'See every update', text: 'Follow your application from submission to a final decision.' },
  { icon: Award, title: 'Keep records close', text: 'Request and download official certificates without another visit.' },
]

function AboutModal({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-panchayat-900/45 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-y-auto rounded-3xl bg-paper shadow-2xl pp-scrollbar max-h-[85vh]">
        <div className="flex items-center justify-between border-b border-ink/10 px-6 py-5">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-marigold-600">Built for citizens</p>
            <h2 className="mt-1 font-display text-2xl text-panchayat-800">About this platform</h2>
          </div>
          <button onClick={onClose} aria-label="Close about this platform" className="grid h-9 w-9 place-items-center rounded-full text-ink/60 transition hover:bg-panchayat-50 hover:text-panchayat-700"><X size={19} /></button>
        </div>

        <div className="space-y-7 p-6">
          <div>
            <h3 className="font-display text-lg text-panchayat-700">What you can do here</h3>
            <ul className="mt-4 space-y-4 text-sm leading-6 text-ink/70">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-marigold-100 text-marigold-600"><Icon size={14} /></span><span><strong className="block font-semibold text-ink">{title}</strong>{text}</span></li>
              ))}
              <li className="flex gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-marigold-100 text-marigold-600"><MessageCircleQuestion size={14} /></span><span><strong className="block font-semibold text-ink">Ask for help</strong>Use the AI assistant for scheme eligibility, required documents, or portal guidance.</span></li>
            </ul>
          </div>

          <div className="rounded-2xl bg-panchayat-50 p-5">
            <h3 className="font-display text-lg text-panchayat-700">Why it exists</h3>
            <p className="mt-2 text-sm leading-6 text-ink/70">Paper files make records difficult to follow and office visits harder to plan. This portal makes services available from home while keeping every decision visible and accountable.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <p className="flex gap-2 text-xs leading-5 text-panchayat-700"><Clock size={15} className="mt-0.5 shrink-0 text-marigold-600" /> Services are available when your household needs them.</p>
              <p className="flex gap-2 text-xs leading-5 text-panchayat-700"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-marigold-600" /> Reviews and decisions remain transparent.</p>
            </div>
          </div>

          <button onClick={onClose} className="w-full rounded-xl bg-panchayat-700 py-3 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:bg-panchayat-600">Continue to sign in</button>
        </div>
      </div>
    </div>
  )
}

export default function Login() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showAbout, setShowAbout] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(formatApiError(err, 'Login failed. Check your credentials.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page relative h-screen overflow-hidden bg-[#f8f7f2] p-4 lg:grid lg:grid-cols-[1.12fr_.88fr] lg:gap-6 lg:p-6">
      <div className="login-halo login-halo-one" aria-hidden="true" />
      <div className="login-halo login-halo-two" aria-hidden="true" />

      <section className="relative hidden overflow-hidden rounded-[2rem] bg-panchayat-700 p-8 text-paper shadow-2xl shadow-panchayat-900/15 lg:flex lg:h-[calc(100vh-3rem)] lg:flex-col">
        <div className="login-pattern" aria-hidden="true" />
        <div className="relative z-10 flex shrink-0 items-center justify-between">
          <Link to="/" className="flex items-center gap-3" aria-label="Back to JanSeva Connect home">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-marigold-300 text-panchayat-900 shadow-lg shadow-panchayat-900/20"><Landmark size={21} /></span>
            <span><span className="block font-display text-xl leading-none">JanSeva Connect</span><span className="mt-1 block text-[9px] font-bold uppercase tracking-[0.22em] text-panchayat-100/70">Andhra Pradesh citizen services</span></span>
          </Link>
          <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-panchayat-100/80 transition hover:text-paper"><ArrowLeft size={14} /> Home</Link>
        </div>

        <div className="relative z-10 my-auto max-w-xl overflow-y-auto pp-scrollbar">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-xs font-semibold text-marigold-300"><Sparkles size={13} /> A simpler way to access local services</div>
          <h1 className="mt-5 font-display text-4xl leading-[1.05] tracking-[-0.04em] xl:text-5xl">Every service,<br /><span className="text-marigold-300">within reach.</span></h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-panchayat-100/75">Sign in to manage your household services, follow requests, and stay connected with your Panchayat office.</p>

          <div className="mt-6 space-y-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="flex max-w-md gap-3 rounded-2xl border border-white/8 bg-white/5 p-3.5 backdrop-blur-sm"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-marigold-300 text-panchayat-900"><Icon size={17} /></span><span><strong className="block text-sm text-paper">{title}</strong><span className="mt-0.5 block text-xs leading-5 text-panchayat-100/65">{text}</span></span></div>
            ))}
          </div>
        </div>

        <div className="relative z-10 flex shrink-0 items-center gap-2 text-xs text-panchayat-100/65"><LockKeyhole size={14} className="text-marigold-300" /> Protected access for citizens, staff, and administrators.</div>
      </section>

      <section className="relative z-10 flex h-[calc(100vh-2rem)] items-center justify-center overflow-y-auto py-6 pp-scrollbar lg:h-[calc(100vh-3rem)]">
        <div className="absolute right-0 top-0 flex items-center gap-3 lg:right-6 lg:top-5"><Link to="/" className="hidden items-center gap-1.5 text-xs font-semibold text-panchayat-700 sm:inline-flex lg:hidden"><ArrowLeft size={14} /> Home</Link><LanguageSwitcher variant="onLight" /></div>
        <div className="w-full max-w-md pt-10 lg:pt-0">
          <div className="mb-7 text-center lg:hidden"><Link to="/" className="inline-flex items-center gap-2"><span className="grid h-10 w-10 place-items-center rounded-xl bg-marigold-300 text-panchayat-900"><Landmark size={19} /></span><span className="font-display text-xl text-panchayat-800">JanSeva Connect</span></Link></div>
          <div className="login-card rounded-[1.75rem] border border-white/80 bg-white/85 p-6 shadow-2xl shadow-panchayat-900/10 backdrop-blur-xl sm:p-8">
            <div className="mb-7">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-marigold-600">Welcome back</p>
              <h2 className="mt-2 font-display text-3xl text-panchayat-800">{t('login.title')}</h2>
              <p className="mt-2 text-sm leading-6 text-ink/60">{t('login.subtitle')}</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.12em] text-ink/55">{t('login.email')}</label>
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-xl border border-ink/10 bg-[#fcfcfa] px-4 py-3 text-sm text-ink outline-none transition placeholder:text-ink/30 focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" placeholder="you@example.com" />
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between"><label className="text-[11px] font-bold uppercase tracking-[0.12em] text-ink/55">{t('login.password')}</label><Link to="/forgot-password" className="text-xs font-semibold text-panchayat-600 transition hover:text-panchayat-800 hover:underline">{t('login.forgotPassword')}</Link></div>
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-xl border border-ink/10 bg-[#fcfcfa] px-4 py-3 text-sm text-ink outline-none transition placeholder:text-ink/30 focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" placeholder="••••••••" />
              </div>

              {error && <div className="rounded-xl border border-brick-500/15 bg-brick-100 px-3.5 py-3 text-sm text-brick-600">{error}</div>}

              <button type="submit" disabled={loading} className="group flex w-full items-center justify-center gap-2 rounded-xl bg-panchayat-700 py-3.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:-translate-y-0.5 hover:bg-panchayat-600 disabled:cursor-not-allowed disabled:opacity-60">{loading ? t('login.signingIn') : t('login.signIn')} {!loading && <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />}</button>
            </form>

            <div className="my-6 h-px bg-ink/8" />
            <p className="text-center text-sm text-ink/60">{t('login.newCitizen')} <Link to="/register" className="font-semibold text-panchayat-600 transition hover:text-panchayat-800 hover:underline">{t('login.createAccount')}</Link></p>
          </div>

          <button onClick={() => setShowAbout(true)} className="mx-auto mt-6 flex items-center gap-2 text-xs font-medium text-panchayat-700/65 transition hover:text-panchayat-800"><ShieldCheck size={14} className="text-marigold-600" /> About this platform &amp; why it exists</button>
        </div>
      </section>

      {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
    </div>
  )
}
