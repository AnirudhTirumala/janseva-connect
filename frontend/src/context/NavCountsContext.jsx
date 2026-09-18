import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useAuth } from './AuthContext'
import { dashboardApi, messagesApi, notificationsApi } from '../api/endpoints'

const NavCountsContext = createContext(null)

/**
 * Single source of truth for every "how many things need my attention"
 * badge in the app - the sidebar nav counts (Applications, Certificates,
 * Issues, Chat) and the notification bell count. Previously these were two
 * separate components each running their own independent poll, so they
 * could drift out of sync with each other and both lagged behind real
 * changes by up to 20s. Now there's one poll (every 8s, plus immediately
 * on tab focus) and, more importantly, one refreshCounts() function that
 * any page can call right after its own mutating action (approving an
 * application, issuing or deleting a certificate, resolving an issue,
 * reading a message) so that action's badge updates immediately instead
 * of waiting for the next poll tick.
 */
export function NavCountsProvider({ children }) {
  const { user } = useAuth()
  const [navCounts, setNavCounts] = useState({ '/applications': 0, '/certificates': 0, '/issues': 0, '/chat': 0, '/assistant': 0 })
  const [chatBreakdown, setChatBreakdown] = useState({ citizen_unread: 0, team_unread: 0 })
  const [notificationCount, setNotificationCount] = useState(0)
  const requestId = useRef(0)

  const refreshCounts = () => {
    if (!user) return
    const thisRequest = ++requestId.current
    Promise.all([
      dashboardApi.navCounts().catch(() => ({ data: {} })),
      messagesApi.unreadCount().catch(() => ({ data: {} })),
      notificationsApi.unreadCount().catch(() => ({ data: {} })),
    ]).then(([countsRes, unreadRes, notifRes]) => {
      if (thisRequest !== requestId.current) return // a newer refresh already landed - discard this stale one
      const counts = countsRes.data || {}
      setNavCounts({
        '/applications': counts.applications || 0,
        '/certificates': counts.certificates || 0,
        '/issues': counts.issues || 0,
        '/chat': unreadRes.data?.unread_count || 0,
        '/assistant': counts.assistant || 0,
      })
      setChatBreakdown({
        citizen_unread: unreadRes.data?.citizen_unread ?? unreadRes.data?.unread_count ?? 0,
        team_unread: unreadRes.data?.team_unread ?? 0,
      })
      setNotificationCount(notifRes.data?.unread_count ?? 0)
    })
  }

  useEffect(() => {
    if (!user) return
    refreshCounts()
    const interval = setInterval(refreshCounts, 8000)
    const onVisible = () => { if (document.visibilityState === 'visible') refreshCounts() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', onVisible) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  return (
    <NavCountsContext.Provider value={{ navCounts, notificationCount, chatBreakdown, refreshCounts }}>
      {children}
    </NavCountsContext.Provider>
  )
}

export function useNavCounts() {
  const ctx = useContext(NavCountsContext)
  if (!ctx) return { navCounts: {}, notificationCount: 0, chatBreakdown: { citizen_unread: 0, team_unread: 0 }, refreshCounts: () => {} }
  return ctx
}
