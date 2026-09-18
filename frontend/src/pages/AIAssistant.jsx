import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { aiApi, issuesApi, notificationsApi } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import { useChat } from '../context/ChatContext'
import { useNavCounts } from '../context/NavCountsContext'
import { Bot, ChevronRight, ClipboardList, FileText, MonitorSmartphone, BarChart3, Send, Sparkles } from 'lucide-react'
import { toReadableText } from '../utils/plainText'

const ISSUE_STATUS_STYLES = {
  open: 'bg-sand text-ink/55',
  in_progress: 'bg-marigold-100 text-marigold-600',
  resolved: 'bg-panchayat-100 text-panchayat-700',
  closed: 'bg-panchayat-700 text-paper',
  reopened: 'bg-brick-100 text-brick-600',
}
const ISSUE_STATUS_LABEL = { open: 'Open', in_progress: 'In progress', resolved: 'Resolved', closed: 'Closed', reopened: 'Reopened' }
const CATEGORY_META = {
  portal: { label: 'Portal bug', icon: MonitorSmartphone },
  application: { label: 'Application issue', icon: ClipboardList },
}

// Gives the "AI Assistant" sidebar badge somewhere concrete to point to,
// instead of a number with nothing behind it: citizens see what they've
// reported through a conversation here; staff/admin see what the
// assistant has flagged for them (a subset of /issues - specifically the
// items that came from a chat instead of the manual "Raise a local issue"
// form) so the badge means "N unhandled things the assistant caught",
// not just a repeat of the Issues count.
function AIFlaggedPanel({ user }) {
  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const isCitizen = user.role === 'citizen'

  useEffect(() => {
    const load = () => issuesApi.list().then((res) => {
      const relevant = res.data.filter((i) => i.source === 'ai_assistant' && (isCitizen || i.status === 'open'))
      setIssues(relevant)
    }).finally(() => setLoading(false))
    load()
    const timer = setInterval(load, 8000)
    return () => clearInterval(timer)
  }, [isCitizen])

  if (loading || issues.length === 0) return null

  return (
    <div className="rounded-3xl border border-ink/7 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-marigold-100 text-marigold-600"><Bot size={18} /></span>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-600">{isCitizen ? 'Logged from your conversations' : 'Flagged by the assistant'}</p>
          <h3 className="font-display text-lg text-panchayat-900">
            {isCitizen ? 'Things you reported here' : `${issues.length} open item${issues.length === 1 ? '' : 's'} need attention`}
          </h3>
        </div>
      </div>
      <div className="space-y-2">
        {issues.slice(0, 5).map((issue) => {
          const meta = CATEGORY_META[issue.category]
          const Icon = meta?.icon
          return (
            <Link
              key={issue.id}
              to="/issues"
              className="flex items-center justify-between gap-3 rounded-2xl border border-ink/7 px-4 py-3 text-sm transition hover:border-panchayat-300 hover:bg-panchayat-50/40"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  {meta && <span className="inline-flex items-center gap-1 rounded-full bg-panchayat-50 px-2 py-0.5 text-[10px] font-bold text-panchayat-600">{Icon && <Icon size={10} />} {meta.label}</span>}
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${ISSUE_STATUS_STYLES[issue.status] || 'bg-sand text-ink/55'}`}>{ISSUE_STATUS_LABEL[issue.status] || issue.status}</span>
                </div>
                <p className="mt-1 truncate font-medium text-ink">{issue.title}</p>
              </div>
              <ChevronRight size={16} className="shrink-0 text-ink/30" />
            </Link>
          )
        })}
      </div>
      {issues.length > 5 && <p className="mt-2 text-xs text-ink/45">+{issues.length - 5} more on the Issues page.</p>}
    </div>
  )
}

function ChatPanel() {
  const { messages, setMessages } = useChat()
  const { refreshCounts } = useNavCounts()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input }
    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await aiApi.chat(userMsg.content, history)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }])
      // The server may have logged a real issue during this reply. Update
      // the assistant/sidebar badge immediately rather than waiting for the
      // shared poll interval.
      refreshCounts()
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="assistant-shell flex h-[540px] flex-col overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-xl shadow-panchayat-900/5">
      <div className="flex items-center gap-3 border-b border-ink/7 bg-panchayat-700 px-5 py-4 text-paper"><span className="assistant-orb grid h-9 w-9 place-items-center rounded-xl bg-marigold-300 text-panchayat-900"><Sparkles size={17} /></span><div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-300">JanSeva guide</p><p className="font-display text-lg">Ask about services, documents, and eligibility</p></div><span className="ml-auto rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold text-panchayat-100">AI assistant</span></div>
      <div ref={scrollRef} className="chat-surface flex-1 space-y-4 overflow-y-auto p-5 pp-scrollbar">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                m.role === 'user' ? 'rounded-br-md bg-panchayat-700 text-paper' : 'rounded-bl-md border border-ink/7 bg-white text-ink shadow-sm'
              }`}
            >
              {m.role === 'assistant' ? toReadableText(m.content) : m.content}
            </div>
          </div>
        ))}
        {loading && <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs text-panchayat-700 shadow-sm"><span className="assistant-typing"><i /><i /><i /></span> JanSeva guide is thinking…</div>}
      </div>
      <div className="flex gap-2 border-t border-ink/7 bg-white p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask about schemes, eligibility, documents…"
          className="flex-1 rounded-xl border border-ink/10 bg-[#fbfaf7] px-3.5 py-2.5 text-sm outline-none focus:border-panchayat-500"
        />
        <button onClick={send} disabled={loading || !input.trim()} className="rounded-xl bg-marigold-500 px-4 text-panchayat-900 transition hover:bg-marigold-600 disabled:opacity-50">
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}

function LetterDrafter() {
  const { user } = useAuth()
  const [form, setForm] = useState({ purpose: '', recipient: 'The Panchayat Secretary', member_name: user?.full_name || '', extra_context: '' })
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const draft = async () => {
    setLoading(true)
    try {
      const res = await aiApi.draftLetter(form)
      setResult(res.data.reply)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3 rounded-3xl border border-ink/7 bg-white p-6 shadow-sm">
      <h3 className="flex items-center gap-2 font-display text-lg text-panchayat-700"><FileText size={18} /> Draft an official letter</h3>
      <input placeholder="Purpose (e.g. request for road repair)" value={form.purpose} onChange={update('purpose')} className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      <input placeholder="Recipient" value={form.recipient} onChange={update('recipient')} className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      <input placeholder="Your name" value={form.member_name} onChange={update('member_name')} className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      <textarea placeholder="Additional context (optional)" rows={2} value={form.extra_context} onChange={update('extra_context')} className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      <button onClick={draft} disabled={loading || !form.purpose} className="rounded-xl bg-panchayat-600 px-4 py-2 text-sm font-bold text-paper shadow-sm hover:bg-panchayat-700 disabled:opacity-50">
        {loading ? 'Drafting…' : 'Draft letter'}
      </button>
      {result && <pre className="whitespace-pre-wrap rounded-2xl bg-sand/40 p-4 font-sans text-sm text-ink/80">{result}</pre>}
    </div>
  )
}

function ReportSummarizer() {
  const [form, setForm] = useState({ month: '', new_members: '', certificates_issued: '', applications_received: '', applications_approved: '', applications_pending: '' })
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const generate = async () => {
    setLoading(true)
    try {
      const res = await aiApi.monthlyReport({
        ...form,
        new_members: parseInt(form.new_members || 0, 10),
        certificates_issued: parseInt(form.certificates_issued || 0, 10),
        applications_received: parseInt(form.applications_received || 0, 10),
        applications_approved: parseInt(form.applications_approved || 0, 10),
        applications_pending: parseInt(form.applications_pending || 0, 10),
      })
      setResult(res.data.reply)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3 rounded-3xl border border-ink/7 bg-white p-6 shadow-sm">
      <h3 className="flex items-center gap-2 font-display text-lg text-panchayat-700"><BarChart3 size={18} /> Monthly report summary</h3>
      <div className="grid grid-cols-2 gap-3">
        <input placeholder="Month (e.g. July 2026)" value={form.month} onChange={update('month')} className="col-span-2 rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
        <input type="number" placeholder="New members" value={form.new_members} onChange={update('new_members')} className="rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
        <input type="number" placeholder="Certificates issued" value={form.certificates_issued} onChange={update('certificates_issued')} className="rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
        <input type="number" placeholder="Applications received" value={form.applications_received} onChange={update('applications_received')} className="rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
        <input type="number" placeholder="Applications approved" value={form.applications_approved} onChange={update('applications_approved')} className="rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
        <input type="number" placeholder="Applications pending" value={form.applications_pending} onChange={update('applications_pending')} className="rounded-xl border border-ink/15 px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
      </div>
      <button onClick={generate} disabled={loading || !form.month} className="rounded-xl bg-panchayat-600 px-4 py-2 text-sm font-bold text-paper shadow-sm hover:bg-panchayat-700 disabled:opacity-50">
        {loading ? 'Generating…' : 'Generate summary'}
      </button>
      {result && <pre className="whitespace-pre-wrap rounded-2xl bg-sand/40 p-4 font-sans text-sm text-ink/80">{result}</pre>}
    </div>
  )
}

export default function AIAssistant() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { navCounts, refreshCounts } = useNavCounts()
  const [tab, setTab] = useState('chat')
  const flaggedCount = navCounts['/assistant'] || 0

  // Opening this page is how the user sees the durable acknowledgement for
  // an assistant-created ticket. It follows the same visible-on-visit rule
  // as Applications and Certificates, keeping the assistant badge current.
  useEffect(() => {
    notificationsApi.markReadByLink('/assistant').then(refreshCounts).catch(() => {})
  }, [user?.id])

  const tabs = [
    { id: 'chat', label: t('ai.askQuestion'), roles: ['citizen', 'staff', 'admin'] },
    { id: 'report', label: t('ai.monthlyReport'), roles: ['staff', 'admin'] },
  ].filter((tab) => tab.roles.includes(user.role))

  return (
    <div className="space-y-6 pb-6">
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><Sparkles size={20} /></span>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600">
            <Sparkles size={13} /> AI Assistant
            {flaggedCount > 0 && <span className="ml-1 rounded-full bg-marigold-500 px-1.5 py-0.5 text-[10px] font-bold normal-case tracking-normal text-panchayat-900">{flaggedCount > 99 ? '99+' : flaggedCount} update{flaggedCount === 1 ? '' : 's'}</span>}
          </div>
          <h1 className="font-display text-3xl text-panchayat-700">
            {user.role === 'citizen' ? t('ai.titleCitizen') : t('ai.title')}
          </h1>
        </div>
      </div>

      <AIFlaggedPanel user={user} />

      <div className="flex flex-wrap gap-2">
        {tabs.map((tb) => (
          <button
            key={tb.id}
            onClick={() => setTab(tb.id)}
            className={`rounded-full px-3.5 py-2 text-xs font-bold transition ${
              tab === tb.id ? 'bg-panchayat-700 text-paper shadow-sm' : 'border border-ink/10 bg-white text-ink/60 hover:bg-panchayat-50'
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {tab === 'chat' && <ChatPanel />}
      {tab === 'report' && <ReportSummarizer />}
    </div>
  )
}
