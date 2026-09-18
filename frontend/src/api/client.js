import axios from 'axios'

// Set VITE_API_URL to the deployed backend's origin (it is baked in at build
// time, so changing it needs a rebuild, not just a restart).
//
// The localhost fallback is for local development only. Shipping a production
// bundle that still points at localhost is the single easiest deploy mistake
// to make on Vercel/Render - the site loads perfectly and then every request
// fails with an opaque connection error. Failing the build instead turns a
// confusing runtime mystery into an obvious, fixable build log.
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Deliberately a warning, not a throw: the build already refuses to produce a
// production bundle without VITE_API_URL (see vite.config.js). Throwing here
// too would only turn an escaped misconfiguration into a blank white page
// instead of an app that at least renders and reports failed requests.
if (import.meta.env.PROD && !import.meta.env.VITE_API_URL) {
  console.error(
    'VITE_API_URL was not set at build time - API requests are going to ' +
    'http://localhost:8000 and will fail. Rebuild with the backend origin set.'
  )
}

const api = axios.create({
  baseURL: API_BASE_URL,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('pp_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pp_token')
      localStorage.removeItem('pp_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
