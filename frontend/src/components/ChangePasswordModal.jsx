import { useEffect, useState } from 'react'
import { authApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, checkPassword } from '../utils/passwordPolicy'
import Modal from './Modal'
import { X } from 'lucide-react'

export default function ChangePasswordModal({ onClose }) {
  const [step, setStep] = useState('form') // 'form' | 'code'
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [code, setCode] = useState('')
  const [info, setInfo] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  const handleSendCode = async (e) => {
    e.preventDefault()
    setError('')
    // Checked before the code is emailed: otherwise the person waits for a
    // code, types it in, and only then learns the password was never valid.
    const policyError = checkPassword(newPassword)
    if (policyError) {
      setError(policyError)
      return
    }
    setLoading(true)
    try {
      const res = await authApi.requestChangePasswordOtp()
      setInfo(res.data.message)
      setStep('code')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not send a confirmation code.'))
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    setError('')
    try {
      const res = await authApi.requestChangePasswordOtp()
      setInfo(res.data.message || 'A new code has been sent.')
      setResendCooldown(30)
    } catch (err) {
      setError(formatApiError(err, 'Could not resend the code.'))
    }
  }

  const handleConfirm = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.confirmChangePassword(oldPassword, code, newPassword)
      onClose()
    } catch (err) {
      setError(formatApiError(err, 'Could not change your password.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal onClose={onClose} maxWidth="max-w-sm">
      <div className="bg-paper rounded-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg text-panchayat-700">Change password</h2>
          <button onClick={onClose}><X size={18} /></button>
        </div>

        {step === 'form' ? (
          <form onSubmit={handleSendCode} className="space-y-4">
            <div>
              <label className="block text-xs uppercase tracking-wide text-ink/60 mb-1.5">Current password</label>
              <input
                type="password"
                required
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full px-3 py-2 border border-ink/15 rounded-sm bg-white outline-none text-sm focus:border-panchayat-500"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wide text-ink/60 mb-1.5">New password</label>
              <input
                type="password"
                required
                minLength={MIN_PASSWORD_LENGTH}
                placeholder={PASSWORD_HINT}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-3 py-2 border border-ink/15 rounded-sm bg-white outline-none text-sm focus:border-panchayat-500"
              />
            </div>
            <p className="text-xs text-ink/50">
              For security, we'll also email a confirmation code to verify it's really you.
            </p>
            {error && <div className="bg-brick-100 text-brick-600 text-sm px-3 py-2 rounded-sm">{error}</div>}
            <div className="flex justify-end gap-3 pt-1">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-ink/60">Cancel</button>
              <button
                type="submit"
                disabled={loading || !oldPassword || newPassword.length < 6}
                className="px-5 py-2 bg-panchayat-600 text-paper text-sm rounded-sm hover:bg-panchayat-700 disabled:opacity-60"
              >
                {loading ? 'Sending code…' : 'Send confirmation code'}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleConfirm} className="space-y-4">
            {info && <div className="bg-panchayat-50 border border-panchayat-300 text-panchayat-700 text-sm px-3 py-2 rounded-sm">{info}</div>}
            <div>
              <label className="block text-xs uppercase tracking-wide text-ink/60 mb-1.5">6-digit code</label>
              <input
                required
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                className="w-full px-3 py-2 border border-ink/15 rounded-sm bg-white outline-none text-sm tracking-[0.3em] font-mono focus:border-panchayat-500"
                placeholder="000000"
              />
            </div>
            <button
              type="button"
              onClick={handleResendCode}
              disabled={resendCooldown > 0}
              className="text-xs font-semibold text-panchayat-600 hover:underline disabled:text-ink/35 disabled:no-underline"
            >
              {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
            </button>
            {error && <div className="bg-brick-100 text-brick-600 text-sm px-3 py-2 rounded-sm">{error}</div>}
            <div className="flex justify-end gap-3 pt-1">
              <button type="button" onClick={() => setStep('form')} className="px-4 py-2 text-sm text-ink/60">Back</button>
              <button
                type="submit"
                disabled={loading || code.length !== 6}
                className="px-5 py-2 bg-panchayat-600 text-paper text-sm rounded-sm hover:bg-panchayat-700 disabled:opacity-60"
              >
                {loading ? 'Changing…' : 'Change password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  )
}
