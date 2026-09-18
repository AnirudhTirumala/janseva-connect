/**
 * FastAPI returns error details in two shapes:
 *  - a plain string, e.g. { detail: "Incorrect email or password" }
 *  - an array of validation errors, e.g.
 *    { detail: [{ loc: [...], msg: "String should have at least 12 characters", type: "..." }] }
 *
 * Rendering the array shape directly in JSX crashes React ("Objects are not
 * valid as a React child"), which is why this always goes through here first.
 */
export function formatApiError(err, fallback = 'Something went wrong. Please try again.') {
  // No response at all means the request never reached the API - the backend
  // is down, the wrong VITE_API_URL was built in, or the network dropped.
  // Falling back to the caller's message here is actively misleading: the
  // login screen would say "Check your credentials" when the credentials were
  // never checked by anything, and registration would say "Registration
  // failed" for a server that was never contacted. Name the real cause.
  if (err && !err.response) {
    if (err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT') {
      return 'The server took too long to respond. Please check your connection and try again.'
    }
    return (
      'Cannot reach the JanSeva Connect server. It may be starting up or offline - ' +
      'please try again in a moment. (If you are running this locally, make sure the ' +
      'backend is started.)'
    )
  }

  const detail = err?.response?.data?.detail

  // 5xx bodies can be HTML from a proxy rather than the API's JSON, in which
  // case `detail` is missing and the generic fallback is genuinely wrong too.
  if (!detail) {
    const status = err?.response?.status
    if (status >= 500) {
      return 'The server hit an error handling that request. Please try again, or contact the office if it keeps happening.'
    }
    return fallback
  }

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : ''
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join(' | ')
  }

  return fallback
}
