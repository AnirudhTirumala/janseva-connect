/**
 * Mirrors the server-side policy in backend/app/schemas/password.py.
 *
 * The server is the authority - this exists so someone typing a password
 * is told what is required *before* they submit, instead of filling in a
 * whole registration form and getting a 422 back about a rule nobody
 * mentioned. Keep the two in step: if the backend rule changes, change
 * this too, or the form will happily accept something the API rejects.
 */

export const MIN_PASSWORD_LENGTH = 10

export const PASSWORD_HINT =
  'At least 10 characters, mixing letters, numbers, and a symbol'

export const PASSWORD_RULE_TEXT =
  'Use at least 10 characters and combine at least three of: lowercase letters, uppercase letters, numbers, and symbols.'

const COMMON_PASSWORDS = new Set([
  'password', 'password1', 'password123', 'passw0rd', 'p@ssw0rd', 'p@ssword',
  '12345678', '123456789', '1234567890', 'qwertyuiop', 'qwerty123', '1q2w3e4r',
  'iloveyou', 'admin123', 'administrator', 'letmein123', 'welcome123',
  'abcd1234', 'abc123456', 'changeme', 'changeme123', 'secret123',
  'janseva123', 'panchayat', 'panchayat123', 'india@123', 'admin@123',
  'staff@123', 'citizen123', 'test1234', 'aadhaar123',
])

/** Returns an error message, or null when the password is acceptable. */
export function checkPassword(password) {
  const value = password || ''
  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters long.`
  }
  // bcrypt silently ignores everything past 72 bytes, so the server rejects
  // longer input rather than accepting a password it will not fully check.
  if (new TextEncoder().encode(value).length > 72) {
    return 'Password is too long - please use 72 characters or fewer.'
  }

  const classes = [
    /[a-z]/.test(value),
    /[A-Z]/.test(value),
    /[0-9]/.test(value),
    /[^a-zA-Z0-9]/.test(value),
  ].filter(Boolean).length
  if (classes < 3) {
    return 'Password must combine at least three of: lowercase letters, uppercase letters, numbers, and symbols.'
  }

  const simplified = value.trim().toLowerCase()
  if (COMMON_PASSWORDS.has(simplified)) {
    return 'That password is too common. Please choose something less guessable.'
  }
  if (new Set(simplified).size < 5) {
    return 'Password repeats too few distinct characters. Please choose something less guessable.'
  }
  return null
}
