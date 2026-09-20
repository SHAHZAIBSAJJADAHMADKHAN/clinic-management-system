const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const adminApi = request => ({
  dashboard: () => request('/admin/dashboard'),
  doctors: () => request('/admin/doctors'),
  createDoctor: body => request('/admin/doctors', json('POST', body)),
  deactivateDoctor: id => request(`/admin/doctors/${id}/deactivate`, { method: 'POST' }),
  patients: search => request(`/admin/patients${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  appointments: ({ doctorId, date, status } = {}) => {
    const params = new URLSearchParams()
    if (doctorId) params.set('doctor_id', doctorId)
    if (date) params.set('date', date)
    if (status) params.set('status', status)
    return request(`/admin/appointments${params.size ? `?${params}` : ''}`)
  },
  cancelAppointment: (id, reason) => request(`/admin/appointments/${id}/cancel`, json('POST', { reason: reason || null })),
})
