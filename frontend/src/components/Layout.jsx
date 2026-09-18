import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { useChat } from '../context/ChatContext'
import { useNavCounts } from '../context/NavCountsContext'
import { authApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import LanguageSwitcher from './LanguageSwitcher'
import NotificationsBell from './NotificationsBell'
import ChangePasswordModal from './ChangePasswordModal'
import ProfileMenu from './ProfileMenu'
import Modal from './Modal'
import {
  LayoutDashboard, Users, FileText, ClipboardList, Award,
  MessageCircleQuestion, MessageCircle, UserCog, User, X, Database, Landmark, MapPin, Menu, AlertTriangle,
} from 'lucide-react'

function useNavItems(t) {
  return {
    admin: [
      { to: '/', label: t('nav.dashboard'), icon: LayoutDashboard },
      { to: '/members', label: t('nav.members'), icon: Users },
      { to: '/schemes', label: t('nav.schemes'), icon: FileText },
      { to: '/applications', label: t('nav.applications'), icon: ClipboardList },
      { to: '/certificates', label: t('nav.certificates'), icon: Award },
      { to: '/issues', label: 'Local Issues', icon: AlertTriangle },
      { to: '/users', label: t('nav.staffUsers'), icon: UserCog },
      { to: '/database', label: 'Database', icon: Database },
      { to: '/chat', label: 'Chat', icon: MessageCircle },
      { to: '/assistant', label: t('nav.aiAssistant'), icon: MessageCircleQuestion },
    ],
    staff: [
      { to: '/', label: t('nav.dashboard'), icon: LayoutDashboard },
      { to: '/members', label: t('nav.members'), icon: Users },
      { to: '/schemes', label: t('nav.schemes'), icon: FileText },
      { to: '/applications', label: t('nav.applications'), icon: ClipboardList },
      { to: '/certificates', label: t('nav.certificates'), icon: Award },
      { to: '/issues', label: 'Local Issues', icon: AlertTriangle },
      { to: '/chat', label: 'Chat', icon: MessageCircle },
      { to: '/assistant', label: t('nav.aiAssistant'), icon: MessageCircleQuestion },
    ],
    citizen: [
      { to: '/', label: t('nav.myProfile'), icon: User },
      { to: '/schemes', label: t('nav.browseSchemes'), icon: FileText },
      { to: '/applications', label: t('nav.myApplications'), icon: ClipboardList },
      { to: '/certificates', label: t('nav.myCertificates'), icon: Award },
      { to: '/issues', label: 'Raise an Issue', icon: AlertTriangle },
      { to: '/chat', label: 'Chat with Office', icon: MessageCircle },
      { to: '/assistant', label: t('nav.askTheOffice'), icon: MessageCircleQuestion },
    ],
  }
}

// Location shown under the logo: citizens see their own village/town, mandal
// staff see their mandal, district staff/admin see their district, and the
// state administrator sees the state - each role gets exactly its own level,
// never a level it doesn't hold (a citizen never sees "District team", etc).
function scopeLabelFor(user) {
  if (!user) return ''
  if (user.role === 'citizen') {
    return user.village ? `${user.village} · Citizen services` : 'Citizen services'
  }
  if (user.role === 'admin' && user.jurisdiction_level === 'super') {
    return 'Andhra Pradesh · Superadmin'
  }
  if (user.role === 'admin' && (!user.jurisdiction_level || user.jurisdiction_level === 'state')) {
    return 'Andhra Pradesh · State administration'
  }
  if (user.jurisdiction_level === 'mandal') {
    return `${user.mandal || 'Assigned mandal'} · Mandal team`
  }
  if (user.district) {
    return `${user.district} · District team`
  }
  return 'Panchayat office'
}

function DeleteAccountModal({ onClose }) {
  const { t } = useTranslation()
  const { deleteAccount } = useAuth()
  const { clearChat } = useChat()
  const navigate = useNavigate()
  const [step, setStep] = useState('confirm') // 'confirm' | 'code'
  const [confirmText, setConfirmText] = useState('')
  const [code, setCode] = useState('')
  const [info, setInfo] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  const handleSendCode = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await authApi.requestAccountDeletion()
      setInfo(res.data.message)
      setStep('code')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not send a confirmation code.'))
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    setError('')
    try {
      const res = await authApi.requestAccountDeletion()
      setInfo(res.data.message || 'A new code has been sent.')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not resend the code.'))
    }
  }

  const handleConfirmDelete = async () => {
    setError('')
    setLoading(true)
    try {
      await deleteAccount(code)
      clearChat()
      navigate('/login')
    } catch (err) {
      setError(formatApiError(err, 'Could not delete your account.'))
      setLoading(false)
    }
  }

  return (
    <Modal onClose={onClose} maxWidth="max-w-sm">
      <div className="bg-paper rounded-sm p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-lg text-brick-600">Delete your account</h2>
          <button onClick={onClose}><X size={18} /></button>
        </div>

        {step === 'confirm' ? (
          <>
            <p className="text-sm text-ink/70 mb-4">
              This permanently deletes your login. Your household record and any certificates or scheme
              applications stay on file with the Panchayat office, but you will no longer be able to sign
              in or manage them online. This cannot be undone.
            </p>
            <label className="block text-xs uppercase tracking-wide text-ink/60 mb-1.5">
              Type <span className="font-mono font-semibold">DELETE</span> to confirm
            </label>
            <input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full px-3 py-2 border border-ink/15 rounded-sm bg-white outline-none text-sm mb-4 focus:border-brick-500"
            />
            {error && <div className="bg-brick-100 text-brick-600 text-sm px-3 py-2 rounded-sm mb-3">{error}</div>}
            <div className="flex justify-end gap-3">
              <button onClick={onClose} className="px-4 py-2 text-sm text-ink/60">{t('common.cancel')}</button>
              <button
                onClick={handleSendCode}
                disabled={confirmText !== 'DELETE' || loading}
                className="px-4 py-2 bg-brick-500 text-paper text-sm rounded-sm hover:bg-brick-600 disabled:opacity-50"
              >
                {loading ? 'Sending code…' : 'Send confirmation code'}
              </button>
            </div>
          </>
        ) : (
          <>
            {info && <div className="bg-panchayat-50 border border-panchayat-300 text-panchayat-700 text-sm px-3 py-2 rounded-sm mb-4">{info}</div>}
            <p className="text-sm text-ink/70 mb-3">
              Enter the code sent to your email to permanently delete your account.
            </p>
            <label className="block text-xs uppercase tracking-wide text-ink/60 mb-1.5">6-digit code</label>
            <input
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              className="w-full px-3 py-2 border border-ink/15 rounded-sm bg-white outline-none text-sm mb-4 tracking-[0.3em] font-mono focus:border-brick-500"
              placeholder="000000"
            />
            {error && <div className="bg-brick-100 text-brick-600 text-sm px-3 py-2 rounded-sm mb-3">{error}</div>}
            <button
              type="button"
              onClick={handleResendCode}
              disabled={resendCooldown > 0}
              className="text-xs font-semibold text-panchayat-600 hover:underline disabled:text-ink/35 disabled:no-underline mb-4"
            >
              {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
            </button>
            <div className="flex justify-end gap-3">
              <button onClick={onClose} className="px-4 py-2 text-sm text-ink/60">{t('common.cancel')}</button>
              <button
                onClick={handleConfirmDelete}
                disabled={code.length !== 6 || loading}
                className="px-4 py-2 bg-brick-500 text-paper text-sm rounded-sm hover:bg-brick-600 disabled:opacity-50"
              >
                {loading ? 'Deleting…' : 'Delete my account'}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}

export default function Layout({ children }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const { clearChat } = useChat()
  const { navCounts } = useNavCounts()
  const navigate = useNavigate()
  const items = useNavItems(t)[user?.role] || []
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showChangePassword, setShowChangePassword] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const handleLogout = () => {
    logout()
    clearChat()
    navigate('/login')
  }

  const roleLabel = { citizen: t('common.citizen'), staff: t('common.staff'), admin: t('common.admin') }[user?.role]
  const scopeLabel = scopeLabelFor(user)

  return (
    <div className="portal-shell relative flex h-screen overflow-hidden bg-paper">
      <div className="portal-orbit portal-orbit-one" aria-hidden="true" />
      <div className="portal-orbit portal-orbit-two" aria-hidden="true" />
      {mobileNavOpen && <button aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} className="fixed inset-0 z-40 animate-fade-in bg-panchayat-900/35 backdrop-blur-sm lg:hidden" />}
      <aside className={`portal-sidebar fixed inset-y-0 left-0 z-50 flex w-80 shrink-0 flex-col bg-panchayat-700 text-paper shadow-2xl shadow-panchayat-900/30 transition-transform duration-300 ease-out lg:static lg:w-80 lg:translate-x-0 lg:shadow-none ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="relative overflow-hidden border-b border-panchayat-500/40 px-5 py-6">
          <div className="absolute -right-8 -top-8 h-28 w-28 animate-glow-pulse rounded-full bg-marigold-300/10" aria-hidden="true" />
          <div className="relative flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-marigold-300 text-panchayat-900 shadow-lg shadow-panchayat-900/20"><Landmark size={21} /></span>
            <div className="min-w-0 leading-tight"><div className="font-display text-xl">JanSeva Connect</div><div className="mt-1 text-[9px] font-bold uppercase tracking-[.17em] text-panchayat-100/65">Andhra Pradesh panchayat services</div></div>
            <button onClick={() => setMobileNavOpen(false)} className="ml-auto grid h-8 w-8 place-items-center rounded-lg text-panchayat-100/70 hover:bg-white/10 lg:hidden"><X size={17} /></button>
          </div>
          <div className="relative mt-5 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-panchayat-100/80"><MapPin size={14} className="shrink-0 text-marigold-300" /><span className="truncate">{scopeLabel}</span></div>
        </div>

        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-5 pp-scrollbar">
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[.16em] text-panchayat-100/45">Workspace</p>
          {items.map(({ to, label, icon: Icon }, index) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileNavOpen(false)}
              style={{ animationDelay: `${index * 45}ms` }}
              className={({ isActive }) =>
                `group flex animate-nav-in items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-marigold-300 text-panchayat-900 font-bold shadow-lg shadow-panchayat-900/10'
                    : 'text-panchayat-50/85 hover:translate-x-0.5 hover:bg-white/8 hover:text-white'
                }`
              }
            >
              <Icon size={17} strokeWidth={2} className="transition-transform duration-200 group-hover:scale-110" />
              <span className="flex-1">{label}</span>
              {navCounts[to] > 0 && <span className="grid min-w-[20px] place-items-center rounded-full bg-brick-500 px-1.5 py-0.5 text-[10px] font-bold text-paper">{navCounts[to] > 99 ? '99+' : navCounts[to]}</span>}
            </NavLink>
          ))}
        </nav>

      </aside>

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="portal-topbar relative z-30 flex h-16 shrink-0 animate-fade-in-down items-center justify-between border-b border-ink/7 bg-white/95 px-4 shadow-sm shadow-panchayat-900/[0.03] sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3"><button onClick={() => setMobileNavOpen(true)} className="grid h-9 w-9 place-items-center rounded-xl border border-ink/8 text-panchayat-700 hover:bg-panchayat-50 lg:hidden"><Menu size={18} /></button><div className="hidden min-w-0 sm:block"><p className="text-[10px] font-bold uppercase tracking-[.16em] text-marigold-600">JanSeva Connect</p><p className="truncate text-sm font-semibold text-panchayat-900">{scopeLabel}</p></div></div>
          <div className="flex items-center gap-2 sm:gap-3">
          <NotificationsBell variant="topbar" />
          <LanguageSwitcher variant="onLight" />
          <ProfileMenu
            user={user}
            roleLabel={roleLabel}
            onChangePassword={() => setShowChangePassword(true)}
            onDeleteAccount={() => setShowDeleteModal(true)}
            onSignOut={handleLogout}
          />
          </div>
        </header>

        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="portal-page mx-auto h-full min-h-[600px] max-w-7xl px-4 py-5 sm:px-6 lg:px-8 lg:py-6">{children}</div>
        </main>
      </div>

      {showDeleteModal && <DeleteAccountModal onClose={() => setShowDeleteModal(false)} />}
      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  )
}
