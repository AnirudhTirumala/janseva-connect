import { useEffect, useState } from 'react'
import { applicationsApi } from '../api/endpoints'
import { formatApiError } from '../utils/formatApiError'
import { useNavCounts } from '../context/NavCountsContext'
import { X, Download, Check, Ban, FolderOpen } from 'lucide-react'
import StatusBadge from './StatusBadge'

export default function StaffDocumentReviewModal({ application, schemeName, onReviewed, onClose }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [remarksDraft, setRemarksDraft] = useState({})
  const [error, setError] = useState('')
  const { refreshCounts } = useNavCounts()

  const load = () => {
    applicationsApi.listDocuments(application.id).then((res) => {
      setDocuments(res.data)
      setLoading(false)
      refreshCounts()
    })
  }

  useEffect(() => { load() }, [])

  const handleReview = async (docId, status) => {
    setError('')
    try {
      await applicationsApi.reviewDocument(application.id, docId, {
        status,
        remarks: remarksDraft[docId] || '',
      })
      load()
      onReviewed?.()
    } catch (err) {
      setError(formatApiError(err, 'Could not update document.'))
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-paper shadow-xl pp-scrollbar">
        <div className="flex items-center justify-between border-b border-ink/7 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-panchayat-50 text-panchayat-600"><FolderOpen size={18} /></span>
            <div>
              <h2 className="font-display text-xl text-panchayat-700">Submitted documents</h2>
              <p className="mt-0.5 text-xs text-ink/50">{schemeName}</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-ink/40 hover:bg-ink/5 hover:text-ink"><X size={20} /></button>
        </div>

        <div className="space-y-3 p-6">
          {loading && <div className="text-sm text-ink/50">Loading…</div>}
          {!loading && documents.length === 0 && (
            <div className="text-sm text-ink/50">No documents uploaded yet for this application.</div>
          )}
          {error && <div className="rounded-xl bg-brick-100 px-3 py-2 text-sm text-brick-600">{error}</div>}

          {documents.map((doc) => (
            <div key={doc.id} className="rounded-2xl border border-ink/8 p-4">
              <div className="mb-2 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink">{doc.document_name}</div>
                  <div className="truncate text-xs text-ink/50">{doc.original_filename}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={doc.status} />
                  <button
                    onClick={() => applicationsApi.downloadDocument(application.id, doc.id, doc.original_filename)}
                    className="rounded-lg p-2 text-ink/50 hover:bg-ink/5 hover:text-panchayat-600"
                    title="Download"
                  >
                    <Download size={16} />
                  </button>
                </div>
              </div>

              {doc.remarks && <div className="mb-2 text-xs text-ink/50">Note: {doc.remarks}</div>}

              {doc.status === 'pending' && (
                <div className="flex items-center gap-2">
                  <input
                    placeholder="Remarks (required to reject)"
                    value={remarksDraft[doc.id] || ''}
                    onChange={(e) => setRemarksDraft({ ...remarksDraft, [doc.id]: e.target.value })}
                    className="flex-1 rounded-lg border border-ink/15 px-2.5 py-1.5 text-xs outline-none focus:border-panchayat-500"
                  />
                  <button
                    onClick={() => handleReview(doc.id, 'approved')}
                    className="flex items-center gap-1 rounded-lg bg-panchayat-600 px-2.5 py-1.5 text-xs font-bold text-paper hover:bg-panchayat-700"
                  >
                    <Check size={13} /> Approve
                  </button>
                  <button
                    onClick={() => handleReview(doc.id, 'rejected')}
                    disabled={!remarksDraft[doc.id]?.trim()}
                    title={!remarksDraft[doc.id]?.trim() ? 'Enter a reason above before rejecting' : ''}
                    className="flex items-center gap-1 rounded-lg bg-brick-500 px-2.5 py-1.5 text-xs font-bold text-paper hover:bg-brick-600 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Ban size={13} /> Reject
                  </button>
                </div>
              )}
            </div>
          ))}

          <div className="flex justify-end pt-2">
            <button onClick={onClose} className="rounded-xl bg-panchayat-600 px-5 py-2 text-sm font-bold text-paper shadow-sm hover:bg-panchayat-700">
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
