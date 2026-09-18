import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { dashboardApi, membersApi, weeklyActivitiesApi } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import { formatApiError } from '../utils/formatApiError'
import LocationFields from '../components/LocationFields'
import {
  ArrowRight, ArrowUpRight, Award, BarChart3, CalendarDays, CheckCircle2, ChevronRight,
  CircleAlert, CircleDot, ClipboardList, Clock3, Command, FileText, MapPin, ShieldCheck,
  Sparkles, TrendingUp, UserRound, Users, X, Send,
} from 'lucide-react'

const STATUS_COLORS = {
  pending: '#E32626',
  under_review: '#777777',
  approved: '#101010',
  rejected: '#A60E0E',
}

const EMPTY_PROFILE = {
  full_name: '', father_or_husband_name: '', date_of_birth: '', gender: '',
  aadhaar_number: '', address: '', village: '', mandal: '', district: '',
  phone: '', annual_income: '',
}

const OPTIONAL_FIELDS = [
  'father_or_husband_name', 'date_of_birth', 'gender', 'aadhaar_number',
  'mandal', 'district', 'phone',
]

function CompleteProfileModal({ member, onClose, onSaved }) {
  const { user } = useAuth()
  const [form, setForm] = useState({ ...EMPTY_PROFILE, ...(member || {}), full_name: member?.full_name || user?.full_name || '', date_of_birth: member?.date_of_birth?.slice(0, 10) || '' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const update = (field) => (e) => setForm((current) => ({ ...current, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const payload = { ...form }
      OPTIONAL_FIELDS.forEach((field) => {
        if (payload[field] === '') payload[field] = null
      })
      payload.annual_income = form.annual_income ? parseInt(form.annual_income, 10) : null
      if (member) await membersApi.updateMe(payload)
      else await membersApi.createMe(payload)
      onSaved()
      onClose()
    } catch (err) {
      setError(formatApiError(err, 'Could not save your profile.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-panchayat-900/45 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-paper shadow-2xl pp-scrollbar">
        <div className="flex items-center justify-between border-b border-ink/10 px-6 py-5">
          <div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-marigold-600">{member ? 'Keep details current' : 'One-time setup'}</p><h2 className="mt-1 font-display text-2xl text-panchayat-900">{member ? 'Update your household profile' : 'Complete your household profile'}</h2></div>
          <button onClick={onClose} aria-label="Close profile form" className="grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-panchayat-50 hover:text-panchayat-700"><X size={19} /></button>
        </div>
        <p className="px-6 pt-5 text-sm leading-6 text-ink/60">{member ? 'Update your name, Aadhaar number, mobile number, and Andhra Pradesh location whenever they change.' : 'Add your household information so the portal can match you with services. Staff can still review and correct it at the office later.'}</p>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-2">
          <Field label="Full name" required value={form.full_name} onChange={update('full_name')} />
          <Field label="Father/Husband name" value={form.father_or_husband_name} onChange={update('father_or_husband_name')} />
          <Field label="Date of birth" type="date" value={form.date_of_birth} onChange={update('date_of_birth')} />
          <Field label="Gender" value={form.gender} onChange={update('gender')} placeholder="Male / Female / Other" />
          <Field label="Aadhaar number" value={form.aadhaar_number} onChange={update('aadhaar_number')} placeholder="12-digit ID" />
          <Field label="Phone" value={form.phone} onChange={update('phone')} />
          <Field label="Address" required value={form.address} onChange={update('address')} className="sm:col-span-2" />
          <LocationFields form={form} update={update} />
          <Field label="Annual income (₹)" type="number" value={form.annual_income} onChange={update('annual_income')} />
          {error && <div className="rounded-xl border border-brick-500/15 bg-brick-100 px-3.5 py-3 text-sm text-brick-600 sm:col-span-2">{error}</div>}
          <div className="flex justify-end gap-3 pt-2 sm:col-span-2"><button type="button" onClick={onClose} className="px-4 py-2.5 text-sm font-semibold text-ink/55 transition hover:text-ink">{member ? 'Cancel' : 'Not now'}</button><button type="submit" disabled={saving} className="rounded-xl bg-panchayat-700 px-5 py-2.5 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:bg-panchayat-600 disabled:opacity-60">{saving ? 'Saving…' : member ? 'Save updates' : 'Save profile'}</button></div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, className = '', ...props }) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">{label}</label>
      <input {...props} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none transition placeholder:text-ink/30 focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" />
    </div>
  )
}

function MetricCard({ label, value, sub, icon: Icon, tone = 'panchayat' }) {
  const tones = {
    panchayat: 'bg-white text-ink after:bg-ink',
    marigold: 'bg-marigold-100 text-marigold-600 after:bg-marigold-500',
    brick: 'bg-brick-100 text-brick-600 after:bg-brick-500',
  }
  return (
    <div className="dashboard-metric group relative overflow-hidden rounded-[1.6rem] border border-ink/10 bg-white p-5">
      <div className={`absolute bottom-0 left-0 h-1 w-full opacity-80 ${tones[tone].split(' ').pop()}`} />
      <div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.13em] text-ink/45">{label}</p><p className="mt-3 font-display text-4xl leading-none text-ink">{value}</p>{sub && <p className="mt-2 text-xs leading-5 text-ink/52">{sub}</p>}</div><span className={`grid h-11 w-11 place-items-center rounded-2xl ${tones[tone].replace(/ after:.*/, '')}`}><Icon size={18} strokeWidth={2.1} /></span></div>
    </div>
  )
}

function QuickAction({ to, label, detail, icon: Icon, primary = false }) {
  return (
    <Link to={to} className={`dashboard-action group relative overflow-hidden rounded-[1.6rem] border p-5 ${primary ? 'dashboard-action-primary border-transparent text-white' : 'border-ink/10 bg-white text-ink'}`}>
      <div className="flex items-start justify-between gap-3"><span className={`grid h-11 w-11 place-items-center rounded-2xl ${primary ? 'bg-white/14 text-white' : 'bg-ink text-white'}`}><Icon size={18} /></span><ArrowUpRight size={18} className="mt-1 transition-transform group-hover:translate-x-1 group-hover:-translate-y-1" /></div>
      <p className="mt-8 text-sm font-bold">{label}</p><p className={`mt-1 text-xs leading-5 ${primary ? 'text-white/70' : 'text-ink/55'}`}>{detail}</p>
    </Link>
  )
}

function StaffAdminDashboard() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [weekly, setWeekly] = useState(null)

  useEffect(() => {
    dashboardApi.summary().then((res) => setSummary(res.data)).catch(() => {})
    dashboardApi.weekly().then((res) => setWeekly(res.data)).catch(() => {})
  }, [])

  if (!summary) return <DashboardLoading label={t('common.loading')} />

  const pieData = Object.entries(summary.applications_by_status).map(([status, count]) => ({ name: status.replace('_', ' '), value: count, status }))
  const pending = summary.applications_by_status.pending || 0
  const underReview = summary.applications_by_status.under_review || 0
  const approved = summary.applications_by_status.approved || 0

  return (
    <div className="dashboard-studio space-y-5 pb-8">
      <header className="dashboard-topline flex flex-wrap items-end justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-marigold-600">JanSeva operating system</p><h1 className="mt-2 font-display text-3xl text-ink sm:text-4xl">Service command centre.</h1></div><p className="dashboard-live-pill"><span /> Live office view</p></header>
      <section className="dashboard-studio-hero relative overflow-hidden rounded-[2rem] p-6 text-white sm:p-8">
        <div className="dashboard-studio-grid" aria-hidden="true" />
        <div className="relative z-10 grid gap-8 lg:grid-cols-[1.15fr_.85fr] lg:items-end"><div><span className="dashboard-kicker"><Command size={13} /> {t('dashboard.officeOverview')}</span><h2 className="mt-5 max-w-xl font-display text-4xl leading-[.95] sm:text-5xl">Good to see you,<br />{user?.full_name?.split(' ')[0] || 'Officer'}.</h2><p className="mt-5 max-w-lg text-sm leading-6 text-white/70">Your service desk has a clear view of today’s citizen requests, approvals, and office activity.</p><Link to="/applications" className="dashboard-red-link mt-7 inline-flex items-center gap-2">Open review queue <ArrowUpRight size={16} /></Link></div><div className="dashboard-radar-card"><div className="dashboard-radar" aria-hidden="true"><span /><span /><i /></div><div className="relative z-10 flex h-full flex-col justify-between"><div className="flex items-center justify-between"><span className="text-[10px] font-bold uppercase tracking-[.16em] text-white/55">Priority queue</span><CircleDot size={18} className="text-red-400" /></div><div><p className="font-display text-6xl leading-none">{pending}</p><p className="mt-2 text-sm text-white/70">applications awaiting review</p></div><div className="flex items-center justify-between border-t border-white/12 pt-4 text-xs"><span className="text-white/55">Active schemes</span><strong>{summary.active_schemes}</strong></div></div></div></div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label={t('dashboard.totalMembers')} value={summary.total_members} sub={`+${summary.new_members_last_30_days} in the last 30 days`} icon={Users} /><MetricCard label={t('dashboard.certificatesIssued')} value={summary.total_certificates_issued} sub={`+${summary.certificates_issued_last_30_days} in the last 30 days`} icon={Award} tone="marigold" /><MetricCard label={t('dashboard.activeSchemes')} value={summary.active_schemes} sub="Services open to citizens" icon={FileText} /><MetricCard label={t('dashboard.pendingApplications')} value={pending} sub="Needs a timely review" icon={ClipboardList} tone="brick" /></section>

      <section className="dashboard-insights-grid grid gap-5 xl:grid-cols-5">
        <div className="min-h-[330px] rounded-3xl border border-ink/7 bg-white p-5 shadow-sm xl:col-span-2"><div className="flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-marigold-600">Application pulse</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Current status mix</h2></div><span className="grid h-9 w-9 place-items-center rounded-xl bg-panchayat-50 text-panchayat-600"><BarChart3 size={17} /></span></div>{pieData.length > 0 ? <div className="mt-2 h-[240px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pieData} dataKey="value" nameKey="name" innerRadius={53} outerRadius={82} paddingAngle={3}>{pieData.map((entry) => <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || '#999'} />)}</Pie><Tooltip /><Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} /></PieChart></ResponsiveContainer></div> : <EmptyState icon={ClipboardList} text="Application activity will appear here." />}</div>
        <div className="rounded-3xl border border-ink/7 bg-white p-5 shadow-sm xl:col-span-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-marigold-600">Weekly activity</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Progress at a glance</h2><p className="mt-1 text-xs text-ink/50">Rolling 7-day view of office throughput.</p></div><span className="grid h-9 w-9 place-items-center rounded-xl bg-marigold-100 text-marigold-600"><TrendingUp size={17} /></span></div>{weekly ? <div className="mt-7 grid gap-3 sm:grid-cols-2"><WeeklyMetric label="Certificates issued" value={weekly.certificates_issued} icon={Award} tone="marigold" /><WeeklyMetric label="Applications submitted" value={weekly.applications_submitted} icon={ClipboardList} tone="panchayat" /><WeeklyMetric label="Applications cleared" value={weekly.applications_cleared} note={`${weekly.applications_approved} approved · ${weekly.applications_rejected} rejected`} icon={CheckCircle2} tone="panchayat" /><WeeklyMetric label="Still pending" value={weekly.applications_still_pending_total} icon={Clock3} tone="sand" /></div> : <EmptyState icon={TrendingUp} text="Weekly activity is loading." />}</div>
      </section>

      <section className="dashboard-workflow grid gap-4 rounded-[1.8rem] p-5 sm:p-6 lg:grid-cols-[.75fr_1.25fr]">
        <div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-marigold-600">Live workflow</p><h2 className="mt-2 font-display text-2xl text-ink">Move the next request.</h2><p className="mt-2 max-w-xs text-sm leading-6 text-ink/55">One clear view of every step in today’s service path.</p><Link to="/applications" className="dashboard-outline-link mt-5 inline-flex">View all applications <ArrowRight size={14} /></Link></div>
        <div className="grid gap-3 sm:grid-cols-3"><WorkflowRow label="Awaiting review" value={pending} detail="Needs a check" tone="red" /><WorkflowRow label="In review" value={underReview} detail="Office is verifying" tone="dark" /><WorkflowRow label="Approved" value={approved} detail="Ready for citizen" tone="light" /></div>
      </section>

      <DistrictActivitySection />

      <section><div className="mb-3 flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-marigold-600">Office shortcuts</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Keep services moving</h2></div><CalendarDays size={19} className="text-panchayat-300" /></div><div className="grid gap-3 md:grid-cols-3"><QuickAction to="/applications" label={t('dashboard.reviewApplications')} detail="Review pending requests and keep citizens informed." icon={ClipboardList} primary /><QuickAction to="/members" label={t('dashboard.registerMember')} detail="Add or update a household record for the office." icon={Users} /><QuickAction to="/certificates" label={t('dashboard.issueCertificate')} detail="Create or process a citizen certificate request." icon={Award} /></div></section>
    </div>
  )
}

function WeeklyMetric({ label, value, note, icon: Icon, tone }) {
  const styles = { panchayat: 'bg-panchayat-50 text-panchayat-700', marigold: 'bg-marigold-100 text-marigold-600', sand: 'bg-sand text-panchayat-700' }
  return <div className="rounded-2xl bg-[#fbfaf7] p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.1em] text-ink/45">{label}</p><p className="mt-2 font-display text-3xl text-panchayat-900">{value}</p>{note && <p className="mt-1 text-[11px] text-ink/50">{note}</p>}</div><span className={`grid h-9 w-9 place-items-center rounded-xl ${styles[tone]}`}><Icon size={16} /></span></div></div>
}

function WorkflowRow({ label, value, detail, tone }) {
  return <article className={`dashboard-workflow-row dashboard-workflow-${tone}`}><div className="flex items-start justify-between gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white/12 text-white"><ClipboardList size={16} /></span><strong className="font-display text-3xl leading-none">{value}</strong></div><p className="mt-6 text-sm font-bold">{label}</p><p className="mt-1 text-xs leading-5 text-white/62">{detail}</p></article>
}

function DistrictActivitySection() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isStateAdmin = isAdmin && (!user?.jurisdiction_level || user.jurisdiction_level === 'state' || user.jurisdiction_level === 'super')
  const isDistrictAdmin = isAdmin && !isStateAdmin
  const [reports, setReports] = useState([])
  const [form, setForm] = useState({ week_start: new Date().toISOString().slice(0, 10), summary: '', achievements: '', blockers: '' })
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const load = () => weeklyActivitiesApi.list().then((res) => setReports(res.data)).catch(() => setReports([]))
  useEffect(() => { if (isAdmin) load() }, [])
  if (!isAdmin) return null
  const submit = async (event) => { event.preventDefault(); setSaving(true); setMessage(''); try { await weeklyActivitiesApi.submit(form); setForm((current) => ({ ...current, summary: '', achievements: '', blockers: '' })); setMessage('Weekly activity submitted formally to the state dashboard.'); load() } catch (err) { setMessage(formatApiError(err, 'Could not submit the weekly activity.')) } finally { setSaving(false) } }
  if (isDistrictAdmin) return <section className="rounded-3xl border border-ink/7 bg-white p-6 shadow-sm"><div className="flex items-start gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-marigold-100 text-marigold-600"><CalendarDays size={18} /></span><div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-600">Formal reporting</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Submit district weekly activity</h2><p className="mt-1 text-sm text-ink/55">This report is submitted to the State Admin dashboard for {user?.district}.</p></div></div><form onSubmit={submit} className="mt-5 grid gap-3 sm:grid-cols-2"><Field label="Week starting" type="date" required value={form.week_start} onChange={(e) => setForm({ ...form, week_start: e.target.value })} /><div className="hidden sm:block" /><div className="sm:col-span-2"><label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[.1em] text-ink/55">Weekly summary</label><textarea required minLength="10" rows="3" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-panchayat-500" placeholder="Services delivered, applications handled, outreach…" /></div><div><label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[.1em] text-ink/55">Achievements</label><textarea rows="2" value={form.achievements} onChange={(e) => setForm({ ...form, achievements: e.target.value })} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-panchayat-500" /></div><div><label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[.1em] text-ink/55">Blockers / support needed</label><textarea rows="2" value={form.blockers} onChange={(e) => setForm({ ...form, blockers: e.target.value })} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-panchayat-500" /></div>{message && <p className={`text-sm sm:col-span-2 ${message.startsWith('Weekly') ? 'text-panchayat-700' : 'text-brick-600'}`}>{message}</p>}<div className="sm:col-span-2"><button disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-panchayat-700 px-4 py-2.5 text-sm font-semibold text-paper hover:bg-panchayat-600 disabled:opacity-50"><Send size={15} /> {saving ? 'Submitting…' : 'Submit formal report'}</button></div></form></section>
  return <section className="rounded-3xl border border-ink/7 bg-white p-6 shadow-sm"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-600">District formal reports</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Weekly activity from district admins</h2><p className="mt-1 text-sm text-ink/55">A normal State Admin dashboard view of every submitted report.</p></div><CalendarDays className="text-panchayat-300" size={20} /></div><div className="mt-5 grid gap-3 md:grid-cols-2">{reports.slice(0, 6).map((report) => <article key={report.id} className="rounded-2xl border border-ink/7 bg-[#fbfaf7] p-4"><div className="flex items-center justify-between gap-3"><strong className="text-sm text-panchayat-900">{report.district}</strong><span className="text-xs text-ink/45">Week of {new Date(report.week_start).toLocaleDateString('en-IN')}</span></div><p className="mt-3 text-sm leading-6 text-ink/65">{report.summary}</p><p className="mt-3 text-xs font-medium text-panchayat-700">Submitted by {report.submitted_by_name || 'District administrator'}</p></article>)}{!reports.length && <p className="rounded-2xl bg-panchayat-50 p-4 text-sm text-panchayat-700 md:col-span-2">No district weekly activity has been submitted yet.</p>}</div></section>
}

function CitizenDashboard() {
  const { t } = useTranslation()
  const { user, refreshUser } = useAuth()
  const [member, setMember] = useState(null)
  const [notFound, setNotFound] = useState(false)
  // Other pages hand off "open the profile form" through sessionStorage
  // (Schemes' locked Apply buttons, ProfileMenu's "Edit full household
  // profile"). The initialiser must stay PURE: React 18 StrictMode invokes it
  // twice in development, so clearing the flag here meant the first call
  // consumed it and the second - the one React keeps - saw nothing, and the
  // modal silently never opened. Read here, clear in an effect.
  const [showModal, setShowModal] = useState(
    () => sessionStorage.getItem('pp_edit_profile') === 'true'
  )
  useEffect(() => {
    sessionStorage.removeItem('pp_edit_profile')
  }, [])
  const firstName = user?.full_name?.split(' ')[0] || 'Citizen'
  const initials = (user?.full_name || 'Citizen').split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()

  const load = () => {
    membersApi.getMe().then((res) => { setMember(res.data); setNotFound(false) }).catch(() => setNotFound(true))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="dashboard-studio dashboard-citizen space-y-5 pb-8">
      <header className="dashboard-topline flex flex-wrap items-end justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-marigold-600">Your JanSeva space</p><h1 className="mt-2 font-display text-3xl text-ink sm:text-4xl">Everything, clearly in one place.</h1></div><p className="dashboard-live-pill"><span /> Your services are live</p></header>
      <section className="dashboard-citizen-hero relative overflow-hidden rounded-[2rem] p-6 text-white sm:p-8"><div className="dashboard-studio-grid" aria-hidden="true" /><div className="relative z-10 grid gap-7 lg:grid-cols-[1.15fr_.85fr] lg:items-center"><div><span className="dashboard-kicker"><Sparkles size={13} /> {t('dashboard.welcome')}</span><h2 className="mt-5 font-display text-4xl leading-[.95] sm:text-5xl">Hello, {firstName}.</h2><p className="mt-5 max-w-lg text-sm leading-6 text-white/70">Apply, follow each review, and keep your official records close—without repeated visits to the office.</p><Link to="/schemes" className="dashboard-red-link mt-7 inline-flex items-center gap-2">Explore welfare schemes <ArrowUpRight size={16} /></Link></div><div className="dashboard-profile-orb"><div className="dashboard-profile-rings" aria-hidden="true"><i /><i /><i /></div><div className="relative z-10 text-center"><span className="mx-auto grid h-16 w-16 place-items-center rounded-[1.4rem] bg-white font-display text-xl text-ink shadow-xl">{initials}</span><p className="mt-4 text-sm font-bold">Citizen portal</p><p className="mt-1 text-xs text-white/60">Your secure service space</p></div></div></div></section>

      {notFound && <section className="relative overflow-hidden rounded-3xl border border-marigold-500/20 bg-marigold-100 p-6"><div className="absolute -right-5 -top-6 h-28 w-28 rounded-full bg-marigold-300/35" aria-hidden="true" /><div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-marigold-500 text-paper"><CircleAlert size={19} /></span><div><h2 className="font-display text-xl text-panchayat-900">One quick step before you begin</h2><p className="mt-1 max-w-xl text-sm leading-6 text-panchayat-700/75">{t('dashboard.profileNotLinked')}</p></div></div><button onClick={() => setShowModal(true)} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-panchayat-700 px-5 py-3 text-sm font-semibold text-paper shadow-lg shadow-panchayat-900/15 transition hover:bg-panchayat-600">{t('dashboard.completeProfile')} <ChevronRight size={16} /></button></div></section>}

      {member && <section className="overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm"><div className="flex flex-col gap-4 border-b border-ink/7 bg-[#fbfaf7] px-6 py-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-panchayat-50 text-panchayat-600"><UserRound size={18} /></span><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-marigold-600">Your household</p><h2 className="mt-1 font-display text-xl text-panchayat-900">Profile at a glance</h2></div></div><div className="flex items-center gap-3"><span className="inline-flex items-center gap-1.5 text-xs font-semibold text-panchayat-600"><ShieldCheck size={14} /> Linked to your account</span><button onClick={() => setShowModal(true)} className="rounded-xl border border-panchayat-100 bg-white px-3 py-2 text-xs font-bold text-panchayat-700 hover:bg-panchayat-50">Update details</button></div></div><dl className="grid gap-px bg-ink/7 sm:grid-cols-2 lg:grid-cols-4"><InfoCell icon={UserRound} label={t('common.fullName')} value={member.full_name} /><InfoCell icon={MapPin} label={t('common.village')} value={`${member.village}${member.mandal ? ` · ${member.mandal}` : ''}`} /><InfoCell icon={Clock3} label={t('common.phone')} value={member.phone || 'Not added'} /><InfoCell icon={FileText} label="Annual income" value={member.annual_income ? `₹${member.annual_income.toLocaleString('en-IN')}` : 'Not added'} /></dl></section>}

      <section><div className="mb-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-marigold-600">Start a service</p><h2 className="mt-1 font-display text-xl text-panchayat-900">What would you like to do?</h2></div><div className="grid gap-3 md:grid-cols-3"><QuickAction to="/schemes" label={t('dashboard.browseSchemes')} detail="Explore support available for your household." icon={FileText} primary /><QuickAction to="/applications" label={t('dashboard.checkApplicationStatus')} detail="Track requests and see the latest updates." icon={ClipboardList} /><QuickAction to="/assistant" label={t('dashboard.askAiAssistant')} detail="Get help with eligibility and documents." icon={Sparkles} /></div></section>

      <section className="flex flex-col gap-4 rounded-3xl border border-panchayat-100 bg-panchayat-50 px-6 py-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-marigold-600 shadow-sm"><CheckCircle2 size={19} /></span><div><h2 className="font-display text-lg text-panchayat-900">Clear status, every step of the way</h2><p className="mt-1 text-sm text-panchayat-700/70">Your requests, documents, and official certificates remain easy to find.</p></div></div><Link to="/certificates" className="inline-flex shrink-0 items-center gap-2 text-sm font-bold text-panchayat-700 transition hover:text-panchayat-900">View certificates <ArrowRight size={16} /></Link></section>

      {showModal && <CompleteProfileModal member={member} onClose={() => setShowModal(false)} onSaved={() => { load(); refreshUser() }} />}
    </div>
  )
}

function InfoCell({ icon: Icon, label, value }) {
  return <div className="bg-white p-5"><span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-panchayat-50 text-panchayat-600"><Icon size={15} /></span><dt className="text-[10px] font-bold uppercase tracking-[0.1em] text-ink/45">{label}</dt><dd className="mt-1 text-sm font-semibold text-panchayat-900">{value}</dd></div>
}

function EmptyState({ icon: Icon, text }) {
  return <div className="grid h-[210px] place-items-center text-center"><div><span className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-panchayat-50 text-panchayat-500"><Icon size={18} /></span><p className="mt-3 text-sm text-ink/45">{text}</p></div></div>
}

function DashboardLoading({ label }) {
  return <div className="grid min-h-[440px] place-items-center"><div className="text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><Clock3 size={20} className="animate-pulse" /></span><p className="mt-3 text-sm text-ink/50">{label}</p></div></div>
}

export default function Dashboard() {
  const { user } = useAuth()
  if (user?.role === 'citizen') return <CitizenDashboard />
  return <StaffAdminDashboard />
}
