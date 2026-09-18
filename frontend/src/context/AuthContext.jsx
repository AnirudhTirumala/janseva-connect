import { createContext, useContext, useState, useEffect } from 'react'
import { authApi } from '../api/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('pp_user')
    const token = localStorage.getItem('pp_token')
    if (stored && token) {
      setUser(JSON.parse(stored))
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const res = await authApi.login(email, password)
    const { access_token, role, full_name, user_id } = res.data
    localStorage.setItem('pp_token', access_token)
    const profile = await authApi.me().catch(() => ({ data: {} }))
    const userObj = { id: user_id, role, full_name, email, ...profile.data }
    localStorage.setItem('pp_user', JSON.stringify(userObj))
    setUser(userObj)
    return userObj
  }

  const loginWithResetToken = async (email, code, newPassword) => {
    const res = await authApi.confirmPasswordReset(email, code, newPassword)
    const { access_token, role, full_name, user_id } = res.data
    localStorage.setItem('pp_token', access_token)
    const profile = await authApi.me().catch(() => ({ data: {} }))
    const userObj = { id: user_id, role, full_name, email, ...profile.data }
    localStorage.setItem('pp_user', JSON.stringify(userObj))
    setUser(userObj)
    return userObj
  }

  const completeRegistration = async (email, code) => {
    const res = await authApi.registerVerify(email, code)
    const { access_token, role, full_name, user_id } = res.data
    localStorage.setItem('pp_token', access_token)
    const profile = await authApi.me().catch(() => ({ data: {} }))
    const userObj = { id: user_id, role, full_name, email, ...profile.data }
    localStorage.setItem('pp_user', JSON.stringify(userObj))
    setUser(userObj)
    return userObj
  }

  const deleteAccount = async (code) => {
    await authApi.confirmAccountDeletion(code)
    localStorage.removeItem('pp_token')
    localStorage.removeItem('pp_user')
    setUser(null)
  }

  const updateUser = async (data) => {
    const res = await authApi.updateMe(data)
    const nextUser = { ...user, ...res.data }
    localStorage.setItem('pp_user', JSON.stringify(nextUser))
    setUser(nextUser)
    return nextUser
  }

  // Re-syncs the cached user (village/district/mandal/etc.) from the server.
  // Needed after a citizen saves their household profile: that request goes
  // through membersApi, not authApi.updateMe, so the cached user object
  // otherwise stays stale (e.g. showing no village under the logo) until
  // the next login.
  const refreshUser = async () => {
    const profile = await authApi.me().catch(() => null)
    if (!profile) return user
    const nextUser = { ...user, ...profile.data }
    localStorage.setItem('pp_user', JSON.stringify(nextUser))
    setUser(nextUser)
    return nextUser
  }

  const logout = () => {
    localStorage.removeItem('pp_token')
    localStorage.removeItem('pp_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, loginWithResetToken, completeRegistration, deleteAccount, updateUser, refreshUser, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
