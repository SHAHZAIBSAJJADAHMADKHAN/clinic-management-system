export const patientApi = (request) => ({
 doctors: () => request('/doctors'), slots: (id,date) => request(`/doctors/${id}/slots?date=${date}`),
 appointments: () => request('/appointments/me'), detail: id => request(`/appointments/me/${id}`),
 book: body => request('/appointments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 cancel: id => request(`/appointments/me/${id}/cancel`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),
 reschedule: (id,body) => request(`/appointments/me/${id}/reschedule`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 note: id => request(`/appointments/me/${id}/visit-note`),
})
