import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '../api/endpoints'
import { useNavCounts } from '../context/NavCountsContext'
import { Bell } from 'lucide-react'
import { safeInternalPath } from '../utils/safeInternalPath'

export default function NotificationsBell({ variant = 'sidebar' }) {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const { notificationCount, refreshCounts } = useNavCounts()
  const ref = useRef(null)
  const navigate = useNavigate()
  const inTopbar = variant === 'topbar'

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleToggle = () => {
    if (!open) {
      notificationsApi.list().then((res) => setNotifications(res.data))
      refreshCounts() // catch anything that changed since the last poll tick
    }
    setOpen(!open)
  }

  const handleNotificationClick = async (n) => {
    if (!n.is_read) {
      await notificationsApi.markRead(n.id)
      refreshCounts()
      setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
    }
    // Only ever navigate to an in-app path. The value comes from the API, but
    // treating it as an opaque destination is how an open redirect gets in:
    // a single leading "//" or a "https:" prefix would send the citizen off
    // the portal from a link that looks like an official notification.
    const target = safeInternalPath(n.link)
    if (target) navigate(target)
    setOpen(false)
  }

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    refreshCounts()
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleToggle}
        aria-label={`Notifications${notificationCount ? ` (${notificationCount} unread)` : ''}`}
        className={inTopbar
          ? 'relative grid h-9 w-9 place-items-center rounded-xl border border-ink/8 bg-white text-panchayat-700 transition hover:-translate-y-0.5 hover:bg-panchayat-50'
          : 'relative flex w-full items-center gap-3 rounded-sm px-3 py-2 text-sm text-panchayat-50/85 transition-colors hover:bg-panchayat-600'}
      >
        <Bell size={17} />
        {!inTopbar && 'Notifications'}
        {notificationCount > 0 && (
          <span className={inTopbar
            ? 'absolute -right-2 -top-2 grid min-w-[18px] place-items-center rounded-full border-2 border-white bg-marigold-500 px-1 py-0.5 text-[10px] font-bold text-panchayat-900'
            : 'ml-auto min-w-[18px] rounded-full bg-marigold-500 px-1.5 py-0.5 text-center text-[10px] font-bold text-panchayat-900'}>
            {notificationCount > 99 ? '99+' : notificationCount}
          </span>
        )}
      </button>

      {open && (
        <div className={`absolute z-50 w-72 max-h-96 overflow-y-auto rounded-sm border border-ink/10 bg-paper pp-scrollbar shadow-xl animate-scale-in ${inTopbar ? 'right-0 top-full mt-2 origin-top-right' : 'bottom-full left-0 mb-2 origin-bottom-left'}`}>
          <div className="flex items-center justify-between px-4 py-3 pp-hairline border-b sticky top-0 bg-paper">
            <span className="font-display text-sm text-panchayat-700">Notifications</span>
            {notificationCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-xs text-panchayat-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          {notifications.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-ink/40">No notifications yet.</div>
          )}
          {notifications.map((n) => (
            <button
              key={n.id}
              onClick={() => handleNotificationClick(n)}
              className={`w-full text-left px-4 py-3 border-b border-ink/5 last:border-0 hover:bg-sand/40 ${!n.is_read ? 'bg-marigold-100/40' : ''}`}
            >
              <div className="flex items-start gap-2">
                {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-marigold-500 mt-1.5 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm text-ink font-medium">{n.title}</div>
                  {n.body && <div className="text-xs text-ink/60 mt-0.5 line-clamp-2">{n.body}</div>}
                  <div className="text-[11px] text-ink/40 mt-1">
                    {new Date(n.created_at).toLocaleDateString('en-IN')}{' '}
                    {new Date(n.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
