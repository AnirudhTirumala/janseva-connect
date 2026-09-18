import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, checkPassword } from '../utils/passwordPolicy'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { ArrowLeft, ArrowRight, KeyRound, Landmark, LockKeyhole, Mail, ShieldCheck, Sparkles } from 'lucide-react'

const STEPS = [
  { icon: Mail, title: '1. Enter your registered email', text: "We'll send a one-time code to confirm it's you." },
  { icon: KeyRound, title: '2. Verify with the code', text: 'Enter the 6-digit code we email you.' },
  { icon: ShieldCheck, title: '3. Set a new password', text: 'Choose a fresh password and sign back in right away.' },
]

const input = 'w-full rounded-xl border border-ink/10 bg-[#fcfcfa] px-4 py-3 text-sm text-ink outline-none transition placeholder:text-ink/30 focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50'

export default function ForgotPassword() {
  const { t } = useTranslation()
  const [step, setStep] = useState('email') // 'email' | 'reset'
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [info, setInfo] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const { loginWithResetToken } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  const handleSendCode = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authApi.requestPasswordReset(email)
      setInfo(res.data.message)
      setStep('reset')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not send a reset code. Please try again.'))
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    setError('')
    try {
      const res = await authApi.requestPasswordReset(email)
      setInfo(res.data.message || 'A new code has been sent.')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not resend the code.'))
    }
  }

  const handleReset = async (e) => {
    e.preventDefault()
    setError('')
    const policyError = checkPassword(newPassword)
    if (policyError) {
      setError(policyError)
      return
    }
    setLoading(true)
    try {
      await loginWithResetToken(email, code, newPassword)
      navigate('/')
    } catch (err) {
      setError(formatApiError(err, 'Could not reset your password. Please try again.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="forgot-password-page relative h-screen overflow-hidden bg-[#f8f7f2] p-4 lg:grid lg:grid-cols-[1.05fr_.95fr] lg:gap-6 lg:p-6">
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
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-xs font-semibold text-marigold-300"><Sparkles size={13} /> Account recovery</div>
          <h1 className="mt-5 font-display text-4xl leading-[1.05] tracking-[-0.04em] xl:text-5xl">Back in,<br /><span className="text-marigold-300">safely.</span></h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-panchayat-100/75">Reset your password in a couple of steps and get straight back to your services.</p>

          <div className="mt-6 space-y-3">
            {STEPS.map(({ icon: Icon, title, text }) => (
              <div key={title} className="flex max-w-md gap-3 rounded-2xl border border-white/8 bg-white/5 p-3.5 backdrop-blur-sm"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-marigold-300 text-panchayat-900"><Icon size={17} /></span><span><strong className="block text-sm text-paper">{title}</strong><span className="mt-0.5 block text-xs leading-5 text-panchayat-100/65">{text}</span></span></div>
            ))}
          </div>
        </div>

        <div className="relative z-10 flex shrink-0 items-center gap-2 text-xs text-panchayat-100/65"><LockKeyhole size={14} className="text-marigold-300" /> Only you can reset your password - the code goes straight to your registered email.</div>
      </section>

      <section className="relative z-10 flex h-[calc(100vh-2rem)] items-center justify-center overflow-y-auto py-6 pp-scrollbar lg:h-[calc(100vh-3rem)]">
        <div className="absolute right-0 top-0 flex items-center gap-3 lg:right-6 lg:top-5"><Link to="/" className="hidden items-center gap-1.5 text-xs font-semibold text-panchayat-700 sm:inline-flex lg:hidden"><ArrowLeft size={14} /> Home</Link><LanguageSwitcher variant="onLight" /></div>
        <div className="w-full max-w-md pt-10 lg:pt-0">
          <div className="mb-7 text-center lg:hidden"><Link to="/" className="inline-flex items-center gap-2"><span className="grid h-10 w-10 place-items-center rounded-xl bg-marigold-300 text-panchayat-900"><Landmark size={19} /></span><span className="font-display text-xl text-panchayat-800">JanSeva Connect</span></Link></div>
          <div className="login-card rounded-[1.75rem] border border-white/80 bg-white/85 p-6 shadow-2xl shadow-panchayat-900/10 backdrop-blur-xl sm:p-8">
            <div className="mb-7">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-marigold-600">Password reset</p>
              <h2 className="mt-2 font-display text-3xl text-panchayat-800">{t('forgotPassword.title')}</h2>
              <p className="mt-2 text-sm leading-6 text-ink/60">{step === 'email' ? t('forgotPassword.subtitleEmail') : t('forgotPassword.subtitleReset')}</p>
            </div>

            {step === 'email' ? (
              <form onSubmit={handleSendCode} className="space-y-5">
                <div>
                  <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.12em] text-ink/55">{t('common.email')}</label>
                  <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="you@example.com" />
                </div>

                {error && <div className="rounded-xl border border-brick-500/15 bg-brick-100 px-3.5 py-3 text-sm text-brick-600">{error}</div>}

                <button type="submit" disabled={loading} className="group flex w-full items-center justify-center gap-2 rounded-xl bg-panchayat-700 py-3.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:-translate-y-0.5 hover:bg-panchayat-600 disabled:cursor-not-allowed disabled:opacity-60">{loading ? t('forgotPassword.sendingCode') : t('forgotPassword.sendCode')} {!loading && <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />}</button>

                <div className="my-6 h-px bg-ink/8" />
                <p className="text-center text-sm text-ink/60"><Link to="/login" className="font-semibold text-panchayat-600 transition hover:text-panchayat-800 hover:underline">{t('forgotPassword.backToSignIn')}</Link></p>
              </form>
            ) : (
              <form onSubmit={handleReset} className="space-y-5">
                {info && <div className="rounded-xl border border-panchayat-100 bg-panchayat-50 px-3.5 py-3 text-sm leading-6 text-panchayat-700">{info}</div>}

                <div>
                  <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.12em] text-ink/55">{t('register.verifyCode')}</label>
                  <input required maxLength={6} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} className={`${input} py-3 text-center font-mono text-lg tracking-[0.45em]`} placeholder="000000" />
                  <button type="button" onClick={handleResendCode} disabled={resendCooldown > 0} className="mt-2 text-xs font-semibold text-panchayat-600 hover:underline disabled:text-ink/35 disabled:no-underline">{resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}</button>
                </div>
                <div>
                  <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.12em] text-ink/55">{t('common.newPassword')}</label>
                  <input type="password" required minLength={MIN_PASSWORD_LENGTH} autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={input} placeholder={PASSWORD_HINT} />
                </div>

                {error && <div className="rounded-xl border border-brick-500/15 bg-brick-100 px-3.5 py-3 text-sm text-brick-600">{error}</div>}

                <button type="submit" disabled={loading || code.length !== 6} className="flex w-full items-center justify-center gap-2 rounded-xl bg-panchayat-700 py-3.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:-translate-y-0.5 hover:bg-panchayat-600 disabled:cursor-not-allowed disabled:opacity-60">{loading ? t('forgotPassword.resetting') : t('forgotPassword.resetButton')}</button>
                <button type="button" onClick={() => { setStep('email'); setCode(''); setError('') }} className="w-full text-center text-xs font-semibold text-ink/50 transition hover:text-panchayat-700">{t('forgotPassword.useDifferentEmail')}</button>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
