import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ChatProvider } from './context/ChatContext'
import { NavCountsProvider } from './context/NavCountsContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'

import { auditApi } from './api/endpoints'

// Route-level loading keeps the first public page and every role-specific
// workspace fast on lower-bandwidth connections. A citizen does not need to
// download the administration, reporting, and AI screens before signing in.
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Members = lazy(() => import('./pages/Members'))
const Schemes = lazy(() => import('./pages/Schemes'))
const Applications = lazy(() => import('./pages/Applications'))
const Certificates = lazy(() => import('./pages/Certificates'))
const Issues = lazy(() => import('./pages/Issues'))
const Users = lazy(() => import('./pages/Users'))
const DatabaseExplorer = lazy(() => import('./pages/DatabaseExplorer'))
const Chat = lazy(() => import('./pages/Chat'))
const AIAssistant = lazy(() => import('./pages/AIAssistant'))
const Landing = lazy(() => import('./pages/Landing'))

function AuthedLayout({ children, allowedRoles, requiresStateAdmin }) {
  return (
    <ProtectedRoute allowedRoles={allowedRoles} requiresStateAdmin={requiresStateAdmin}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}

function HomeRoute() {
  const { user } = useAuth()
  return user ? <AuthedLayout><Dashboard /></AuthedLayout> : <Landing />
}

function ClickAudit() {
  const { user } = useAuth()
  useEffect(() => {
    if (!user) return undefined
    const track = (event) => {
      const element = event.target.closest('a, button, [role="button"]')
      if (!element || element.dataset.auditIgnore !== undefined) return
      const label = (element.dataset.auditLabel || element.getAttribute('aria-label') || element.textContent || element.tagName)
        .replace(/\s+/g, ' ').trim().slice(0, 120)
      if (!label) return
      auditApi.trackClick({ path: window.location.pathname, target: label, metadata: { element: element.tagName.toLowerCase() } }).catch(() => {})
    }
    document.addEventListener('click', track, true)
    return () => document.removeEventListener('click', track, true)
  }, [user])
  return null
}

function AppRoutes() {
  const { loading } = useAuth()
  if (loading) return null

  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-paper text-sm font-medium text-panchayat-700">Loading JanSeva Connect…</div>}>
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />

      <Route path="/" element={<HomeRoute />} />
      <Route
        path="/members"
        element={<AuthedLayout allowedRoles={['staff', 'admin']}><Members /></AuthedLayout>}
      />
      <Route path="/schemes" element={<AuthedLayout><Schemes /></AuthedLayout>} />
      <Route path="/applications" element={<AuthedLayout><Applications /></AuthedLayout>} />
      <Route path="/certificates" element={<AuthedLayout><Certificates /></AuthedLayout>} />
      <Route path="/issues" element={<AuthedLayout><Issues /></AuthedLayout>} />
      <Route
        path="/users"
        element={<AuthedLayout allowedRoles={['admin']}><Users /></AuthedLayout>}
      />
      <Route
        path="/database"
        element={<AuthedLayout allowedRoles={['admin']} requiresStateAdmin><DatabaseExplorer /></AuthedLayout>}
      />
      <Route path="/chat" element={<AuthedLayout><Chat /></AuthedLayout>} />
      <Route path="/assistant" element={<AuthedLayout><AIAssistant /></AuthedLayout>} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <AuthProvider>
          <NavCountsProvider>
            <ChatProvider>
              <ClickAudit />
              <AppRoutes />
            </ChatProvider>
          </NavCountsProvider>
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
