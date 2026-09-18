import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Fails a production build that was never told where the backend lives.
 *
 * VITE_API_URL is inlined at build time. Forgetting it on Vercel or Render
 * does not break the build or the page - the site loads perfectly and then
 * every request goes to http://localhost:8000 and dies with an opaque
 * network error, which looks like a backend outage rather than a missing
 * setting. Failing here puts the real reason in the deploy log instead.
 *
 * Set ALLOW_MISSING_API_URL=1 to build without it on purpose (e.g. checking
 * locally that the bundle still compiles).
 */
function requireApiUrl(env) {
  return {
    name: 'require-api-url',
    apply: 'build',
    buildStart() {
      if (env.VITE_API_URL || process.env.ALLOW_MISSING_API_URL === '1') return
      this.error(
        'VITE_API_URL is not set.\n\n' +
        'A production build needs the backend origin baked in, for example:\n' +
        '  VITE_API_URL=https://your-backend.onrender.com\n\n' +
        'On Vercel/Render, add it as an environment variable for the frontend\n' +
        'project and redeploy. To build without it on purpose, set\n' +
        'ALLOW_MISSING_API_URL=1.'
      )
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), requireApiUrl(env)],
    server: {
      port: 5173,
      host: true,
    },
  }
})
