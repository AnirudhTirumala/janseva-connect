import { useEffect, useState } from 'react'
import { applicationsApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import { useNavCounts } from '../context/NavCountsContext'
import { X, Upload, CheckCircle2, Clock, XCircle, Download, FileUp } from 'lucide-react'
import StatusBadge from './StatusBadge'

function DocumentRow({ requirement, application, existingDoc, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('document_name', requirement.name)
      formData.append('requirement_id', requirement.id)
      formData.append('file', file)
      await applicationsApi.uploadDocument(application.id, formData)
      onUploaded()
    } catch (err) {
      setError(formatApiError(err, 'Upload failed.'))
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-ink/8 p-4 transition hover:border-ink/15">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          {requirement.name}
          {requirement.is_mandatory && <span className="text-xs text-brick-500">*</span>}
        </div>
        {existingDoc ? (
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge status={existingDoc.status} />
            <span className="truncate text-xs text-ink/50">{existingDoc.original_filename}</span>
          </div>
        ) : (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-ink/40">
            <Clock size={12} /> Not uploaded yet
          </div>
        )}
        {existingDoc?.remarks && (
          <div className="mt-1 text-xs text-ink/50">Note: {existingDoc.remarks}</div>
        )}
        {error && <div className="mt-1 text-xs text-brick-600">{error}</div>}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {existingDoc && (
          <button
            onClick={() => applicationsApi.downloadDocument(application.id, existingDoc.id, existingDoc.original_filename)}
            className="rounded-lg p-2 text-ink/50 hover:bg-ink/5 hover:text-panchayat-600"
            title="Download"
          >
            <Download size={16} />
          </button>
        )}
        <label className="flex cursor-pointer items-center gap-1.5 rounded-xl bg-sand px-3 py-2 text-xs font-semibold text-ink hover:bg-sand/70">
          <Upload size={13} />
          {uploading ? 'Uploading…' : existingDoc ? 'Replace' : 'Upload'}
          <input type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleFileChange} disabled={uploading} />
        </label>
      </div>
    </div>
  )
}

// onUploaded (optional): called after every successful upload, not just on
// close - so a citizen's applications list updates live behind this modal
// instead of only once they close it (see Applications.jsx / Schemes.jsx).
export default function DocumentUploadModal({ application, scheme, onUploaded, onClose }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const { refreshCounts } = useNavCounts()

  const load = async () => {
    const res = await applicationsApi.listDocuments(application.id)
    setDocuments(res.data)
    setLoading(false)
    refreshCounts()
    // Wait for the list behind this modal to receive the new application
    // state before the citizen sees the next action. This eliminates the
    // old refresh race after a successful document upload.
    await onUploaded?.()
  }

  useEffect(() => { load() }, [])

  const docByRequirement = Object.fromEntries(documents.map((d) => [d.requirement_id, d]))
  const requirements = scheme?.document_requirements || []
  const allMandatoryUploaded = requirements
    .filter((r) => r.is_mandatory)
    .every((r) => docByRequirement[r.id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-paper shadow-xl pp-scrollbar">
        <div className="flex items-center justify-between border-b border-ink/7 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-panchayat-50 text-panchayat-600"><FileUp size={18} /></span>
            <div>
              <h2 className="font-display text-xl text-panchayat-700">Upload documents</h2>
              <p className="mt-0.5 text-xs text-ink/50">{scheme?.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-ink/40 hover:bg-ink/5 hover:text-ink"><X size={20} /></button>
        </div>

        <div className="space-y-3 p-6">
          {loading && <div className="text-sm text-ink/50">Loading…</div>}

          {!loading && requirements.length === 0 && (
            <div className="text-sm text-ink/50">This scheme has no specific document requirements listed.</div>
          )}

          {!loading && requirements.map((req) => (
            <DocumentRow
              key={req.id}
              requirement={req}
              application={application}
              existingDoc={docByRequirement[req.id]}
              onUploaded={load}
            />
          ))}

          {!loading && requirements.length > 0 && (
            <div className={`mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ${allMandatoryUploaded ? 'bg-panchayat-50 text-panchayat-700' : 'bg-marigold-100 text-marigold-700'}`}>
              {allMandatoryUploaded ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              {allMandatoryUploaded ? 'All required documents uploaded.' : 'Some required documents are still missing.'}
            </div>
          )}

          <div className="flex justify-end pt-3">
            <button onClick={onClose} className="rounded-xl bg-panchayat-600 px-5 py-2 text-sm font-bold text-paper shadow-sm hover:bg-panchayat-700">
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
