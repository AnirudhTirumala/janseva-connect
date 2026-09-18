import api from './client'

export const authApi = {
  register: (data) => api.post('/api/auth/register', data),
  registerVerify: (email, code) => api.post('/api/auth/register/verify', { email, code }),
  login: (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return api.post('/api/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  me: () => api.get('/api/auth/me'),
  updateMe: (data) => api.patch('/api/auth/me', data),
  requestAccountDeletion: () => api.post('/api/auth/delete-account/request'),
  confirmAccountDeletion: (code) => api.post('/api/auth/delete-account/confirm', { code }),
  requestPasswordReset: (email) => api.post('/api/auth/password-reset/request', { email }),
  confirmPasswordReset: (email, code, new_password) =>
    api.post('/api/auth/password-reset/confirm', { email, code, new_password }),
  requestChangePasswordOtp: () => api.post('/api/auth/change-password/request-otp'),
  confirmChangePassword: (old_password, code, new_password) =>
    api.post('/api/auth/change-password/confirm', { old_password, code, new_password }),
}

export const membersApi = {
  list: (params) => api.get('/api/members/', { params }),
  getMe: () => api.get('/api/members/me'),
  createMe: (data) => api.post('/api/members/me', data),
  updateMe: (data) => api.patch('/api/members/me', data),
  get: (id) => api.get(`/api/members/${id}`),
  create: (data) => api.post('/api/members/', data),
  update: (id, data) => api.put(`/api/members/${id}`, data),
  remove: (id) => api.delete(`/api/members/${id}`),
}

export const schemesApi = {
  list: (activeOnly = true) => api.get('/api/schemes/', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/api/schemes/${id}`),
  create: (data) => api.post('/api/schemes/', data),
  update: (id, data) => api.put(`/api/schemes/${id}`, data),
  remove: (id) => api.delete(`/api/schemes/${id}`),
}

export const applicationsApi = {
  apply: (data) => api.post('/api/applications/', data),
  my: () => api.get('/api/applications/my'),
  list: (statusFilter, view) => api.get('/api/applications/', { params: { status_filter: statusFilter, view } }),
  queueCounts: () => api.get('/api/applications/queue-counts'),
  review: (id, data) => api.patch(`/api/applications/${id}/review`, data),
  downloadApprovalPdf: async (id) => {
    const res = await api.get(`/api/applications/${id}/approval-pdf/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `approval_${id}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
  uploadDocument: (applicationId, formData) =>
    api.post(`/api/applications/${applicationId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  listDocuments: (applicationId) => api.get(`/api/applications/${applicationId}/documents`),
  downloadDocument: async (applicationId, documentId, filename) => {
    const res = await api.get(`/api/applications/${applicationId}/documents/${documentId}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = filename || 'document'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
  reviewDocument: (applicationId, documentId, data) =>
    api.patch(`/api/applications/${applicationId}/documents/${documentId}/review`, data),
}

export const notificationsApi = {
  list: () => api.get('/api/notifications/'),
  unreadCount: () => api.get('/api/notifications/unread-count'),
  markRead: (id) => api.patch(`/api/notifications/${id}/read`),
  markAllRead: () => api.patch('/api/notifications/read-all'),
  markReadByLink: (link) => api.patch('/api/notifications/read-by-link', null, { params: { link } }),
}

export const messagesApi = {
  conversations: (search) => api.get('/api/messages/conversations', { params: search ? { search } : {} }),
  officeContacts: () => api.get('/api/messages/office-contacts'),
  thread: (citizenUserId) => api.get(`/api/messages/thread/${citizenUserId}`),
  send: (body, citizenUserId) => api.post('/api/messages/', { body, citizen_user_id: citizenUserId }),
  unreadCount: () => api.get('/api/messages/unread-count'),
  // channel is undefined/omitted for the legacy single merged view (mandal-level
  // staff); otherwise { scope: 'all'|'district'|'mandal', district?, mandal? }.
  internal: (channel) => api.get('/api/messages/internal', { params: channel || {} }),
  sendInternal: (body, channel) => api.post('/api/messages/internal', { body, ...(channel || {}) }),
  internalUnreadCounts: () => api.get('/api/messages/internal/unread-counts'),
}

export const certificatesApi = {
  issue: (data) => api.post('/api/certificates/', data),
  list: () => api.get('/api/certificates/'),
  my: () => api.get('/api/certificates/my'),
  request: (data) => api.post('/api/certificates/requests', data),
  requests: () => api.get('/api/certificates/requests'),
  reviewRequest: (id, data) => api.patch(`/api/certificates/requests/${id}`, data),
  issueRequest: (id) => api.post(`/api/certificates/requests/${id}/issue`),
  download: async (id, filename) => {
    const res = await api.get(`/api/certificates/${id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename ? `${filename}.pdf` : 'certificate.pdf'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
  view: async (id) => {
    const res = await api.get(`/api/certificates/${id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    window.setTimeout(() => window.URL.revokeObjectURL(url), 60000)
  },
  types: () => api.get('/api/certificates/types'),
  addType: (data) => api.post('/api/certificates/types', data),
  updateType: (id, data) => api.patch(`/api/certificates/types/${id}`, data),
  deleteType: (id) => api.delete(`/api/certificates/types/${id}`),
  remove: (id) => api.delete(`/api/certificates/${id}`),
}

export const usersApi = {
  list: () => api.get('/api/users/'),
  citizenLookup: (email) => api.get('/api/users/citizen-lookup', { params: { email } }),
  requestCreate: (data) => api.post('/api/users/request', data),
  confirmCreate: (email, code) => api.post('/api/users/confirm', { email, code }),
  activate: (id) => api.patch(`/api/users/${id}/activate`),
  deactivate: (id) => api.patch(`/api/users/${id}/deactivate`),
  reassign: (id, data) => api.patch(`/api/users/${id}/reassign`, data),
  remove: (id) => api.delete(`/api/users/${id}`),
}

export const weeklyActivitiesApi = {
  list: () => api.get('/api/weekly-activities/'),
  submit: (data) => api.post('/api/weekly-activities/', data),
}

export const issuesApi = {
  list: () => api.get('/api/issues/'),
  raise: (data) => api.post('/api/issues/', data),
  reply: (id, data) => api.patch(`/api/issues/${id}`, data),
  respond: (id, data) => api.patch(`/api/issues/${id}/respond`, data),
}

export const locationsApi = {
  districts: () => api.get('/api/locations/districts'),
}

export const dashboardApi = {
  summary: () => api.get('/api/dashboard/summary'),
  weekly: () => api.get('/api/dashboard/weekly'),
  navCounts: () => api.get('/api/dashboard/nav-counts'),
}

export const aiApi = {
  chat: (message, history) => api.post('/api/ai/chat', { message, history }),
  draftLetter: (data) => api.post('/api/ai/draft-letter', data),
  monthlyReport: (data) => api.post('/api/ai/monthly-report-summary', data),
  generateSql: (question) => api.post('/api/ai/generate-sql', { question }),
}

export const auditApi = {
  trackClick: (data) => api.post('/api/audit/click', data),
  events: (limit = 250) => api.get('/api/audit/events', { params: { limit } }),
  otps: (limit = 250) => api.get('/api/audit/otps', { params: { limit } }),
}
