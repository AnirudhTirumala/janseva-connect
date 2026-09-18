import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { applicationsApi, schemesApi, notificationsApi } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import { useNavCounts } from '../context/NavCountsContext'
import StatusBadge from '../components/StatusBadge'
import DocumentUploadModal from '../components/DocumentUploadModal'
import StaffDocumentReviewModal from '../components/StaffDocumentReviewModal'
import { formatApiError } from '../utils/formatApiError'
import { ClipboardList, Download, Eye, FileUp, FolderOpen, Lock, Sparkles } from 'lucide-react'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'under_review', label: 'Under review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

export default function Applications() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { refreshCounts } = useNavCounts()
  const [applications, setApplications] = useState([])
  const [schemeMap, setSchemeMap] = useState({})
  const [loadError, setLoadError] = useState('')
  // 'actionable' = the citizen has done their part and an officer can act.
  // 'awaiting_citizen' = still missing mandatory documents. Separate axis
  // from status, so both can be applied at once.
  const [view, setView] = useState('actionable')
  const [queueCounts, setQueueCounts] = useState(null)
  const [filter, setFilter] = useState('')
  const [remarksDraft, setRemarksDraft] = useState({})
  const [uploadTarget, setUploadTarget] = useState(null)
  const [reviewTarget, setReviewTarget] = useState(null)

  const load = async () => {
    // allSettled, not all: these are independent, and one failing request must
    // not blank the whole table. A Promise.all here meant an unrelated error on
    // the members call rejected load() before setApplications ever ran, so the
    // queue rendered "No applications found" while the API was returning rows.
    const isStaff = user.role !== 'citizen'
    const [applicationsResult, schemesResult, countsResult] = await Promise.allSettled([
      isStaff ? applicationsApi.list(filter || undefined, view) : applicationsApi.my(),
      schemesApi.list(false),
      isStaff ? applicationsApi.queueCounts() : Promise.resolve(null),
    ])
    if (countsResult.status === 'fulfilled' && countsResult.value) {
      setQueueCounts(countsResult.value.data)
    }
    if (applicationsResult.status === 'fulfilled') {
      setApplications(applicationsResult.value.data)
      setLoadError('')
    } else {
      setLoadError(formatApiError(applicationsResult.reason, 'Could not load applications.'))
    }
    if (schemesResult.status === 'fulfilled') {
      setSchemeMap(Object.fromEntries(schemesResult.value.data.map((s) => [s.id, s])))
    }
  }

  // Runs after every upload AND after the modal closes, so the row behind
  // it (document count, "already applied" state, status) is never stale -
  // previously this only reran once the modal closed, so a citizen saw no
  // change at all until they manually refreshed the page.
  const loadAndRefresh = async () => {
    await load()
    refreshCounts()
  }

  useEffect(() => { load() }, [filter, view])

  // Visiting this page is itself how a citizen "sees" these updates - the
  // badge shouldn't stay stuck just because they navigated here directly
  // instead of clicking through the notification bell.
  useEffect(() => {
    if (user.role === 'citizen') {
      notificationsApi.markReadByLink('/applications').then(refreshCounts)
    }
  }, [])

  const handleReview = async (id, status) => {
    try {
      await applicationsApi.review(id, { status, remarks: remarksDraft[id] || '' })
      loadAndRefresh()
    } catch (err) {
      alert(formatApiError(err, 'Could not update application.'))
    }
  }

  const openReview = (application, schemeName) => setReviewTarget({ application, schemeName })

  const isStaffAdmin = user.role !== 'citizen'

  return (
    <div className="space-y-6 pb-6">
      <div>
        <div className="mb-1 flex items-center gap-1.5 text-xs uppercase tracking-widest text-marigold-600">
          <Sparkles size={13} /> {isStaffAdmin ? t('applications.approvalQueue') : t('applications.yourSubmissions')}
        </div>
        <h1 className="font-display text-3xl text-panchayat-700">
          {isStaffAdmin ? t('applications.titleStaff') : t('applications.titleCitizen')}
        </h1>
      </div>

      {/* Two axes, deliberately not merged into one pill row: readiness is
          about whether the citizen has finished, status is about where the
          office has got to. Folding them together would make "Pending"
          ambiguous and destroy the real work queue, "pending AND actionable". */}
      {isStaffAdmin && (
        <div className="flex flex-wrap gap-2">
          {[
            { value: 'actionable', label: 'Needs your action', count: queueCounts?.actionable },
            { value: 'awaiting_citizen', label: 'Awaiting citizen', count: queueCounts?.awaiting_citizen },
            { value: 'all', label: 'Everything', count: queueCounts?.total },
          ].map(({ value, label, count }) => (
            <button
              key={value}
              onClick={() => setView(value)}
              className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                view === value
                  ? 'bg-panchayat-700 text-paper shadow-sm'
                  : 'border border-ink/10 bg-white text-ink/60 hover:bg-panchayat-50'
              }`}
            >
              {label}
              {count !== undefined && count !== null && (
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                  view === value ? 'bg-white/20' : 'bg-panchayat-50 text-panchayat-700'
                }`}>{count}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {isStaffAdmin && view === 'awaiting_citizen' && (
        <p className="rounded-xl border border-marigold-500/25 bg-marigold-100 px-4 py-2.5 text-xs leading-5 text-panchayat-800">
          These citizens still owe required documents, so there is nothing to approve yet. The
          portal emails them when a document is rejected, but nobody is reminded automatically
          that an upload was never finished - use Chat to follow one up.
        </p>
      )}

      {isStaffAdmin && (
        <div className="flex flex-wrap gap-2">
          {FILTERS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                filter === value ? 'bg-panchayat-700 text-paper shadow-sm' : 'bg-white border border-ink/10 text-ink/60 hover:bg-panchayat-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="overflow-hidden rounded-3xl border border-ink/7 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-ink/7 bg-[#fbfaf7] text-left text-[11px] font-bold uppercase tracking-[.1em] text-ink/45">
                <th className="px-5 py-3.5">{t('applications.scheme')}</th>
                {isStaffAdmin && <th className="px-5 py-3.5">{t('applications.applicant')}</th>}
                <th className="px-5 py-3.5">{t('applications.submitted')}</th>
                <th className="px-5 py-3.5">{t('applications.status')}</th>
                <th className="px-5 py-3.5">{t('applications.documents')}</th>
                {isStaffAdmin && <th className="px-5 py-3.5">Action</th>}
              </tr>
            </thead>
            <tbody>
              {applications.map((a) => {
                const scheme = schemeMap[a.scheme_id]
                const needsDocumentReview = a.required_document_count > 0 && !a.documents_reviewed
                const canApprove = a.required_document_count === 0 || a.documents_approved
                return (
                  <tr key={a.id} className="border-b border-ink/5 align-top last:border-0 hover:bg-panchayat-50/30">
                    <td className="px-5 py-4 font-semibold text-ink">{scheme?.name || `Scheme #${a.scheme_id}`}</td>
                    {isStaffAdmin && <td className="px-5 py-4 text-ink/70">{a.member_name || `Member #${a.member_id}`}</td>}
                    <td className="px-5 py-4 text-ink/70">{new Date(a.submitted_at).toLocaleDateString('en-IN')}</td>
                    <td className="px-5 py-4">
                      <StatusBadge status={a.status} />
                      {/* Not staff-only any more. This was the one place the incomplete state
                      was stated, and a citizen could not see it - so the person who had to
                      act was the only one never told. */}
                  {!a.documents_complete && a.required_document_count > 0 && (
                        <div className="mt-1.5 text-[11px] font-medium text-marigold-700">
                          {a.uploaded_document_count}/{a.required_document_count} documents uploaded
                          {isStaffAdmin ? ' - awaiting citizen' : ' - upload the rest to complete this application'}
                        </div>
                      )}
                      {isStaffAdmin && a.documents_complete && !a.documents_reviewed && a.required_document_count > 0 && (
                        <div className="mt-1.5 text-[11px] font-medium text-marigold-700">
                          {a.document_review_pending_count} required document{a.document_review_pending_count === 1 ? '' : 's'} awaiting review
                        </div>
                      )}
                      {isStaffAdmin && a.documents_reviewed && !a.documents_approved && a.required_document_count > 0 && (
                        <div className="mt-1.5 text-[11px] font-medium text-brick-600">
                          A required document was rejected - approval is unavailable.
                        </div>
                      )}
                      {a.remarks && <div className="mt-1.5 max-w-xs text-xs text-ink/50">{a.remarks}</div>}
                      {isStaffAdmin && a.reviewed_by_name && a.reviewed_at && (
                        <div className="mt-1.5 text-[11px] text-ink/40">
                          by {a.reviewed_by_name}, {new Date(a.reviewed_at).toLocaleDateString('en-IN')}{' '}
                          {new Date(a.reviewed_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      )}
                      {!isStaffAdmin && a.status === 'approved' && (
                        <button
                          onClick={() => applicationsApi.downloadApprovalPdf(a.id)}
                          className="mt-1.5 flex items-center gap-1 text-[11px] font-semibold text-panchayat-600 hover:underline"
                        >
                          <Download size={11} /> Download approval PDF
                        </button>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {isStaffAdmin ? (
                        <button
                          onClick={() => openReview(a, scheme?.name)}
                          className="flex items-center gap-1.5 text-xs font-semibold text-panchayat-600 hover:underline"
                        >
                          {a.documents_reviewed ? <Eye size={13} /> : <FolderOpen size={13} />} {a.documents_reviewed ? 'Reviewed documents' : t('applications.viewDocuments')}
                        </button>
                      ) : scheme?.document_requirements?.length > 0 ? (
                        <button
                          onClick={() => setUploadTarget({ application: a, scheme })}
                          className="flex items-center gap-1.5 text-xs font-semibold text-panchayat-600 hover:underline"
                        >
                          <FileUp size={13} /> {t('applications.manageDocuments')}
                        </button>
                      ) : (
                        <span className="text-xs text-ink/30">—</span>
                      )}
                    </td>
                    {isStaffAdmin && (a.status === 'pending' || a.status === 'under_review') && (
                      <td className="px-5 py-4">
                        <div className="flex max-w-[240px] flex-col gap-1.5">
                          <input
                            placeholder="Remarks (required to reject)"
                            value={remarksDraft[a.id] || ''}
                            onChange={(e) => setRemarksDraft({ ...remarksDraft, [a.id]: e.target.value })}
                            className="rounded-lg border border-ink/15 px-2.5 py-1.5 text-xs outline-none focus:border-panchayat-500"
                          />
                          {needsDocumentReview ? (
                            <button
                              onClick={() => openReview(a, scheme?.name)}
                              title="Review every required document before you can change this application"
                              className="flex items-center justify-center gap-1.5 rounded-lg bg-marigold-100 px-2.5 py-1.5 text-xs font-bold text-marigold-700 hover:bg-marigold-100/70"
                            >
                              <Lock size={12} /> Review documents first
                            </button>
                          ) : (
                            <div className="flex gap-1.5">
                              {a.status === 'pending' && (
                                <button onClick={() => handleReview(a.id, 'under_review')} className="rounded-lg bg-panchayat-100 px-2.5 py-1.5 text-xs font-bold text-panchayat-700 hover:bg-panchayat-300/50">
                                  Mark reviewing
                                </button>
                              )}
                              <button
                                onClick={() => handleReview(a.id, 'approved')}
                                disabled={!canApprove}
                                title={!canApprove ? 'Approve every required document before approving the application' : ''}
                                className="rounded-lg bg-panchayat-600 px-2.5 py-1.5 text-xs font-bold text-paper hover:bg-panchayat-700 disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleReview(a.id, 'rejected')}
                                disabled={!remarksDraft[a.id]?.trim()}
                                title={!remarksDraft[a.id]?.trim() ? 'Enter a reason above before rejecting' : ''}
                                className="rounded-lg bg-brick-500 px-2.5 py-1.5 text-xs font-bold text-paper hover:bg-brick-600 disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
              {applications.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-16 text-center">
                    <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-panchayat-50 text-panchayat-500"><ClipboardList size={19} /></span>
                    {/* "None found" and "we could not load them" are very
                        different facts - showing the first for the second is
                        how a working queue looks empty for hours. */}
                    {loadError
                      ? <p className="mt-3 text-sm font-semibold text-brick-600">{loadError}</p>
                      : isStaffAdmin && view === 'actionable' && queueCounts?.awaiting_citizen > 0
                        ? (
                          <p className="mt-3 text-sm text-ink/50">
                            Nothing needs your action right now.{' '}
                            <button onClick={() => setView('awaiting_citizen')} className="font-bold text-panchayat-700 hover:underline">
                              {queueCounts.awaiting_citizen} awaiting citizen documents
                            </button>
                            {' '}- telling a staff member they have no work when rows are merely hidden would be a lie.
                          </p>
                        )
                        : <p className="mt-3 text-sm text-ink/40">No applications found.</p>}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {uploadTarget && (
        <DocumentUploadModal
          application={uploadTarget.application}
          scheme={uploadTarget.scheme}
          onUploaded={loadAndRefresh}
          onClose={() => { setUploadTarget(null); loadAndRefresh() }}
        />
      )}
      {reviewTarget && (
        <StaffDocumentReviewModal
          application={reviewTarget.application}
          schemeName={reviewTarget.schemeName}
          onReviewed={loadAndRefresh}
          onClose={() => { setReviewTarget(null); loadAndRefresh() }}
        />
      )}
    </div>
  )
}
