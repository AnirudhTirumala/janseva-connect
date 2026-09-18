import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children, allowedRoles, requiresStateAdmin = false }) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  const isStateAdmin = user.role === 'admin' && (!user.jurisdiction_level || ['state', 'super'].includes(user.jurisdiction_level))
  if (requiresStateAdmin && !isStateAdmin) {
    return <Navigate to="/" replace />
  }
  return children
}
