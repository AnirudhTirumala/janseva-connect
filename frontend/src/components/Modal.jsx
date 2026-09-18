import { useEffect } from 'react'
import { createPortal } from 'react-dom'

/**
 * Shared modal shell used across the app's popover modals.
 *
 * Renders through a portal into document.body - this is deliberate, not
 * just tidiness: a `position: fixed` modal normally sizes itself against
 * the browser viewport, but if ANY ancestor element has a transform,
 * filter, backdrop-filter, perspective, or will-change set, that ancestor
 * silently becomes the modal's containing block instead, so the modal
 * sizes/centers itself against that ancestor's box instead of the screen
 * (this is exactly what broke the profile modals when the header had
 * backdrop-blur). Portaling to document.body makes the modal immune to
 * that regardless of what styling exists on its logical parent now or is
 * added later.
 */
export default function Modal({ onClose, children, maxWidth = 'max-w-md' }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex animate-fade-in items-center justify-center bg-panchayat-900/45 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className={`w-full ${maxWidth} animate-scale-in`}>{children}</div>
    </div>,
    document.body
  )
}
