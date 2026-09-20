import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiRequest } from '../services/api'
import { doctorApi } from '../services/doctorApi'
import { Button, Card, EmptyState, ErrorState, Input, LoadingState, Select, StatCard, StatusBadge, Textarea } from '../components/ui'
import { formatAppointmentDateTime } from '../utils/time'

const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const appointmentPatient = appointment => appointment.profiles?.full_name || 'Patient'
const formatTime = formatAppointmentDateTime
const messageOf = error => error?.message || 'Unable to complete this request.'

const useDoctor = () => {
  const { session } = useAuth()
  return doctorApi((path, options) => apiRequest(path, options, session?.access_token))
}

function Notice({ children }) { return children ? <Card className="doctor-notice" role="status">{children}</Card> : null }
function AppointmentCard({ appointment, onAction, busy }) {
  const final = ['completed', 'no_show', 'cancelled', 'rejected'].includes(appointment.status)
  return <Card className="appointment-card"><div className="appointment-card__heading"><div><StatusBadge status={appointment.status} /><h3>{appointmentPatient(appointment)}</h3><p>{formatTime(appointment.start_at)}</p></div><Link to={`/doctor/appointments/${appointment.id}`}>Open appointment</Link></div>
    {appointment.status === 'pending' && <div className="inline-actions"><Button loading={busy === `confirm-${appointment.id}`} onClick={() => onAction('confirm', appointment.id)}>Confirm</Button><Button variant="destructive" loading={busy === `reject-${appointment.id}`} onClick={() => onAction('reject', appointment.id)}>Reject</Button></div>}
    {appointment.status === 'confirmed' && <div className="inline-actions"><Button loading={busy === `complete-${appointment.id}`} onClick={() => onAction('complete', appointment.id)}>Mark completed</Button><Button variant="secondary" loading={busy === `no-show-${appointment.id}`} onClick={() => onAction('no-show', appointment.id)}>Mark no-show</Button></div>}
    {!final && <p className="muted-copy">Finalization eligibility is confirmed securely by the clinic.</p>}
  </Card>
}

export function DoctorDashboard() {
  const api = useDoctor(); const [data, setData] = useState(); const [error, setError] = useState('')
  const today = new Date().toISOString().slice(0, 10)
  useEffect(() => { Promise.all([api.schedule({ date: today }), api.pending()]).then(([schedule, pending]) => setData({ schedule: schedule.filter(item => item.start_at.slice(0, 10) === today), pending })).catch(error => setError(messageOf(error))) }, [])
  if (!data && !error) return <LoadingState />
  if (error) return <ErrorState>{error}</ErrorState>
  const confirmed = data.schedule.filter(item => item.status === 'confirmed')
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Clinical workspace</p><h2>Today at a glance</h2></div><Link className="button button--primary" to="/doctor/schedule">View schedule</Link></div><div className="foundation-grid"><StatCard label="Pending requests" value={data.pending.length} /><StatCard label="Confirmed today" value={confirmed.length} /><Card><Link to="/doctor/availability">Manage availability</Link><p className="muted-copy">Keep future booking windows up to date.</p></Card></div><section><div className="section-heading"><h2>Today’s schedule</h2><Link to="/doctor/schedule">Review all</Link></div>{data.schedule.length ? <div className="appointment-list">{data.schedule.map(item => <Card key={item.id}><StatusBadge status={item.status} /><h3>{appointmentPatient(item)}</h3><p>{formatTime(item.start_at)}</p></Card>)}</div> : <EmptyState>No appointments are scheduled for today.</EmptyState>}</section><section><div className="section-heading"><h2>Pending requests</h2><Link to="/doctor/requests">Review all</Link></div>{data.pending.length ? <div className="appointment-list">{data.pending.slice(0, 3).map(item => <Card key={item.id}><StatusBadge status="pending" /><h3>{appointmentPatient(item)}</h3><p>{formatTime(item.start_at)}</p></Card>)}</div> : <EmptyState>No appointment requests need a decision.</EmptyState>}</section><div className="quick-links"><Link to="/doctor/availability">Availability</Link><Link to="/doctor/leaves">Leave management</Link></div></div>
}

function useAppointments(load) {
  const [items, setItems] = useState(); const [error, setError] = useState(''); const [busy, setBusy] = useState(''); const [notice, setNotice] = useState('')
  const refresh = () => load().then(setItems).catch(error => setError(messageOf(error)))
  useEffect(() => { refresh() }, [])
  return { items, error, busy, notice, setBusy, setNotice, refresh, setError }
}
async function transition(api, action, id, reason) {
  if (action === 'confirm') return api.confirm(id)
  if (action === 'reject') return api.reject(id, reason)
  if (action === 'complete') return api.complete(id)
  return api.noShow(id)
}
function AppointmentActions({ api, state, requireReason = false }) {
  const [rejecting, setRejecting] = useState(''); const [reason, setReason] = useState('')
  const run = async (action, id) => {
    if (action === 'reject' && !rejecting) { setRejecting(id); return }
    if (action === 'reject' && rejecting === id && !reason.trim()) { state.setError('A rejection reason is required.'); return }
    state.setBusy(`${action}-${id}`); state.setNotice(''); state.setError('')
    try { await transition(api, action, id, reason); state.setNotice(action === 'confirm' ? 'Appointment confirmed.' : action === 'reject' ? 'Appointment rejected.' : action === 'complete' ? 'Appointment marked completed.' : 'Appointment marked no-show.'); setRejecting(''); setReason(''); await state.refresh() } catch (error) { state.setError(messageOf(error)) } finally { state.setBusy('') }
  }
  return <>{state.items.map(appointment => <div key={appointment.id}>{rejecting === appointment.id && <Card className="reason-card"><Textarea id={`reason-${appointment.id}`} label="Reason for rejection" value={reason} onChange={event => setReason(event.target.value)} /><div className="inline-actions"><Button variant="destructive" onClick={() => run('reject', appointment.id)}>Confirm rejection</Button><Button variant="ghost" onClick={() => setRejecting('')}>Cancel</Button></div></Card>}<AppointmentCard appointment={appointment} busy={state.busy} onAction={run} /></div>)}</>
}

export function PendingRequests() {
  const api = useDoctor(); const state = useAppointments(api.pending)
  if (!state.items && !state.error) return <LoadingState />
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Appointment requests</p><h2>Pending decisions</h2></div></div><Notice>{state.notice}</Notice>{state.error && <ErrorState>{state.error}</ErrorState>}{!state.items?.length ? <EmptyState>No pending appointment requests.</EmptyState> : <div className="appointment-list"><AppointmentActions api={api} state={state} /></div>}</div>
}

export function DoctorSchedule() {
  const api = useDoctor(); const [filters, setFilters] = useState({ date: '', status: '' }); const [state, setState] = useState({ loading: true, items: [], error: '' }); const [busy, setBusy] = useState(''); const [notice, setNotice] = useState('')
  const refresh = () => { setState(current => ({ ...current, loading: true })); api.schedule(filters).then(items => setState({ loading: false, items, error: '' })).catch(error => setState({ loading: false, items: [], error: messageOf(error) })) }
  useEffect(() => { refresh() }, [])
  const perform = async (action, id) => { setBusy(`${action}-${id}`); setNotice(''); try { await transition(api, action, id); setNotice(action === 'complete' ? 'Appointment marked completed.' : 'Appointment marked no-show.'); refresh() } catch (error) { setState(current => ({ ...current, error: messageOf(error) })) } finally { setBusy('') } }
  if (state.loading && !state.items.length) return <LoadingState />
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Schedule</p><h2>Your appointments</h2></div></div><div className="filter-row"><Input id="schedule-date" label="From date" type="date" value={filters.date} onChange={event => setFilters({ ...filters, date: event.target.value })} /><Select id="schedule-status" label="Status" value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option>{['pending', 'confirmed', 'rejected', 'cancelled', 'completed', 'no_show'].map(status => <option key={status} value={status}>{status.replace('_', ' ')}</option>)}</Select><Button onClick={refresh}>Apply filters</Button></div><Notice>{notice}</Notice>{state.error && <ErrorState>{state.error}</ErrorState>}{!state.items.length ? <EmptyState>No appointments match these filters.</EmptyState> : <div className="appointment-list">{state.items.map(appointment => <AppointmentCard key={appointment.id} appointment={appointment} busy={busy} onAction={perform} />)}</div>}</div>
}

export function AvailabilityManagement() {
  const api = useDoctor(); const [items, setItems] = useState(); const [form, setForm] = useState({ day_of_week: 0, start_time: '09:00', end_time: '17:00' }); const [editing, setEditing] = useState(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('')
  const refresh = () => api.availability().then(setItems).catch(error => setError(messageOf(error)))
  useEffect(() => { refresh() }, [])
  const save = async event => { event.preventDefault(); setBusy(true); setError(''); setNotice(''); try { if (editing) await api.updateAvailability(editing, form); else await api.createAvailability(form); setNotice(editing ? 'Availability updated.' : 'Availability added.'); setEditing(null); setForm({ day_of_week: 0, start_time: '09:00', end_time: '17:00' }); await refresh() } catch (error) { setError(messageOf(error)) } finally { setBusy(false) } }
  const edit = item => { setEditing(item.id); setForm({ day_of_week: item.day_of_week, start_time: item.start_time.slice(0, 5), end_time: item.end_time.slice(0, 5) }); window.scrollTo?.({ top: 0, behavior: 'smooth' }) }
  const remove = async id => { setBusy(true); setError(''); try { await api.deleteAvailability(id); setNotice('Availability removed.'); await refresh() } catch (error) { setError(messageOf(error)) } finally { setBusy(false) } }
  if (!items && !error) return <LoadingState />
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Booking windows</p><h2>Availability</h2></div></div><Card><form className="form-grid" onSubmit={save}><Select id="availability-day" label="Weekday" value={form.day_of_week} onChange={event => setForm({ ...form, day_of_week: Number(event.target.value) })}>{weekdays.map((day, index) => <option key={day} value={index}>{day}</option>)}</Select><Input id="availability-start" label="Start time" type="time" value={form.start_time} onChange={event => setForm({ ...form, start_time: event.target.value })} required /><Input id="availability-end" label="End time" type="time" value={form.end_time} onChange={event => setForm({ ...form, end_time: event.target.value })} required /><div className="inline-actions"><Button loading={busy} type="submit">{editing ? 'Save changes' : 'Add availability'}</Button>{editing && <Button type="button" variant="ghost" onClick={() => { setEditing(null); setForm({ day_of_week: 0, start_time: '09:00', end_time: '17:00' }) }}>Cancel edit</Button>}</div></form></Card><Notice>{notice}</Notice>{error && <ErrorState>{error}</ErrorState>}{!items?.length ? <EmptyState>No availability has been set.</EmptyState> : <div className="availability-list">{items.map(item => <Card key={item.id}><h3>{weekdays[item.day_of_week]}</h3><p>{item.start_time.slice(0, 5)} – {item.end_time.slice(0, 5)}</p><div className="inline-actions"><Button variant="secondary" disabled={busy} onClick={() => edit(item)}>Edit</Button><Button variant="destructive" loading={busy} onClick={() => remove(item.id)}>Delete</Button></div></Card>)}</div>}</div>
}

export function LeaveManagement() {
  const api = useDoctor(); const [items, setItems] = useState(); const [leaveDate, setLeaveDate] = useState(''); const [reason, setReason] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('')
  const refresh = () => api.leaves().then(setItems).catch(error => setError(messageOf(error)))
  useEffect(() => { refresh() }, [])
  const save = async event => { event.preventDefault(); setBusy(true); setError(''); setNotice(''); try { await api.createLeave({ leave_date: leaveDate, reason: reason || null }); setNotice('Leave saved. Affected pending and confirmed appointments are handled by the clinic.'); setLeaveDate(''); setReason(''); await refresh() } catch (error) { setError(messageOf(error)) } finally { setBusy(false) } }
  const remove = async id => { setBusy(true); setError(''); try { await api.deleteLeave(id); setNotice('Leave removed.'); await refresh() } catch (error) { setError(messageOf(error)) } finally { setBusy(false) } }
  if (!items && !error) return <LoadingState />
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Time away</p><h2>Leave management</h2></div></div><Card><p className="warning-copy">Adding leave may automatically cancel affected Pending and Confirmed appointments. The clinic will process those changes securely.</p><form className="form-grid" onSubmit={save}><Input id="leave-date" label="Leave date" type="date" min={new Date(Date.now() + 86400000).toISOString().slice(0, 10)} value={leaveDate} onChange={event => setLeaveDate(event.target.value)} required /><Textarea id="leave-reason" label="Reason (optional)" value={reason} onChange={event => setReason(event.target.value)} maxLength="500" /><Button loading={busy} type="submit">Add leave</Button></form></Card><Notice>{notice}</Notice>{error && <ErrorState>{error}</ErrorState>}{!items?.length ? <EmptyState>No future leave is recorded.</EmptyState> : <div className="availability-list">{items.map(item => <Card key={item.id}><h3>{item.leave_date}</h3>{item.reason && <p>{item.reason}</p>}<Button variant="destructive" loading={busy} onClick={() => remove(item.id)}>Remove leave</Button></Card>)}</div>}</div>
}

export function DoctorAppointmentDetail() {
  const api = useDoctor(); const { appointmentId } = useParams(); const [appointment, setAppointment] = useState(); const [note, setNote] = useState(''); const [noteFound, setNoteFound] = useState(false); const [history, setHistory] = useState(); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [saving, setSaving] = useState(false)
  const load = async () => { try { const appointments = await api.schedule(); const current = appointments.find(item => item.id === appointmentId); if (!current) { setError('Appointment not found in your schedule.'); return } setAppointment(current); try { const result = await api.note(appointmentId); setNote(result.note_text); setNoteFound(true) } catch { setNoteFound(false) } const records = await api.history(current.patient_profile_id); setHistory(records) } catch (error) { setError(messageOf(error)) } }
  useEffect(() => { load() }, [appointmentId])
  const save = async event => { event.preventDefault(); setSaving(true); setError(''); try { await api.saveNote(appointmentId, note); setNoteFound(true); setNotice('Visit note saved securely.') } catch (error) { setError(messageOf(error)) } finally { setSaving(false) } }
  if (!appointment && !error) return <LoadingState />
  if (error) return <ErrorState>{error}</ErrorState>
  return <div className="page-stack"><Link to="/doctor/schedule">← Back to schedule</Link><Card><StatusBadge status={appointment.status} /><h2>{appointmentPatient(appointment)}</h2><p>{formatTime(appointment.start_at)}</p></Card><Card><h2>Visit note</h2>{!noteFound && <p className="muted-copy">No visit note has been recorded yet.</p>}<form className="page-stack" onSubmit={save}><Textarea id="visit-note" label="Clinical note" value={note} onChange={event => setNote(event.target.value)} maxLength="10000" required /><Button loading={saving} type="submit">{noteFound ? 'Update note' : 'Save note'}</Button></form></Card><Notice>{notice}</Notice><section><h2>Authorized patient history</h2>{history === undefined ? <LoadingState /> : !history.length ? <EmptyState>No prior appointments with this patient.</EmptyState> : <div className="appointment-list">{history.map(record => <Card key={record.id}><StatusBadge status={record.status} /><p>{formatTime(record.start_at)}</p>{record.visit_notes?.[0]?.note_text && <p className="note-preview">{record.visit_notes[0].note_text}</p>}</Card>)}</div>}</section></div>
}
