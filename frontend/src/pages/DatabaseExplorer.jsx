import { useEffect, useState } from 'react'
import { usersApi, membersApi, schemesApi, applicationsApi, certificatesApi, auditApi } from '../api/endpoints'
import StatusBadge from '../components/StatusBadge'
import { Database as DatabaseIcon, Users, Contact, Landmark, ClipboardList, Award, KeyRound, History } from 'lucide-react'

const TABLES = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'members', label: 'Members', icon: Contact },
  { id: 'schemes', label: 'Schemes', icon: Landmark },
  { id: 'applications', label: 'Applications', icon: ClipboardList },
  { id: 'certificates', label: 'Certificates', icon: Award },
  { id: 'otps', label: 'OTP history', icon: KeyRound },
  { id: 'audit', label: 'Audit log', icon: History },
]

function Pill({ tone = 'neutral', children }) {
  const tones = {
    good: 'bg-panchayat-100 text-panchayat-700',
    warn: 'bg-marigold-100 text-marigold-600',
    bad: 'bg-brick-100 text-brick-600',
    neutral: 'bg-ink/6 text-ink/60',
  }
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>{children}</span>
}

function DataTable({ columns, rows, emptyText, icon: Icon }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink/7 bg-[#fbfaf7] text-left text-[11px] font-bold uppercase tracking-[.1em] text-ink/45">
              {columns.map((col) => (
                <th key={col} className="whitespace-nowrap px-5 py-3.5">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows}
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-5 py-16 text-center">
                  <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-500">
                    {Icon ? <Icon size={19} /> : <DatabaseIcon size={19} />}
                  </span>
                  <p className="mt-3 text-sm text-ink/40">{emptyText}</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function DatabaseExplorer() {
  const [tab, setTab] = useState('users')
  const [users, setUsers] = useState([])
  const [members, setMembers] = useState([])
  const [schemes, setSchemes] = useState([])
  const [applications, setApplications] = useState([])
  const [certificates, setCertificates] = useState([])
  const [otps, setOtps] = useState([])
  const [auditEvents, setAuditEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      usersApi.list(),
      membersApi.list({ limit: 500 }),
      schemesApi.list(false),
      applicationsApi.list(),
      certificatesApi.list(),
      auditApi.otps(),
      auditApi.events(),
    ]).then(([u, m, s, a, c, o, e]) => {
      setUsers(u.data)
      setMembers(m.data)
      setSchemes(s.data)
      setApplications(a.data)
      setCertificates(c.data)
      setOtps(o.data)
      setAuditEvents(e.data)
      setLoading(false)
    })
  }, [])

  const schemeName = (id) => schemes.find((s) => s.id === id)?.name || `#${id}`
  const memberName = (id) => members.find((m) => m.id === id)?.full_name || `#${id}`
  const counts = { users: users.length, members: members.length, schemes: schemes.length, applications: applications.length, certificates: certificates.length, otps: otps.length, audit: auditEvents.length }
  const activeTable = TABLES.find((t) => t.id === tab)

  return (
    <div className="space-y-6 pb-6">
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600"><DatabaseIcon size={20} /></span>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600">
            <DatabaseIcon size={13} /> Live data
          </div>
          <h1 className="font-display text-3xl text-panchayat-700">Database</h1>
        </div>
      </div>

      <p className="max-w-2xl text-sm text-ink/60">A protected, live view of the operational records. OTP codes and passwords are never displayed or stored in this explorer.</p>

      <div className="flex flex-wrap gap-2">
        {TABLES.map((t) => {
          const Icon = t.icon
          const active = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-bold transition ${
                active ? 'bg-panchayat-700 text-paper shadow-sm' : 'border border-ink/10 bg-white text-ink/60 hover:bg-panchayat-50'
              }`}
            >
              <Icon size={13} />
              {t.label}
              <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${active ? 'bg-white/15' : 'bg-ink/6'}`}>{counts[t.id]}</span>
            </button>
          )
        })}
      </div>

      {loading && <div className="text-sm text-ink/50">Loading…</div>}

      {!loading && tab === 'users' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Name', 'Email', 'Role', 'Status', 'Created']}
          emptyText="No users found."
          rows={users.map((u) => (
            <tr key={u.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{u.id}</td>
              <td className="px-5 py-3 font-medium text-ink">{u.full_name}</td>
              <td className="px-5 py-3 text-ink/70">{u.email}</td>
              <td className="px-5 py-3 capitalize text-ink/70">{u.role}</td>
              <td className="px-5 py-3"><Pill tone={u.is_active ? 'good' : 'bad'}>{u.is_active ? 'Active' : 'Deactivated'}</Pill></td>
              <td className="px-5 py-3 text-ink/70">{new Date(u.created_at).toLocaleDateString('en-IN')}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'members' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Name', 'Village', 'Phone', 'Annual Income', 'Portal Linked']}
          emptyText="No members found."
          rows={members.map((m) => (
            <tr key={m.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{m.id}</td>
              <td className="px-5 py-3 font-medium text-ink">{m.full_name}</td>
              <td className="px-5 py-3 text-ink/70">{m.village}</td>
              <td className="px-5 py-3 text-ink/70">{m.phone || '—'}</td>
              <td className="px-5 py-3 text-ink/70">{m.annual_income ? `₹${m.annual_income.toLocaleString('en-IN')}` : '—'}</td>
              <td className="px-5 py-3 text-ink/70">{m.user_id ? 'Yes' : 'No'}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'schemes' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Name', 'Active', 'Income Limit', 'Documents Required', 'Created']}
          emptyText="No schemes found."
          rows={schemes.map((s) => (
            <tr key={s.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{s.id}</td>
              <td className="px-5 py-3 font-medium text-ink">{s.name}</td>
              <td className="px-5 py-3"><Pill tone={s.is_active ? 'good' : 'bad'}>{s.is_active ? 'Active' : 'Inactive'}</Pill></td>
              <td className="px-5 py-3 text-ink/70">{s.max_income_limit ? `₹${s.max_income_limit.toLocaleString('en-IN')}` : '—'}</td>
              <td className="px-5 py-3 text-ink/70">{s.document_requirements?.length || 0}</td>
              <td className="px-5 py-3 text-ink/70">{new Date(s.created_at).toLocaleDateString('en-IN')}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'applications' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Scheme', 'Member', 'Status', 'Submitted']}
          emptyText="No applications found."
          rows={applications.map((a) => (
            <tr key={a.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{a.id}</td>
              <td className="px-5 py-3 font-medium text-ink">{schemeName(a.scheme_id)}</td>
              <td className="px-5 py-3 text-ink/70">{memberName(a.member_id)}</td>
              <td className="px-5 py-3"><StatusBadge status={a.status} /></td>
              <td className="px-5 py-3 text-ink/70">{new Date(a.submitted_at).toLocaleDateString('en-IN')}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'certificates' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Certificate No.', 'Citizen', 'Type', 'Issued']}
          emptyText="No certificates found."
          rows={certificates.map((c) => (
            <tr key={c.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{c.id}</td>
              <td className="px-5 py-3 font-mono text-xs text-panchayat-700">{c.certificate_number}</td>
              <td className="px-5 py-3 font-medium text-ink">{c.member_name || memberName(c.member_id)}</td>
              <td className="px-5 py-3 capitalize text-ink/70">{c.certificate_type}</td>
              <td className="px-5 py-3 text-ink/70">{new Date(c.issued_at).toLocaleDateString('en-IN')}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'otps' && (
        <DataTable
          icon={activeTable.icon}
          columns={['ID', 'Recipient', 'Purpose', 'Status', 'Expires', 'Sent']}
          emptyText="No OTPs have been sent."
          rows={otps.map((otp) => (
            <tr key={otp.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="px-5 py-3 text-ink/70">{otp.id}</td>
              <td className="px-5 py-3 text-ink/70">{otp.email}</td>
              <td className="px-5 py-3 capitalize text-ink/70">{otp.purpose.replaceAll('_', ' ')}</td>
              <td className="px-5 py-3"><Pill tone={otp.is_used ? 'good' : 'warn'}>{otp.is_used ? 'Used' : 'Pending'}</Pill></td>
              <td className="px-5 py-3 text-ink/70">{new Date(otp.expires_at).toLocaleString('en-IN')}</td>
              <td className="px-5 py-3 text-ink/70">{new Date(otp.created_at).toLocaleString('en-IN')}</td>
            </tr>
          ))}
        />
      )}

      {!loading && tab === 'audit' && (
        <DataTable
          icon={activeTable.icon}
          columns={['When', 'Actor', 'Role', 'Event', 'Action', 'Outcome']}
          emptyText="No audit activity has been recorded yet."
          rows={auditEvents.map((event) => (
            <tr key={event.id} className="border-b border-ink/5 last:border-0 hover:bg-panchayat-50/30">
              <td className="whitespace-nowrap px-5 py-3 text-ink/70">{new Date(event.created_at).toLocaleString('en-IN')}</td>
              <td className="px-5 py-3 text-ink/70">{event.actor_user_id ? `User #${event.actor_user_id}` : 'Visitor'}</td>
              <td className="px-5 py-3 capitalize text-ink/70">{event.actor_role || '—'}</td>
              <td className="px-5 py-3 text-ink/70">{event.event_type.replaceAll('_', ' ')}</td>
              <td className="px-5 py-3 font-medium text-ink">{event.action}</td>
              <td className="px-5 py-3"><Pill tone={event.outcome === 'failed' ? 'bad' : 'good'}>{event.outcome || 'recorded'}</Pill></td>
            </tr>
          ))}
        />
      )}
    </div>
  )
}
