const STATUS_STYLES = {
  pending: 'bg-marigold-100 text-marigold-600',
  under_review: 'bg-panchayat-100 text-panchayat-600',
  approved: 'bg-panchayat-100 text-panchayat-700',
  rejected: 'bg-brick-100 text-brick-600',
}

const STATUS_LABELS = {
  pending: 'Pending',
  under_review: 'Under review',
  approved: 'Approved',
  rejected: 'Rejected',
}

export default function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium tracking-wide uppercase ${
        STATUS_STYLES[status] || 'bg-sand text-ink'
      }`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}
