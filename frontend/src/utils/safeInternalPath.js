const BACKSLASH = String.fromCharCode(92)

/**
 * Accepts only a path that stays inside this app.
 *
 * Notification links arrive from the API as plain strings and are handed
 * straight to react-router's navigate(). Anything that can be read as an
 * absolute or protocol-relative URL ("//evil.example", "https://…", and -
 * the case behind CVE-2025-68470 - backslash variants) would take the
 * citizen off the portal from a link that looks official.
 *
 * Returns the safe path, or null when the value is not an internal route.
 */
export function safeInternalPath(link) {
  if (typeof link !== 'string') return null
  const value = link.trim()
  if (!value.startsWith('/')) return null
  // A backslash anywhere is rejected: no legitimate route in this app
  // contains one, and browsers normalise it to "/" when resolving an
  // origin, which is exactly how "/\evil.example" becomes off-site.
  if (value.includes(BACKSLASH)) return null
  // "//host" is protocol-relative and also leaves the origin.
  if (value.startsWith('//')) return null
  return value
}
