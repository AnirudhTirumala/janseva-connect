import { useEffect, useState } from 'react'
import { issuesApi, notificationsApi } from '../api/endpoints'
import { useNavCounts } from '../context/NavCountsContext'
import { useAuth } from '../context/AuthContext'
import { formatApiError } from '../utils/formatApiError'
import { AlertTriangle, Bot, CheckCircle2, ClipboardList, Clock, MapPin, MessageSquarePlus, MonitorSmartphone, RotateCcw, Send, Sparkles, XCircle } from 'lucide-react'
import { ProfileLockedButton, ProfileRequiredBanner, useProfileGate } from '../components/ProfileGate'

const STATUS_STYLES = {
  open: 'bg-sand text-ink/55',
  in_progress: 'bg-marigold-100 text-marigold-600',
  resolved: 'bg-panchayat-100 text-panchayat-700',
  closed: 'bg-panchayat-700 text-paper',
  reopened: 'bg-brick-100 text-brick-600',
}
const STATUS_LABEL = { open: 'Open', in_progress: 'In progress', resolved: 'Resolved - awaiting your confirmation', closed: 'Closed', reopened: 'Reopened' }

// civic (default) issues are the plain "Raise a local issue" form below and
// need no extra label - the page is already about them. portal/application
// issues only ever come from the AI assistant recognising a problem it
// couldn't solve itself (see app/utils/issue_escalation.py), so both the
// category and that provenance are shown together.
const CATEGORY_META = {
  portal: { label: 'Portal bug', icon: MonitorSmartphone, className: 'bg-brick-100 text-brick-600' },
  application: { label: 'Application issue', icon: ClipboardList, className: 'bg-marigold-100 text-marigold-700' },
}

const ISSUE_BARS = [
  { id: 'local', category: 'civic', label: 'Local issues', title: 'Locality issues', description: 'Roads, water, sanitation, streetlights, and other locality concerns.', matches: (issue) => issue.category === 'civic' },
  { id: 'application', category: 'application', label: 'Application issues', title: 'Applications & service help', description: 'Scheme, certificate, document-upload, and service-delivery issues reported to the office or AI Assistant.', matches: (issue) => issue.category === 'application' },
  { id: 'portal', category: 'portal', label: 'Portal reports', title: 'Portal bugs', description: 'Technical JanSeva Connect problems escalated to state and super administrators.', matches: (issue) => issue.category === 'portal' },
]

function IssueCategoryTag({ category, source }) {
  const meta = CATEGORY_META[category]
  if (!meta) return null
  const Icon = meta.icon
  return (
    <span className="inline-flex items-center gap-2 text-[10px] font-bold">
      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${meta.className}`}><Icon size={10} /> {meta.label}</span>
      {source === 'ai_assistant' && <span className="inline-flex items-center gap-1 rounded-full bg-panchayat-50 px-2 py-0.5 text-panchayat-600"><Bot size={10} /> via AI Assistant</span>}
    </span>
  )
}

// Each desk gets its own wording. A single generic form on three tabs tells
// a citizen nothing about which one to use, and "Describe the issue and its
// exact location" is actively wrong for a portal bug.
const RAISE_COPY = {
  civic: {
    heading: 'Raise a local issue',
    blurb: 'Tell your office about a problem in your locality - roads, water, sanitation, streetlights, and similar. The office aims to reply within 7 days.',
    titlePlaceholder: 'Short title (e.g. Streetlight not working near bus stand)',
    bodyPlaceholder: 'Describe the issue and its exact location',
    button: 'Raise issue',
    sent: 'Issue raised. Your local office aims to reply within a week.',
  },
  application: {
    heading: 'Report a problem with a service',
    blurb: 'Something wrong with a scheme application, a certificate, or a service you were promised - stuck too long, a decision you dispute, wrong details on a record. This goes to the whole service team, not only your local office.',
    titlePlaceholder: 'Short title (e.g. Pension application stuck for six weeks)',
    bodyPlaceholder: 'Which application or certificate, what went wrong, and what you expected',
    button: 'Report problem',
    sent: 'Reported. The service team can see this and will update you here.',
  },
  portal: {
    heading: 'Report a problem with this website',
    blurb: 'A technical fault in the portal itself - a page that will not load, a button that does nothing, an upload that fails, an error message. This goes to the administrators who maintain the platform.',
    titlePlaceholder: 'Short title (e.g. Upload button does nothing on Chrome)',
    bodyPlaceholder: 'What you were doing, what you expected, and what happened instead',
    button: 'Report problem',
    sent: 'Reported. The platform administrators can see this and will update you here.',
  },
}

function RaiseIssueForm({ onRaised, needsProfile, goCompleteProfile, category = 'civic' }) {
  const copy = RAISE_COPY[category] || RAISE_COPY.civic
  const [title, setTitle] = useState(''); const [description, setDescription] = useState(''); const [submitting, setSubmitting] = useState(false); const [message, setMessage] = useState('')
  const submit = async (event) => {
    event.preventDefault(); setSubmitting(true); setMessage('')
    try {
      await issuesApi.raise({ title: title.trim(), description: description.trim(), category })
      setTitle(''); setDescription(''); setMessage(copy.sent)
      onRaised()
    } catch (error) {
      setMessage(formatApiError(error, 'Could not raise this issue.'))
    } finally {
      setSubmitting(false)
    }
  }
  return <form onSubmit={submit} className="rounded-3xl border border-ink/7 bg-white p-6 shadow-sm">
    <div className="flex gap-3">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-marigold-100 text-marigold-600"><MessageSquarePlus size={19} /></span>
      <div>
        <h2 className="font-display text-xl text-panchayat-900">{copy.heading}</h2>
        <p className="mt-1 text-sm text-ink/55">{copy.blurb}</p>
      </div>
    </div>
    <div className="mt-5 space-y-3">
      <input required minLength={4} maxLength={150} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={copy.titlePlaceholder} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" />
      <textarea required minLength={10} maxLength={2000} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder={copy.bodyPlaceholder} className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50" />
    </div>
    {needsProfile ? <div className="mt-4"><ProfileLockedButton label="Complete your profile to raise an issue" onComplete={goCompleteProfile} /></div> : <button disabled={submitting} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-panchayat-700 px-4 py-2.5 text-sm font-semibold text-paper hover:bg-panchayat-600 disabled:opacity-50"><Send size={15} /> {submitting ? 'Submitting…' : copy.button}</button>}
    {message && <p className={`mt-3 text-sm ${message.startsWith('Issue raised') ? 'text-panchayat-700' : 'text-brick-600'}`}>{message}</p>}
  </form>
}

function IssueCard({ issue, office, onReplied }) {
  const [status, setStatus] = useState(issue.status); const [reply, setReply] = useState(issue.reply || ''); const [working, setWorking] = useState(false); const [error, setError] = useState('')
  const [rejecting, setRejecting] = useState(false); const [feedback, setFeedback] = useState('')
  const submitReply = async () => {
    if (!reply.trim()) return
    setWorking(true); setError('')
    try {
      await issuesApi.reply(issue.id, { status, reply: reply.trim() })
      onReplied()
    } catch (err) {
      setError(formatApiError(err, 'Could not send this reply.'))
    } finally {
      setWorking(false)
    }
  }
  const respond = async (accepted) => {
    setWorking(true); setError('')
    try {
      await issuesApi.respond(issue.id, { accepted, feedback: accepted ? undefined : feedback.trim() || undefined })
      setRejecting(false)
      onReplied()
    } catch (err) {
      setError(formatApiError(err, 'Could not send your response.'))
    } finally {
      setWorking(false)
    }
  }
  const location = [issue.village, issue.mandal, issue.district].filter(Boolean).join(', ')
  return <article className="p-5 sm:px-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {issue.category !== 'civic' && <div className="mb-1.5"><IssueCategoryTag category={issue.category} source={issue.source} /></div>}
        <h3 className="font-semibold text-ink">{issue.title}</h3>
        {office && <p className="mt-1 text-sm text-ink/60">{issue.citizen_name}</p>}
        {location && <p className="mt-1 flex items-center gap-1 text-xs text-ink/45"><MapPin size={11} /> {location}</p>}
        <p className="mt-1 text-xs text-ink/45">Raised {new Date(issue.created_at).toLocaleDateString('en-IN')}</p>
        <p className="mt-3 text-sm leading-6 text-ink/70">{issue.description}</p>
        {issue.reply && <div className="mt-3 rounded-2xl bg-panchayat-50 p-3.5 text-sm leading-6 text-panchayat-700"><strong className="block text-[11px] font-bold uppercase tracking-wide text-panchayat-600">Office reply{issue.replied_by_name ? ` · ${issue.replied_by_name}` : ''}</strong>{issue.reply}</div>}
        {issue.citizen_feedback && <div className="mt-3 rounded-2xl bg-brick-100 p-3.5 text-sm leading-6 text-brick-600"><strong className="block text-[11px] font-bold uppercase tracking-wide text-brick-600">{issue.status === 'reopened' ? 'Citizen said this is not resolved' : 'Citizen feedback'}</strong>{issue.citizen_feedback}</div>}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${STATUS_STYLES[issue.status] || 'bg-sand text-ink/55'}`}>{STATUS_LABEL[issue.status] || issue.status}</span>
        {issue.is_overdue && <span className="inline-flex items-center gap-1 rounded-full bg-brick-100 px-2.5 py-1 text-[10px] font-bold text-brick-600"><Clock size={11} /> Past 7-day target</span>}
      </div>
    </div>
    {!office && issue.status === 'resolved' && <div className="mt-4 rounded-2xl border border-panchayat-100 bg-panchayat-50 p-4">
      <p className="text-sm font-semibold text-panchayat-800">Is your issue actually resolved?</p>
      <p className="mt-1 text-xs text-ink/55">Let the office know so they can close it, or reopen it if it isn't fixed yet.</p>
      {!rejecting ? <div className="mt-3 flex flex-wrap gap-2">
        <button disabled={working} onClick={() => respond(true)} className="inline-flex items-center gap-1.5 rounded-xl bg-panchayat-700 px-3.5 py-2 text-sm font-semibold text-paper disabled:opacity-50"><CheckCircle2 size={15} /> Yes, it's resolved</button>
        <button disabled={working} onClick={() => setRejecting(true)} className="inline-flex items-center gap-1.5 rounded-xl border border-brick-500/30 bg-white px-3.5 py-2 text-sm font-semibold text-brick-600 disabled:opacity-50"><XCircle size={15} /> No, reopen it</button>
      </div> : <div className="mt-3 space-y-2">
        <textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} maxLength={2000} rows={2} placeholder="What's still wrong? (optional, helps the office fix it properly)" className="w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-brick-500 focus:ring-4 focus:ring-brick-100" />
        <div className="flex gap-2">
          <button disabled={working} onClick={() => respond(false)} className="inline-flex items-center gap-1.5 rounded-xl bg-brick-500 px-3.5 py-2 text-sm font-semibold text-paper disabled:opacity-50"><RotateCcw size={14} /> {working ? 'Sending…' : 'Reopen issue'}</button>
          <button disabled={working} onClick={() => setRejecting(false)} className="px-3.5 py-2 text-sm font-semibold text-ink/50">Cancel</button>
        </div>
      </div>}
    </div>}
    {office && <div className="mt-4 flex flex-wrap items-center gap-2">
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-xl border border-ink/10 px-3 py-2 text-sm outline-none focus:border-panchayat-500">
        <option value="open">Open</option>
        <option value="in_progress">In progress</option>
        <option value="resolved">Resolved</option>
      </select>
      <input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write a reply for the citizen" maxLength={2000} className="min-w-56 flex-1 rounded-xl border border-ink/10 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      <button disabled={working || !reply.trim()} onClick={submitReply} className="rounded-xl bg-panchayat-700 px-3 py-2 text-sm font-semibold text-paper disabled:opacity-50">{working ? 'Sending…' : issue.reply ? 'Update reply' : 'Send reply'}</button>
    </div>}
    {error && <p className="mt-2 text-xs text-brick-600">{error}</p>}
  </article>
}

export default function Issues() {
  const { user } = useAuth()
  const { needsProfile, goCompleteProfile } = useProfileGate(user.role)
  const office = user.role !== 'citizen'
  const { refreshCounts } = useNavCounts()
  const [issues, setIssues] = useState([]); const [loading, setLoading] = useState(true); const [activeBar, setActiveBar] = useState('local')
  const load = () => issuesApi.list().then((res) => { setIssues(res.data); setLoading(false) }).catch(() => setLoading(false))
  const loadAndRefresh = () => { load(); refreshCounts() }
  useEffect(() => { load() }, [])
  // Visiting this page is itself how a citizen "sees" these updates.
  useEffect(() => { if (!office) notificationsApi.markReadByLink('/issues').then(refreshCounts) }, [])
  const activeMeta = ISSUE_BARS.find((item) => item.id === activeBar) || ISSUE_BARS[0]
  const visibleIssues = issues.filter(activeMeta.matches)
  const overdueCount = visibleIssues.filter((issue) => issue.is_overdue).length
  return <div className="space-y-6 pb-6">
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600"><Sparkles size={13} /> Issue desk</div>
      <h1 className="font-display text-3xl text-panchayat-700">{activeMeta.title}</h1>
      <p className="mt-1 text-sm text-ink/55">{activeMeta.description}</p>
    </div>
    <div className="flex flex-wrap gap-2 rounded-2xl border border-ink/7 bg-white p-2 shadow-sm">
      {ISSUE_BARS.map((bar) => { const count = issues.filter(bar.matches).length; return <button key={bar.id} onClick={() => setActiveBar(bar.id)} className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${activeBar === bar.id ? 'bg-panchayat-700 text-paper shadow-sm' : 'text-ink/60 hover:bg-panchayat-50'}`}>{bar.label}<span className={`rounded-full px-1.5 py-0.5 text-[10px] ${activeBar === bar.id ? 'bg-white/15' : 'bg-sand text-ink/50'}`}>{count}</span></button> })}
    </div>
    {!office && needsProfile && <ProfileRequiredBanner heading="You cannot raise an issue yet - your household profile is missing" body="An issue is routed to the office that covers your village and mandal, so the portal needs your household record to know where to send it. Add those details once and you can report anything in your locality." onComplete={goCompleteProfile} />}
    {!office && <RaiseIssueForm key={activeBar} category={activeMeta.category} onRaised={loadAndRefresh} needsProfile={needsProfile} goCompleteProfile={goCompleteProfile} />}
    <section className="overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/7 px-6 py-5">
        <h2 className="font-display text-xl text-panchayat-900">{office ? activeMeta.label : `Your ${activeMeta.label.toLowerCase()}`}</h2>
        {office && overdueCount > 0 && <span className="inline-flex items-center gap-1.5 rounded-full bg-brick-100 px-3 py-1.5 text-xs font-bold text-brick-600"><AlertTriangle size={13} /> {overdueCount} past the 7-day target</span>}
      </div>
      <div className="divide-y divide-ink/6">
        {loading && <p className="px-6 py-12 text-center text-sm text-ink/40">Loading…</p>}
        {!loading && visibleIssues.map((issue) => <IssueCard key={issue.id} issue={issue} office={office} onReplied={loadAndRefresh} />)}
        {!loading && !visibleIssues.length && <p className="px-6 py-12 text-center text-sm text-ink/40">{office ? `No ${activeMeta.label.toLowerCase()} in your view yet.` : `You have no ${activeMeta.label.toLowerCase()} yet.`}</p>}
      </div>
    </section>
  </div>
}
