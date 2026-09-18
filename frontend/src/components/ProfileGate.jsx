import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { membersApi } from '../api/endpoints'
import { AlertTriangle, ChevronRight, Lock } from 'lucide-react'

/**
 * Shared "you need a household profile first" gate.
 *
 * Applying for a scheme, requesting a certificate, and raising an issue all
 * require a Member record, and the API refuses each one with a 400 if it is
 * missing. Relying on that refusal alone put the explanation in a neutral
 * message banner *after* the citizen filled in a form and pressed submit -
 * where it reads like ordinary page copy and gets missed entirely.
 *
 * These three pieces state it before the interaction instead, in the error
 * palette, with the remedy one click away. Kept in one place so the three
 * pages cannot drift apart.
 */

/** Resolves whether the signed-in citizen has a household record yet. */
export function useProfileGate(role) {
  // null while unknown - callers must not render the warning during that
  // window or it flashes on screen for every citizen who does have a profile.
  const [hasProfile, setHasProfile] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    // Staff and admins are never gated; treat them as satisfied.
    if (role !== 'citizen') {
      setHasProfile(true)
      return undefined
    }
    let active = true
    // A 404 here is the normal "not registered yet" answer, not an error.
    membersApi.getMe()
      .then(() => { if (active) setHasProfile(true) })
      .catch(() => { if (active) setHasProfile(false) })
    return () => { active = false }
  }, [role])

  /** Drops the citizen straight into the profile form on the dashboard. */
  const goCompleteProfile = () => {
    sessionStorage.setItem('pp_edit_profile', 'true')
    navigate('/')
  }

  return { hasProfile, needsProfile: hasProfile === false, goCompleteProfile }
}

/** Full-width red alert explaining why nothing on this page can be used yet. */
export function ProfileRequiredBanner({ heading, body, onComplete }) {
  return (
    <section
      role="alert"
      className="relative overflow-hidden rounded-2xl border-2 border-brick-500/45 bg-brick-100 p-5 shadow-sm"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brick-500 text-paper">
            <AlertTriangle size={20} />
          </span>
          <div>
            <h2 className="font-display text-lg text-brick-600">{heading}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-brick-600/85">{body}</p>
          </div>
        </div>
        <button
          onClick={onComplete}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-brick-500 px-5 py-3 text-sm font-bold text-paper shadow-lg shadow-brick-500/25 transition hover:-translate-y-0.5 hover:bg-brick-600"
        >
          Complete my profile <ChevronRight size={16} />
        </button>
      </div>
    </section>
  )
}

/** Replaces the real action button, so the click leads somewhere useful. */
export function ProfileLockedButton({ label, onComplete, className = '' }) {
  return (
    <button
      type="button"
      onClick={onComplete}
      title="Add your household details first - one form, then every service opens up."
      className={`flex items-center gap-2 rounded-xl border-2 border-brick-500/40 bg-brick-100 px-4 py-2 text-xs font-bold text-brick-600 transition hover:-translate-y-0.5 hover:bg-brick-500 hover:text-paper ${className}`}
    >
      <Lock size={13} /> {label}
    </button>
  )
}
