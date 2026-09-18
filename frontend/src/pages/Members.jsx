import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { membersApi, usersApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, checkPassword } from '../utils/passwordPolicy'
import { useAuth } from '../context/AuthContext'
import LocationFields from '../components/LocationFields'
import { BadgeCheck, MailCheck, Plus, Search, X } from 'lucide-react'

const EMPTY_FORM = {
  full_name: '', father_or_husband_name: '', date_of_birth: '', gender: '', aadhaar_number: '',
  phone: '', address: '', village: '', mandal: '', district: '', annual_income: '',
  email: '', password: '', state: 'Andhra Pradesh',
}

const optional = ['father_or_husband_name', 'date_of_birth', 'gender', 'aadhaar_number']

function TextField({ label, className = '', ...props }) {
  return <div className={className}><label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">{label}</label><input {...props} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none transition placeholder:text-ink/30 focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" /></div>
}

function CitizenRegistrationModal({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [step, setStep] = useState('details')
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  const requestVerification = async (event) => {
    event.preventDefault()
    setError('')
    // Caught here so the officer fixes it at the counter, rather than after
    // the citizen has already been emailed a code for an account that the
    // API will refuse to create.
    const policyError = checkPassword(form.password)
    if (policyError) { setError(policyError); return }
    setSaving(true)
    try {
      const profile = { ...form, annual_income: form.annual_income ? Number(form.annual_income) : null }
      delete profile.email; delete profile.password
      optional.forEach((field) => { if (!profile[field]) profile[field] = null })
      const result = await usersApi.requestCreate({
        full_name: form.full_name, email: form.email, phone: form.phone, password: form.password,
        role: 'citizen', district: form.district, mandal: form.mandal, village: form.village,
        member_profile: profile,
      })
      setMessage(result.data.message); setStep('verify'); setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not begin citizen registration.'))
    } finally { setSaving(false) }
  }

  const resendCode = async () => {
    setError('')
    try {
      const profile = { ...form, annual_income: form.annual_income ? Number(form.annual_income) : null }
      delete profile.email; delete profile.password
      optional.forEach((field) => { if (!profile[field]) profile[field] = null })
      const result = await usersApi.requestCreate({
        full_name: form.full_name, email: form.email, phone: form.phone, password: form.password,
        role: 'citizen', district: form.district, mandal: form.mandal, village: form.village,
        member_profile: profile,
      })
      setMessage(result.data.message || 'A new code has been sent.'); setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not resend the code.'))
    }
  }

  const verifyAndCreate = async (event) => {
    event.preventDefault()
    setError(''); setSaving(true)
    try {
      await usersApi.confirmCreate(form.email, code)
      onCreated(); onClose()
    } catch (err) {
      setError(formatApiError(err, 'Could not verify this email.'))
    } finally { setSaving(false) }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-panchayat-900/45 p-4 backdrop-blur-sm">
    <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-paper shadow-2xl pp-scrollbar">
      <div className="flex items-center justify-between border-b border-ink/10 px-6 py-5"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-marigold-600">Verified onboarding</p><h2 className="mt-1 font-display text-2xl text-panchayat-900">Register a citizen</h2></div><button onClick={onClose} aria-label="Close registration" className="grid h-9 w-9 place-items-center rounded-full text-ink/55 hover:bg-panchayat-50"><X size={19} /></button></div>
      {step === 'details' ? <form onSubmit={requestVerification} className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-2">
        <div className="sm:col-span-2 rounded-2xl border border-panchayat-100 bg-panchayat-50 px-4 py-3 text-sm text-panchayat-700"><span className="flex gap-2"><MailCheck size={18} className="mt-0.5 shrink-0 text-marigold-600" />The citizen’s email is verified with an OTP before the portal login is created. After verification, their login ID and temporary password are emailed automatically.</span></div>
        <TextField required label="Name" value={form.full_name} onChange={update('full_name')} />
        <TextField label="Father / husband name" value={form.father_or_husband_name} onChange={update('father_or_husband_name')} />
        <TextField label="Date of birth" type="date" value={form.date_of_birth} onChange={update('date_of_birth')} />
        <div><label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">Gender</label><select value={form.gender} onChange={update('gender')} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-panchayat-500"><option value="">Select gender</option><option>Female</option><option>Male</option><option>Other</option></select></div>
        <TextField label="Aadhaar number" inputMode="numeric" minLength="12" maxLength="12" value={form.aadhaar_number} onChange={update('aadhaar_number')} placeholder="12-digit Aadhaar" />
        <TextField required label="Mobile number" inputMode="tel" value={form.phone} onChange={update('phone')} />
        <TextField required label="Address" className="sm:col-span-2" value={form.address} onChange={update('address')} />
        <LocationFields form={form} update={update} />
        <TextField label="Annual income (₹)" type="number" min="0" value={form.annual_income} onChange={update('annual_income')} />
        <TextField required label="Email ID (OTP verified)" className="sm:col-span-2" type="email" value={form.email} onChange={update('email')} />
        <TextField required label="Temporary password" className="sm:col-span-2" type="password" minLength={MIN_PASSWORD_LENGTH} value={form.password} onChange={update('password')} placeholder={PASSWORD_HINT} />
        {error && <div className="rounded-xl bg-brick-100 px-3 py-2 text-sm text-brick-600 sm:col-span-2">{error}</div>}
        <div className="flex justify-end gap-3 pt-2 sm:col-span-2"><button type="button" onClick={onClose} className="px-4 py-2.5 text-sm font-semibold text-ink/55">Cancel</button><button disabled={saving} className="rounded-xl bg-panchayat-700 px-5 py-2.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 hover:bg-panchayat-600 disabled:opacity-50">{saving ? 'Sending OTP…' : 'Send verification OTP'}</button></div>
      </form> : <form onSubmit={verifyAndCreate} className="p-6"><div className="rounded-2xl bg-panchayat-50 p-5 text-sm leading-6 text-panchayat-700"><BadgeCheck className="mb-2 text-marigold-600" size={22} />{message || `A verification code was sent to ${form.email}.`}</div><p className="mt-5 text-sm text-ink/65">Ask the citizen for the 6-digit code from their inbox. Once confirmed, the member record and their citizen login are created together.</p><TextField required label="Email OTP" maxLength="6" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} placeholder="000000" className="mt-5" /><button type="button" onClick={resendCode} disabled={resendCooldown > 0} className="mt-2 text-xs font-semibold text-panchayat-600 hover:underline disabled:text-ink/35 disabled:no-underline">{resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}</button>{error && <div className="mt-4 rounded-xl bg-brick-100 px-3 py-2 text-sm text-brick-600">{error}</div>}<div className="mt-6 flex justify-end gap-3"><button type="button" onClick={() => setStep('details')} className="px-4 py-2.5 text-sm font-semibold text-ink/55">Back</button><button disabled={saving || code.length !== 6} className="rounded-xl bg-panchayat-700 px-5 py-2.5 text-sm font-semibold text-paper hover:bg-panchayat-600 disabled:opacity-50">{saving ? 'Creating…' : 'Verify & create citizen'}</button></div></form>}
    </div>
  </div>
}

export default function Members() {
  const { t } = useTranslation(); const { user } = useAuth()
  const [members, setMembers] = useState([]); const [search, setSearch] = useState(''); const [showModal, setShowModal] = useState(false); const [loading, setLoading] = useState(true)
  const load = () => { setLoading(true); membersApi.list({ search: search || undefined }).then((res) => setMembers(res.data)).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])
  useEffect(() => { const timer = setTimeout(load, 350); return () => clearTimeout(timer) }, [search])
  const canRegister = user.role === 'admin'

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><div className="mb-1 text-xs uppercase tracking-widest text-marigold-600">Andhra Pradesh household register</div><h1 className="font-display text-3xl text-panchayat-700">{t('members.title')}</h1><p className="mt-1 text-sm text-ink/55">Records are automatically limited to your permitted district and mandal.</p></div>{canRegister && <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-xl bg-panchayat-700 px-4 py-2.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:-translate-y-0.5 hover:bg-panchayat-600"><Plus size={16} /> Register citizen</button>}</div>
    <div className="relative max-w-md"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/40" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, village, or mobile…" className="w-full rounded-xl border border-ink/10 bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" /></div>
    <div className="overflow-x-auto rounded-2xl border border-ink/10 bg-white shadow-sm"><table className="w-full min-w-[780px] text-sm"><thead><tr className="border-b border-ink/7 bg-[#fbfaf7] text-left text-[11px] font-bold uppercase tracking-[.1em] text-ink/45"><th className="px-5 py-3">Citizen</th><th className="px-5 py-3">District / mandal</th><th className="px-5 py-3">Village</th><th className="px-5 py-3">Mobile</th><th className="px-5 py-3">Income</th><th className="px-5 py-3">Portal</th></tr></thead><tbody>{members.map((member) => <tr key={member.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/35"><td className="px-5 py-3 font-semibold text-ink">{member.full_name}<div className="mt-0.5 text-xs font-normal text-ink/45">{member.father_or_husband_name || '—'}</div></td><td className="px-5 py-3 text-ink/65">{member.district || '—'}<div className="mt-0.5 text-xs text-ink/45">{member.mandal || '—'}</div></td><td className="px-5 py-3 text-ink/65">{member.village}</td><td className="px-5 py-3 text-ink/65">{member.phone || '—'}</td><td className="px-5 py-3 text-ink/65">{member.annual_income ? `₹${member.annual_income.toLocaleString('en-IN')}` : '—'}</td><td className="px-5 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${member.user_id ? 'bg-panchayat-100 text-panchayat-700' : 'bg-sand text-ink/55'}`}>{member.user_id ? 'Verified login' : 'Record only'}</span></td></tr>)}{!loading && !members.length && <tr><td colSpan="6" className="px-5 py-12 text-center text-ink/40">No citizens found in this jurisdiction.</td></tr>}</tbody></table></div>
    {showModal && <CitizenRegistrationModal onClose={() => setShowModal(false)} onCreated={load} />}
  </div>
}
