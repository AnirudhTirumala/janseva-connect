import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { schemesApi, applicationsApi } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import { useNavCounts } from '../context/NavCountsContext'
import { formatApiError } from '../utils/formatApiError'
import DocumentUploadModal from '../components/DocumentUploadModal'
import { ProfileLockedButton, ProfileRequiredBanner, useProfileGate } from '../components/ProfileGate'
import { Plus, X, Send, CheckCircle2, FileUp, Pencil, Trash2, Landmark, Sparkles, IndianRupee, ListChecks } from 'lucide-react'

const EMPTY_SCHEME = { name: '', description: '', eligibility_criteria: '', max_income_limit: '' }

function SchemeFormModal({ existingScheme, onClose, onSaved }) {
  const isEdit = !!existingScheme
  const [form, setForm] = useState(
    existingScheme
      ? {
          name: existingScheme.name,
          description: existingScheme.description,
          eligibility_criteria: existingScheme.eligibility_criteria || '',
          max_income_limit: existingScheme.max_income_limit || '',
        }
      : EMPTY_SCHEME
  )
  const [docNames, setDocNames] = useState(existingScheme?.document_requirements?.map((d) => d.name) || [])
  const [docInput, setDocInput] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const addDoc = () => {
    const trimmed = docInput.trim()
    if (trimmed && !docNames.includes(trimmed)) {
      setDocNames([...docNames, trimmed])
    }
    setDocInput('')
  }

  const removeDoc = (name) => setDocNames(docNames.filter((d) => d !== name))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const payload = {
        ...form,
        eligibility_criteria: form.eligibility_criteria || null,
        max_income_limit: form.max_income_limit ? parseInt(form.max_income_limit, 10) : null,
        document_requirement_names: docNames,
      }
      if (isEdit) {
        await schemesApi.update(existingScheme.id, payload)
      } else {
        await schemesApi.create(payload)
      }
      await onSaved()
      onClose()
    } catch (err) {
      setError(formatApiError(err, isEdit ? 'Could not update scheme.' : 'Could not create scheme.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-paper shadow-xl pp-scrollbar">
        <div className="flex items-center justify-between border-b border-ink/7 px-6 py-4">
          <h2 className="font-display text-xl text-panchayat-700">{isEdit ? 'Edit scheme' : 'New scheme'}</h2>
          <button type="button" aria-label="Close scheme form" onClick={onClose} className="rounded-lg p-1.5 text-ink/40 hover:bg-ink/5 hover:text-ink"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink/60">Scheme name</label>
            <input required value={form.name} onChange={update('name')} className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink/60">Description</label>
            <textarea required rows={3} value={form.description} onChange={update('description')} className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink/60">Eligibility criteria</label>
            <textarea rows={2} value={form.eligibility_criteria} onChange={update('eligibility_criteria')} className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink/60">Required documents</label>
            <p className="mb-2 text-xs text-ink/50">Add each document separately - citizens get one upload slot per item.</p>
            <div className="mb-2 flex gap-2">
              <input
                value={docInput}
                onChange={(e) => setDocInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDoc() } }}
                placeholder="e.g. Aadhaar Card"
                className="flex-1 rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-panchayat-500"
              />
              <button type="button" onClick={addDoc} className="rounded-xl bg-sand px-4 py-2 text-sm font-semibold text-ink hover:bg-sand/70">
                Add
              </button>
            </div>
            {docNames.length > 0 && (
              <ul className="space-y-1.5">
                {docNames.map((name) => (
                  <li key={name} className="flex items-center justify-between rounded-xl bg-sand/50 px-3 py-1.5 text-sm">
                    {name}
                    <button type="button" aria-label={`Remove ${name}`} onClick={() => removeDoc(name)} className="text-ink/40 hover:text-brick-600">
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {isEdit && <p className="mt-2 text-xs text-marigold-600">Saving will replace the full document list with what's shown above.</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink/60">Max income limit (₹, optional)</label>
            <input type="number" value={form.max_income_limit} onChange={update('max_income_limit')} className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-panchayat-500" />
          </div>
          {error && <div className="rounded-xl bg-brick-100 px-3 py-2 text-sm text-brick-600">{error}</div>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="rounded-xl px-4 py-2 text-sm font-semibold text-ink/60 hover:bg-ink/5">Cancel</button>
            <button type="submit" disabled={saving} className="rounded-xl bg-panchayat-600 px-5 py-2 text-sm font-bold text-paper shadow-sm hover:bg-panchayat-700 disabled:opacity-60">
              {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Create scheme'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function DeleteSchemeModal({ scheme, superadmin, onClose, onDeleted }) {
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    setError('')
    setDeleting(true)
    try {
      if (superadmin) await schemesApi.remove(scheme.id)
      else await schemesApi.update(scheme.id, { is_active: false })
      await onDeleted()
      onClose()
    } catch (err) {
      setError(formatApiError(err, superadmin ? 'Could not delete scheme.' : 'Could not retire scheme.'))
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="w-full max-w-sm rounded-3xl bg-paper p-6 shadow-xl">
        <h2 className="mb-3 font-display text-lg text-brick-600">{superadmin ? `Delete "${scheme.name}"?` : `Retire "${scheme.name}"?`}</h2>
        <p className="mb-4 text-sm text-ink/70">
          {superadmin ? 'If citizens have already applied, JanSeva safely retires the scheme instead, so their records are never lost.' : 'This removes the scheme from the citizen catalogue while preserving applications and their audit history. Only the superadmin can permanently delete an unused scheme.'}
        </p>
        {error && <div className="mb-3 rounded-xl bg-brick-100 px-3 py-2 text-sm text-brick-600">{error}</div>}
        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm font-semibold text-ink/60 hover:bg-ink/5">Cancel</button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-xl bg-brick-500 px-4 py-2 text-sm font-bold text-paper shadow-sm hover:bg-brick-600 disabled:opacity-50"
          >
            {deleting ? (superadmin ? 'Deleting…' : 'Retiring…') : (superadmin ? 'Delete scheme' : 'Retire from catalogue')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Schemes() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { refreshCounts } = useNavCounts()
  const [schemes, setSchemes] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [applications, setApplications] = useState([])
  const [applying, setApplying] = useState(null)
  const [message, setMessage] = useState('')
  const [uploadTarget, setUploadTarget] = useState(null)
  const { needsProfile, goCompleteProfile } = useProfileGate(user.role)
  const catalogueManager = user.role === 'admin' && (!user.jurisdiction_level || ['state', 'super', ''].includes(user.jurisdiction_level))
  const superadmin = user.role === 'admin' && user.jurisdiction_level === 'super'

  const load = async () => {
    const schemeRequest = schemesApi.list(!catalogueManager)
    const applicationRequest = user.role === 'citizen' ? applicationsApi.my() : null
    const [schemesResult, applicationsResult] = await Promise.all([schemeRequest, applicationRequest])
    setSchemes(schemesResult.data)
    if (applicationsResult) setApplications(applicationsResult.data)
  }

  useEffect(() => { load() }, [])

  // Runs on every document upload AND when the upload modal closes, so a
  // citizen's card (documents uploaded count, "already applied" state)
  // never sits stale behind the modal waiting on a manual page refresh.
  const loadAndRefresh = async () => {
    await load()
    refreshCounts()
  }

  const applicationForScheme = (schemeId) => {
    const matches = applications.filter((a) => a.scheme_id === schemeId)
    if (matches.length === 0) return null
    return matches.reduce((latest, a) => (new Date(a.submitted_at) > new Date(latest.submitted_at) ? a : latest))
  }

  const handleApply = async (scheme) => {
    setApplying(scheme.id)
    setMessage('')
    try {
      const res = await applicationsApi.apply({ scheme_id: scheme.id })
      await load()
      refreshCounts()
      if (scheme.document_requirements?.length > 0) {
        setUploadTarget({ application: res.data, scheme })
      } else {
        setMessage('Application submitted. Track its status under "My Applications".')
      }
    } catch (err) {
      setMessage(formatApiError(err, 'Could not submit application.'))
    } finally {
      setApplying(null)
    }
  }

  return (
    <div className="space-y-6 pb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600">
            <Sparkles size={13} /> {t('schemes.welfarePrograms')}
          </div>
          <h1 className="font-display text-3xl text-panchayat-700">
            {user.role === 'citizen' ? t('schemes.browseSchemes') : t('schemes.title')}
          </h1>
        </div>
        {catalogueManager && (
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 rounded-xl bg-panchayat-600 px-4 py-2.5 text-sm font-bold text-paper shadow-sm transition hover:-translate-y-0.5 hover:bg-panchayat-700 hover:shadow-md"
          >
            <Plus size={16} /> {t('schemes.newScheme')}
          </button>
        )}
      </div>

      {/* Stated before any interaction rather than as a 400 after pressing
          Apply - see components/ProfileGate.jsx for why. */}
      {needsProfile && (
        <ProfileRequiredBanner
          heading="You cannot apply yet - your household profile is missing"
          body="Every scheme below is matched against your household record: your village, mandal, district and annual income. Add those details once and all of these become available to apply for."
          onComplete={goCompleteProfile}
        />
      )}

      {message && (
        <div className="rounded-2xl border border-panchayat-200 bg-panchayat-50 px-4 py-2.5 text-sm font-medium text-panchayat-700">
          {message}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {schemes.map((s) => {
          const existingApp = user.role === 'citizen' ? applicationForScheme(s.id) : null
          return (
            <div
              key={s.id}
              className="group relative overflow-hidden rounded-3xl border border-ink/7 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-600 transition group-hover:bg-panchayat-100">
                  <Landmark size={20} />
                </span>
                {catalogueManager && (
                  <div className="flex shrink-0 gap-1">
                    <button type="button" aria-label={`Edit ${s.name}`} onClick={() => setEditTarget(s)} className="rounded-lg p-1.5 text-ink/40 hover:bg-ink/5 hover:text-panchayat-600" title="Edit">
                      <Pencil size={15} />
                    </button>
                    <button type="button" aria-label={`Delete ${s.name}`} onClick={() => setDeleteTarget(s)} className="rounded-lg p-1.5 text-ink/40 hover:bg-brick-50 hover:text-brick-600" title="Delete">
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>
              <h3 className="font-display text-lg text-panchayat-900">{s.name}</h3>
              <p className="mt-1.5 text-sm leading-5 text-ink/65">{s.description}</p>

              <div className="mt-3 space-y-1.5">
                {s.eligibility_criteria && (
                  <p className="flex items-start gap-1.5 text-xs text-ink/50">
                    <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-panchayat-500" />
                    <span><span className="font-semibold text-ink/60">{t('schemes.eligibility')}:</span> {s.eligibility_criteria}</span>
                  </p>
                )}
                {s.document_requirements?.length > 0 && (
                  <p className="flex items-start gap-1.5 text-xs text-ink/50">
                    <ListChecks size={13} className="mt-0.5 shrink-0 text-panchayat-500" />
                    <span><span className="font-semibold text-ink/60">{t('schemes.documentsNeeded')}:</span> {s.document_requirements.map((d) => d.name).join(', ')}</span>
                  </p>
                )}
                {s.max_income_limit && (
                  <p className="flex items-start gap-1.5 text-xs text-ink/50">
                    <IndianRupee size={13} className="mt-0.5 shrink-0 text-panchayat-500" />
                    <span><span className="font-semibold text-ink/60">{t('schemes.incomeLimit')}:</span> ₹{s.max_income_limit.toLocaleString('en-IN')}/yr</span>
                  </p>
                )}
              </div>

              {user.role === 'citizen' && (
                <div className="mt-4 border-t border-ink/7 pt-4">
                  {existingApp && existingApp.status !== 'rejected' ? (
                    existingApp.documents_complete ? (
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-panchayat-50 px-3 py-1 text-xs font-bold text-panchayat-700">
                          <CheckCircle2 size={13} /> {t('schemes.alreadyApplied')}
                        </span>
                        {s.document_requirements?.length > 0 && (
                          <button
                            onClick={() => setUploadTarget({ application: existingApp, scheme: s })}
                            className="flex items-center gap-1.5 text-xs font-semibold text-panchayat-600 hover:underline"
                          >
                            <FileUp size={13} /> {t('schemes.manageDocuments')}
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        <div className="rounded-xl bg-marigold-100 px-3 py-2 text-xs font-medium text-marigold-700">
                          Application started, but not yet complete - {existingApp.uploaded_document_count} of {existingApp.required_document_count} required documents uploaded.
                        </div>
                        <button
                          onClick={() => setUploadTarget({ application: existingApp, scheme: s })}
                          className="flex items-center gap-2 rounded-xl bg-marigold-500 px-4 py-2 text-xs font-bold text-panchayat-900 shadow-sm transition hover:-translate-y-0.5 hover:bg-marigold-600 hover:shadow-md"
                        >
                          <FileUp size={13} /> Finish uploading documents
                        </button>
                      </div>
                    )
                  ) : (
                    <div className="space-y-2.5">
                      {existingApp && existingApp.status === 'rejected' && (
                        <div className="rounded-xl bg-brick-100 px-3 py-2 text-xs text-brick-600">
                          Your previous application was rejected{existingApp.remarks ? `: ${existingApp.remarks}` : '.'} You can apply again below.
                        </div>
                      )}
                      {needsProfile ? (
                        <ProfileLockedButton label="Complete your profile to apply" onComplete={goCompleteProfile} />
                      ) : (
                        <button
                          onClick={() => handleApply(s)}
                          disabled={applying === s.id}
                          className="flex items-center gap-2 rounded-xl bg-marigold-500 px-4 py-2 text-xs font-bold text-panchayat-900 shadow-sm transition hover:-translate-y-0.5 hover:bg-marigold-600 hover:shadow-md disabled:opacity-60"
                        >
                          <Send size={13} /> {applying === s.id ? 'Submitting…' : existingApp ? 'Apply again' : t('schemes.applyNow')}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
        {schemes.length === 0 && (
          <div className="col-span-2 rounded-3xl border border-dashed border-ink/15 bg-white/60 py-16 text-center">
            <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-500"><Landmark size={19} /></span>
            <p className="mt-3 text-sm text-ink/40">No active schemes yet.</p>
          </div>
        )}
      </div>

      {showModal && <SchemeFormModal onClose={() => setShowModal(false)} onSaved={load} />}
      {editTarget && <SchemeFormModal existingScheme={editTarget} onClose={() => setEditTarget(null)} onSaved={load} />}
      {deleteTarget && <DeleteSchemeModal scheme={deleteTarget} superadmin={superadmin} onClose={() => setDeleteTarget(null)} onDeleted={load} />}
      {uploadTarget && (
        <DocumentUploadModal
          application={uploadTarget.application}
          scheme={uploadTarget.scheme}
          onUploaded={loadAndRefresh}
          onClose={() => { setUploadTarget(null); loadAndRefresh() }}
        />
      )}
    </div>
  )
}
