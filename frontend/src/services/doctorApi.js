const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const doctorApi = request => ({
  availability: () => request('/doctor/availability'),
  createAvailability: body => request('/doctor/availability', json('POST', body)),
  updateAvailability: (id, body) => request(`/doctor/availability/${id}`, json('PUT', body)),
  deleteAvailability: id => request(`/doctor/availability/${id}`, { method: 'DELETE' }),
  leaves: () => request('/doctor/leaves'),
  createLeave: body => request('/doctor/leaves', json('POST', body)),
  deleteLeave: id => request(`/doctor/leaves/${id}`, { method: 'DELETE' }),
  pending: () => request('/doctor/appointments/pending'),
  schedule: ({ date, status } = {}) => {
    const params = new URLSearchParams()
    if (date) params.set('date', date)
    if (status) params.set('status', status)
    return request(`/doctor/schedule${params.size ? `?${params}` : ''}`)
  },
  confirm: id => request(`/doctor/appointments/${id}/confirm`, { method: 'POST' }),
  reject: (id, reason) => request(`/doctor/appointments/${id}/reject`, json('POST', { reason })),
  complete: id => request(`/doctor/appointments/${id}/complete`, { method: 'POST' }),
  noShow: id => request(`/doctor/appointments/${id}/no-show`, { method: 'POST' }),
  note: id => request(`/doctor/appointments/${id}/visit-note`),
  saveNote: (id, note_text) => request(`/doctor/appointments/${id}/visit-note`, json('PUT', { note_text })),
  history: patientId => request(`/doctor/patients/${patientId}/history`),
})
