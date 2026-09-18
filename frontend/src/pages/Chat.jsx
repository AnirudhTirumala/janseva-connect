import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { messagesApi } from '../api/endpoints'
import { useNavCounts } from '../context/NavCountsContext'
import { useAuth } from '../context/AuthContext'
import { ANDHRA_LOCATIONS, DISTRICTS } from '../data/andhraLocations'
import { AlertCircle, CheckCheck, ChevronRight, MapPin, MessageCircle, Radio, Search, Send, Sparkles, UsersRound } from 'lucide-react'
import { formatApiError } from '../utils/formatApiError'

function Avatar({ name = '?' }) { return <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-marigold-100 text-[10px] font-bold text-marigold-600">{name.split(' ').map((item) => item[0]).slice(0, 2).join('')}</span> }

// Citizens can only ever reach mandal/district staff or district/state
// admin (enforced server-side by jurisdiction); this labels each contact
// with exactly which of those four categories they are, instead of a bare
// "staff"/"admin" role, so that scope is visible rather than implicit.
function contactLevelLabel(contact) {
  const role = contact.role === 'admin' ? 'admin' : 'staff'
  if (contact.jurisdiction_level === 'mandal') return `Mandal ${role}`
  if (contact.jurisdiction_level === 'district') return `District ${role}`
  return `State ${role}`
}

function Bubble({ message, mine, internal = false }) { return <div className={`mb-3 flex gap-2 ${mine ? 'justify-end' : 'justify-start'}`}>{!mine && internal && <Avatar name={message.sender_name} />}<div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-sm ${mine ? 'rounded-br-md bg-panchayat-700 text-paper' : 'rounded-bl-md border border-ink/6 bg-white text-ink'}`}>{!mine && (internal || message.sender_role !== 'citizen') && <p className="mb-1 text-[11px] font-bold text-marigold-600">{message.sender_name || 'Panchayat office'}</p>}<p className="whitespace-pre-wrap leading-5">{message.body}</p><p className={`mt-1.5 text-[10px] ${mine ? 'text-panchayat-100/70' : 'text-ink/40'}`}>{new Date(message.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}{mine && !internal && <CheckCheck size={12} className="ml-1 inline align-text-bottom text-marigold-300" />}</p></div></div> }

function Composer({ onSend, busy, placeholder = 'Type a message…' }) { const [value, setValue] = useState(''); const submit = () => { if (!value.trim() || busy) return; onSend(value.trim()); setValue('') }; return <div className="border-t border-ink/7 bg-white p-3"><div className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-[#fbfaf7] p-1.5 focus-within:border-panchayat-400"><input value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && submit()} placeholder={placeholder} className="min-w-0 flex-1 bg-transparent px-2.5 py-2 text-sm outline-none" /><button onClick={submit} disabled={busy || !value.trim()} aria-label="Send message" className="grid h-9 w-9 place-items-center rounded-xl bg-marigold-500 text-panchayat-900 transition hover:bg-marigold-600 disabled:opacity-45">{busy ? <CheckCheck size={16} /> : <Send size={16} />}</button></div></div> }

function CitizenThread({ citizenUserId, name, currentUserId }) { const { refreshCounts } = useNavCounts(); const [messages, setMessages] = useState([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const scroll = useRef(null); const load = () => messagesApi.thread(citizenUserId).then((res) => { setMessages(res.data); refreshCounts() }).catch((err) => setError(formatApiError(err, 'Unable to load messages.'))); useEffect(() => { load(); const timer = setInterval(load, 8000); return () => clearInterval(timer) }, [citizenUserId]); useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: 'smooth' }) }, [messages]); const send = async (body) => { const draft = { id: `draft-${Date.now()}`, sender_id: currentUserId, body, created_at: new Date().toISOString(), is_read: false }; setMessages((items) => [...items, draft]); setBusy(true); setError(''); try { const res = await messagesApi.send(body, citizenUserId); setMessages((items) => items.map((item) => item.id === draft.id ? res.data : item)); refreshCounts() } catch (err) { setMessages((items) => items.filter((item) => item.id !== draft.id)); setError(formatApiError(err, 'Message could not be sent.')) } finally { setBusy(false) } }; return <div className="flex h-full flex-col"><div className="flex items-center gap-3 border-b border-ink/7 bg-white px-5 py-4"><Avatar name={name} /><div><strong className="block text-sm text-panchayat-900">{name}</strong><span className="text-xs text-panchayat-700/55">Secure service conversation</span></div><span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-panchayat-50 px-2.5 py-1 text-[10px] font-bold text-panchayat-700"><Radio size={11} /> Live updates</span></div><div ref={scroll} className="chat-surface flex-1 overflow-y-auto p-5 pp-scrollbar">{messages.map((message) => <Bubble key={message.id} message={message} mine={message.sender_id === currentUserId} />)}{!messages.length && <div className="mt-12 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><MessageCircle size={21} /></span><p className="mt-3 text-sm text-ink/45">No messages yet. Start the conversation.</p></div>}</div>{error && <p className="flex items-center gap-1.5 px-4 py-2 text-xs text-brick-600"><AlertCircle size={13} />{error}</p>}<Composer onSend={send} busy={busy} /></div> }

function CitizenChat({ user }) { const [contacts, setContacts] = useState([]); useEffect(() => { messagesApi.officeContacts().then((res) => setContacts(res.data)).catch(() => setContacts([])) }, []); return <div className="grid h-full overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm md:grid-cols-[250px_1fr]"><aside className="hidden border-r border-ink/7 bg-[#fbfaf7] p-4 md:block"><p className="text-[10px] font-bold uppercase tracking-[.15em] text-marigold-600">Your local office</p><h2 className="mt-2 font-display text-xl text-panchayat-900">Here to help</h2><p className="mt-2 text-xs leading-5 text-ink/55">Your district and mandal office team can see and reply to this secure conversation.</p><div className="mt-5 space-y-3">{contacts.map((contact) => <div key={contact.id} className="flex items-center gap-2"><Avatar name={contact.full_name} /><div><p className="text-xs font-bold text-ink">{contact.full_name}</p><p className="text-[10px] text-ink/45">{contactLevelLabel(contact)}</p></div></div>)}</div></aside><CitizenThread citizenUserId={user.id} name="JanSeva Connect office" currentUserId={user.id} /></div> }

function CitizenInbox({ user }) { const [items, setItems] = useState([]); const [selected, setSelected] = useState(null); const [search, setSearch] = useState(''); const [loading, setLoading] = useState(true); const load = (term = search) => messagesApi.conversations(term || undefined).then((res) => { setItems(res.data); setLoading(false) }).catch(() => setLoading(false)); useEffect(() => { load(''); const timer = setInterval(() => load(), 10000); return () => clearInterval(timer) }, []); useEffect(() => { const timer = setTimeout(() => load(search), 300); return () => clearTimeout(timer) }, [search]); return <div className="grid h-full overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm md:grid-cols-[300px_1fr]"><aside className="flex min-h-0 flex-col border-r border-ink/7"><div className="border-b border-ink/7 p-4"><p className="text-[10px] font-bold uppercase tracking-[.15em] text-marigold-600">Citizen inbox</p><div className="relative mt-3"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/40" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search citizen…" className="w-full rounded-xl border border-ink/10 bg-[#fbfaf7] py-2.5 pl-8 pr-3 text-sm outline-none focus:border-panchayat-500" /></div></div><div className="flex-1 overflow-y-auto pp-scrollbar">{loading && <p className="p-5 text-center text-sm text-ink/40">Loading inbox…</p>}{items.map((item) => <button key={item.citizen_user_id} onClick={() => setSelected(item)} className={`w-full border-b border-ink/5 px-4 py-3.5 text-left transition hover:bg-panchayat-50/50 ${selected?.citizen_user_id === item.citizen_user_id ? 'bg-panchayat-50' : ''}`}><div className="flex items-center gap-2"><Avatar name={item.citizen_name} /><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><strong className="truncate text-sm text-ink">{item.citizen_name}</strong>{item.unread_count > 0 && <span className="rounded-full bg-marigold-500 px-1.5 py-0.5 text-[10px] font-bold text-panchayat-900">{item.unread_count}</span>}</div><p className="mt-0.5 truncate text-xs text-ink/45">{item.last_message || 'No messages yet'}</p></div></div></button>)}{!loading && !items.length && <p className="p-5 text-center text-sm text-ink/40">No citizens found.</p>}</div></aside><div className="min-h-0">{selected ? <CitizenThread citizenUserId={selected.citizen_user_id} name={selected.citizen_name} currentUserId={user.id} /> : <div className="grid h-full place-items-center bg-[#fbfaf7] p-6 text-center"><div><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><UsersRound size={23} /></span><p className="mt-3 font-display text-xl text-panchayat-900">Select a citizen</p><p className="mt-1 text-sm text-ink/50">Only citizens within your authorised jurisdiction appear here.</p></div></div>}</div></div> }

// State/super admins oversee every staff group; district admins also have a
// management forum. Staff get one clear staff-group channel plus their
// separate citizen inbox.
function channelScope(user) {
  const isStateAdmin = user.role === 'admin' && (!user.jurisdiction_level || ['state', 'super', ''].includes(user.jurisdiction_level))
  if (isStateAdmin) return 'state'
  if (user.role === 'admin' && user.district) return 'district'
  if (user.district) return 'staff'
  return 'none'
}

// Mirrors the backend's _channel_link (app/routers/messages.py) exactly -
// both sides build the same string so a channel's unread count (looked up
// by this key) and a click on its bell notification (which carries this
// same link) always agree on which channel they mean.
function channelLink(scope, district, mandal) {
  if (scope === 'district') return `/chat?scope=district&district=${encodeURIComponent(district)}`
  if (scope === 'mandal') return `/chat?scope=mandal&district=${encodeURIComponent(district)}&mandal=${encodeURIComponent(mandal)}`
  if (scope === 'leadership') return '/chat?scope=leadership'
  if (scope === 'district_admins') return '/chat?scope=district_admins'
  return '/chat?scope=all'
}

function ChannelBadge({ count }) { if (!count) return null; return <span className="rounded-full bg-marigold-500 px-1.5 py-0.5 text-[10px] font-bold text-panchayat-900">{count}</span> }

function TeamChannelThread({ channel, user }) {
  const { refreshCounts } = useNavCounts()
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scroll = useRef(null)

  const params = channel
    ? { scope: channel.scope, ...(channel.district ? { district: channel.district } : {}), ...(channel.mandal ? { mandal: channel.mandal } : {}) }
    : undefined

  const load = () => {
    if (!channel) return
    messagesApi.internal(params).then((res) => { setMessages(res.data); refreshCounts() }).catch((err) => setError(formatApiError(err, 'Unable to load this channel.')))
  }
  useEffect(() => { load(); const timer = setInterval(load, 8000); return () => clearInterval(timer) }, [channel?.scope, channel?.district, channel?.mandal])
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: 'smooth' }) }, [messages])

  const send = async (body) => {
    setBusy(true); setError('')
    try {
      const result = await messagesApi.sendInternal(body, params)
      setMessages((items) => [...items, result.data])
      refreshCounts()
    } catch (err) {
      setError(formatApiError(err, 'Could not send team message.'))
    } finally {
      setBusy(false)
    }
  }

  if (!channel) {
    return (
      <div className="grid h-full place-items-center bg-[#fbfaf7] p-6 text-center">
        <div>
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><UsersRound size={23} /></span>
          <p className="mt-3 font-display text-xl text-panchayat-900">Select a channel</p>
          <p className="mt-1 text-sm text-ink/50">Pick the all-staff channel, a district, or a mandal to see and send messages there.</p>
        </div>
      </div>
    )
  }

  const isLeadership = channel.scope === 'leadership'
  const isDistrictAdmins = channel.scope === 'district_admins'
  const title = isLeadership ? 'State leadership' : isDistrictAdmins ? 'District administrators' : channel.mandal || channel.district || 'All Staff & Admins'
  const kicker = isLeadership ? 'Superadmin & state admins' : isDistrictAdmins ? 'Management forum' : channel.scope === 'district' ? 'District staff group' : 'Mandal staff group'

  return (
    <section className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-3 border-b border-ink/7 bg-panchayat-700 px-5 py-4 text-paper">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10 text-marigold-300"><UsersRound size={19} /></span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-300">{kicker}</p>
          <h2 className="truncate font-display text-xl">{title}</h2>
        </div>
      </div>
      {(isLeadership || isDistrictAdmins) && <p className="border-b border-ink/7 bg-marigold-100/60 px-5 py-2 text-xs font-medium text-panchayat-700">{isLeadership ? 'Private channel for superadmin and state administrators.' : 'Shared by state/super administrators and district administrators.'}</p>}
      <div ref={scroll} className="chat-surface flex-1 overflow-y-auto p-5 pp-scrollbar">
        {messages.map((message) => <Bubble key={message.id} message={message} mine={message.sender_id === user.id} internal />)}
        {!messages.length && <div className="mt-12 text-center text-sm text-ink/45">No messages yet in this channel. Start the conversation.</div>}
      </div>
      {error && <p className="px-4 py-2 text-xs text-brick-600">{error}</p>}
      <Composer onSend={send} busy={busy} placeholder={`Message ${title}…`} />
    </section>
  )
}

// The multi-channel picker for state/super admins (scope='state': All
// Staff & Admins, plus every district as a collapsible group revealing its
// mandals) and district admins/staff (scope='district': just their own
// district's row, always expanded, since it's the only one they have).
function requestedChannelFor(user, scope, requested) {
  const fallback = scope === 'state'
    ? { scope: 'leadership' }
    : scope === 'district'
      ? { scope: 'district_admins' }
      : user.jurisdiction_level === 'mandal'
        ? { scope: 'mandal', district: user.district, mandal: user.mandal }
        : { scope: 'district', district: user.district }
  if (!requested) return fallback
  if (scope === 'state') return requested
  if (scope === 'district' && requested.scope === 'district_admins') return requested
  if (requested.scope === 'district' && requested.district === user.district) return requested
  if (requested.scope === 'mandal' && requested.district === user.district && requested.mandal && (scope === 'district' || requested.mandal === user.mandal)) return requested
  return fallback
}

function MultiChannelTeamChat({ user, scope, requestedChannel }) {
  const [selected, setSelected] = useState(() => requestedChannelFor(user, scope, requestedChannel))
  const [unreadByLink, setUnreadByLink] = useState({})
  const [expandedDistricts, setExpandedDistricts] = useState(() => new Set())
  const [query, setQuery] = useState('')

  const loadUnread = () => messagesApi.internalUnreadCounts().then((res) => setUnreadByLink(res.data)).catch(() => {})
  useEffect(() => { loadUnread(); const timer = setInterval(loadUnread, 8000); return () => clearInterval(timer) }, [])
  useEffect(() => { setSelected(requestedChannelFor(user, scope, requestedChannel)) }, [requestedChannel?.scope, requestedChannel?.district, requestedChannel?.mandal, scope, user.district])

  // Reading a channel marks it read server-side (see internal_thread in
  // messages.py) - re-check shortly after switching so that channel's own
  // badge clears without waiting for the next 8s poll. Also clear it
  // optimistically right away for an instant-feeling sidebar.
  const selectChannel = (next) => {
    setSelected(next)
    const link = channelLink(next.scope, next.district, next.mandal)
    setUnreadByLink((prev) => (prev[link] ? { ...prev, [link]: 0 } : prev))
    window.setTimeout(loadUnread, 500)
  }

  const toggleDistrict = (district) => setExpandedDistricts((prev) => {
    const next = new Set(prev)
    next.has(district) ? next.delete(district) : next.add(district)
    return next
  })

  const q = query.trim().toLowerCase()
  const districts = scope === 'state' ? DISTRICTS : [user.district]
  const managementMatches = !q || 'state leadership district administrators management forum'.includes(q)

  return (
    <div className="grid h-full overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm md:grid-cols-[300px_1fr]">
      <aside className="flex min-h-0 flex-col border-r border-ink/7">
        <div className="border-b border-ink/7 p-4">
          <p className="text-[10px] font-bold uppercase tracking-[.15em] text-marigold-600">Team chat</p>
          {scope === 'state' && (
            <div className="relative mt-3">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/40" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a district or mandal…" className="w-full rounded-xl border border-ink/10 bg-[#fbfaf7] py-2.5 pl-8 pr-3 text-sm outline-none focus:border-panchayat-500" />
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto pp-scrollbar">
          {scope === 'state' && managementMatches && <>
            <button onClick={() => selectChannel({ scope: 'leadership' })} className={`flex w-full items-center gap-2 border-b border-ink/5 px-4 py-3 text-left text-sm transition hover:bg-panchayat-50/50 ${selected.scope === 'leadership' ? 'bg-panchayat-50 font-semibold text-panchayat-700' : 'text-ink'}`}><Sparkles size={14} className="shrink-0 text-marigold-600" /><span className="flex-1 truncate">State leadership</span><ChannelBadge count={unreadByLink[channelLink('leadership')]} /></button>
            <button onClick={() => selectChannel({ scope: 'district_admins' })} className={`flex w-full items-center gap-2 border-b border-ink/5 px-4 py-3 text-left text-sm transition hover:bg-panchayat-50/50 ${selected.scope === 'district_admins' ? 'bg-panchayat-50 font-semibold text-panchayat-700' : 'text-ink'}`}><UsersRound size={14} className="shrink-0 text-marigold-600" /><span className="flex-1 truncate">District administrators</span><ChannelBadge count={unreadByLink[channelLink('district_admins')]} /></button>
          </>}
          {scope === 'district' && managementMatches && <button onClick={() => selectChannel({ scope: 'district_admins' })} className={`flex w-full items-center gap-2 border-b border-ink/5 px-4 py-3 text-left text-sm transition hover:bg-panchayat-50/50 ${selected.scope === 'district_admins' ? 'bg-panchayat-50 font-semibold text-panchayat-700' : 'text-ink'}`}><UsersRound size={14} className="shrink-0 text-marigold-600" /><span className="flex-1 truncate">District administrators</span><ChannelBadge count={unreadByLink[channelLink('district_admins')]} /></button>}
          {scope === 'staff' && <button onClick={() => selectChannel(user.jurisdiction_level === 'mandal' ? { scope: 'mandal', district: user.district, mandal: user.mandal } : { scope: 'district', district: user.district })} className={`flex w-full items-center gap-2 border-b border-ink/5 px-4 py-3 text-left text-sm transition hover:bg-panchayat-50/50 ${selected.scope !== 'district_admins' ? 'bg-panchayat-50 font-semibold text-panchayat-700' : 'text-ink'}`}><UsersRound size={14} className="shrink-0 text-marigold-600" /><span className="flex-1 truncate">My staff group{user.mandal ? ` · ${user.mandal}` : ` · ${user.district}`}</span><ChannelBadge count={unreadByLink[channelLink(selected.scope, selected.district, selected.mandal)]} /></button>}
          {scope !== 'staff' && districts.map((district) => {
            const mandals = ANDHRA_LOCATIONS[district] || []
            const districtMatches = !q || district.toLowerCase().includes(q)
            const matchingMandals = mandals.filter((m) => districtMatches || m.toLowerCase().includes(q))
            if (q && !districtMatches && matchingMandals.length === 0) return null
            const isExpanded = scope === 'district' || expandedDistricts.has(district) || (!!q && matchingMandals.length > 0)
            const districtSelected = selected.scope === 'district' && selected.district === district
            const districtUnread = unreadByLink[channelLink('district', district)] || 0
            return (
              <div key={district}>
                <div className={`flex items-center border-b border-ink/5 pr-3 transition hover:bg-panchayat-50/50 ${districtSelected ? 'bg-panchayat-50' : ''}`}>
                  {scope === 'state' && (
                    <button onClick={() => toggleDistrict(district)} className="py-2.5 pl-3 pr-1.5 text-ink/30 hover:text-ink/60" aria-label={isExpanded ? 'Collapse mandals' : 'Expand mandals'}>
                      <ChevronRight size={14} className={`transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                    </button>
                  )}
                  <button
                    onClick={() => selectChannel({ scope: 'district', district })}
                    className={`flex flex-1 items-center gap-2 py-2.5 text-left text-sm ${scope === 'district' ? 'pl-4' : ''} ${districtSelected ? 'font-semibold text-panchayat-700' : 'text-ink'}`}
                  >
                    <MapPin size={13} className="shrink-0 text-panchayat-500" />
                    <span className="flex-1 truncate">{district}{scope === 'district' ? ' (district-wide)' : ''}</span>
                    <ChannelBadge count={districtUnread} />
                  </button>
                </div>
                {isExpanded && matchingMandals.map((mandal) => {
                  const mandalSelected = selected.scope === 'mandal' && selected.district === district && selected.mandal === mandal
                  const unread = unreadByLink[channelLink('mandal', district, mandal)] || 0
                  return (
                    <button
                      key={mandal}
                      onClick={() => selectChannel({ scope: 'mandal', district, mandal })}
                      className={`flex w-full items-center gap-2 border-b border-ink/5 py-2.5 pl-10 pr-3 text-left text-sm transition hover:bg-panchayat-50/50 ${mandalSelected ? 'bg-panchayat-50 font-semibold text-panchayat-700' : 'text-ink/70'}`}
                    >
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-ink/20" />
                      <span className="flex-1 truncate">{mandal}</span>
                      <ChannelBadge count={unread} />
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>
      </aside>
      <div className="min-h-0"><TeamChannelThread channel={selected} user={user} /></div>
    </div>
  )
}

// The original single merged thread - unchanged - still used by
// mandal-level staff (only ever one place to post, so a picker adds
// nothing) and by any staff/admin record without a jurisdiction assigned yet.
function LegacyTeamChat({ user }) {
  const isStateAdmin = user.role === 'admin' && !user.district
  const { refreshCounts } = useNavCounts()
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scroll = useRef(null)
  const load = () => messagesApi.internal().then((res) => setMessages(res.data)).catch((err) => setError(formatApiError(err, 'Unable to load staff collaboration.')))
  useEffect(() => { load(); const timer = setInterval(load, 8000); return () => clearInterval(timer) }, [])
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: 'smooth' }) }, [messages])
  const send = async (body) => { setBusy(true); setError(''); try { const result = await messagesApi.sendInternal(body); setMessages((items) => [...items, result.data]); refreshCounts() } catch (err) { setError(formatApiError(err, 'Could not send team message.')) } finally { setBusy(false) } }
  return <section className="flex h-full flex-col overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm"><div className="flex items-center gap-3 border-b border-ink/7 bg-panchayat-700 px-5 py-4 text-paper"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 text-marigold-300"><UsersRound size={19} /></span><div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-marigold-300">Staff collaboration</p><h2 className="font-display text-xl">District &amp; mandal team chat</h2></div><span className="ml-auto rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold">{isStateAdmin ? 'Broadcasts to all districts' : 'Admin-visible'}</span></div>{isStateAdmin && <p className="border-b border-ink/7 bg-marigold-100/60 px-5 py-2 text-xs font-medium text-panchayat-700">As state administrator, messages you send here reach every district and mandal team.</p>}<div ref={scroll} className="chat-surface flex-1 overflow-y-auto p-5 pp-scrollbar">{messages.map((message) => <Bubble key={message.id} message={message} mine={message.sender_id === user.id} internal />)}{!messages.length && <div className="mt-12 text-center text-sm text-ink/45">No team messages yet. Start the district conversation.</div>}</div>{error && <p className="px-4 py-2 text-xs text-brick-600">{error}</p>}<Composer onSend={send} busy={busy} placeholder={isStateAdmin ? 'Message all districts (state-wide broadcast)…' : 'Message your district / mandal team…'} /></section>
}

function TeamChat({ user, requestedChannel }) {
  const scope = channelScope(user)
  if (scope === 'state' || scope === 'district' || scope === 'staff') return <MultiChannelTeamChat user={user} scope={scope} requestedChannel={requestedChannel} />
  return <LegacyTeamChat user={user} />
}

export default function Chat() {
  const { user } = useAuth()
  const { chatBreakdown } = useNavCounts()
  const [searchParams] = useSearchParams()
  const office = user.role !== 'citizen'
  const requestedScope = searchParams.get('scope')
  const requestedChannel = requestedScope === 'leadership'
    ? { scope: 'leadership' }
    : requestedScope === 'district_admins'
      ? { scope: 'district_admins' }
      : requestedScope === 'all'
    ? { scope: 'all' }
    : requestedScope === 'district' && searchParams.get('district')
      ? { scope: 'district', district: searchParams.get('district') }
      : requestedScope === 'mandal' && searchParams.get('district') && searchParams.get('mandal')
        ? { scope: 'mandal', district: searchParams.get('district'), mandal: searchParams.get('mandal') }
        : null
  const [tab, setTab] = useState(() => office && requestedChannel ? 'team' : 'citizens')
  useEffect(() => { if (office && requestedChannel) setTab('team') }, [office, requestedChannel?.scope, requestedChannel?.district, requestedChannel?.mandal])
  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600"><Sparkles size={13} /> Connected service</div>
          <h1 className="font-display text-3xl text-panchayat-700">{office ? 'Conversations' : 'Chat with your office'}</h1>
        </div>
        {office && (
          <div className="flex rounded-xl border border-ink/8 bg-white p-1 shadow-sm">
            <button onClick={() => setTab('citizens')} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold ${tab === 'citizens' ? 'bg-panchayat-700 text-paper' : 'text-ink/55'}`}>
              Citizen inbox
              {chatBreakdown.citizen_unread > 0 && <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${tab === 'citizens' ? 'bg-white/20' : 'bg-marigold-500 text-panchayat-900'}`}>{chatBreakdown.citizen_unread}</span>}
            </button>
            <button onClick={() => setTab('team')} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold ${tab === 'team' ? 'bg-panchayat-700 text-paper' : 'text-ink/55'}`}>
              Team chat
              {chatBreakdown.team_unread > 0 && <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${tab === 'team' ? 'bg-white/20' : 'bg-marigold-500 text-panchayat-900'}`}>{chatBreakdown.team_unread}</span>}
            </button>
          </div>
        )}
      </div>
      <div className="min-h-0 flex-1">{!office ? <CitizenChat user={user} /> : tab === 'citizens' ? <CitizenInbox user={user} /> : <TeamChat user={user} requestedChannel={requestedChannel} />}</div>
    </div>
  )
}
