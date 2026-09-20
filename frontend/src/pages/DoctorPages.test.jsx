import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { RequireAuth } from '../routes/Guards'
import { AvailabilityManagement, DoctorAppointmentDetail, DoctorDashboard, DoctorSchedule, LeaveManagement, PendingRequests } from './DoctorPages'

const auth = vi.hoisted(() => ({ session: { access_token: 'test-token' }, loading: false, error: null, profile: { role: 'doctor' } }))
const api = vi.hoisted(() => ({ availability: vi.fn(), createAvailability: vi.fn(), updateAvailability: vi.fn(), deleteAvailability: vi.fn(), leaves: vi.fn(), createLeave: vi.fn(), deleteLeave: vi.fn(), pending: vi.fn(), schedule: vi.fn(), confirm: vi.fn(), reject: vi.fn(), complete: vi.fn(), noShow: vi.fn(), note: vi.fn(), saveNote: vi.fn(), history: vi.fn() }))

vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../services/doctorApi', () => ({ doctorApi: () => api }))

const route = (element, url = '/', path = '*') => render(<MemoryRouter initialEntries={[url]}><Routes><Route path={path} element={element} /></Routes></MemoryRouter>)
const appointment = (overrides = {}) => ({ id: 'a1', patient_profile_id: 'p1', start_at: '2035-01-01T09:00:00Z', end_at: '2035-01-01T09:30:00Z', status: 'pending', profiles: { full_name: 'Morgan Lee' }, ...overrides })

beforeEach(() => { vi.clearAllMocks(); auth.profile = { role: 'doctor' }; auth.loading = false; auth.error = null })

test('allows an authenticated doctor through the existing doctor role guard', () => {
  route(<RequireAuth roles={['doctor']}><p>Doctor workspace</p></RequireAuth>, '/doctor', '/doctor')
  expect(screen.getByText('Doctor workspace')).toBeInTheDocument()
})

test('dashboard renders today schedule, pending count, navigation, and an empty schedule state', async () => {
  const today = new Date().toISOString().slice(0, 10)
  api.schedule.mockResolvedValue([appointment({ start_at: `${today}T09:00:00Z`, status: 'confirmed' })])
  api.pending.mockResolvedValue([])
  route(<DoctorDashboard />)
  expect(await screen.findByText('Morgan Lee')).toBeInTheDocument()
  expect(screen.getByText(/2:00 PM/)).toBeInTheDocument()
  expect(screen.getByText('Confirmed today')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Manage availability' })).toBeInTheDocument()

  api.schedule.mockResolvedValue([]); api.pending.mockResolvedValue([])
  route(<DoctorDashboard />)
  expect(await screen.findByText('No appointments are scheduled for today.')).toBeInTheDocument()
})

test('pending requests render patient and allow confirm with server refresh and duplicate prevention', async () => {
  let resolveConfirm
  api.pending.mockResolvedValue([appointment()]).mockResolvedValueOnce([appointment()]).mockResolvedValueOnce([])
  api.confirm.mockImplementation(() => new Promise(resolve => { resolveConfirm = resolve }))
  route(<PendingRequests />)
  expect(await screen.findByText('Morgan Lee')).toBeInTheDocument()
  expect(screen.getByText('Pending')).toBeInTheDocument()
  const confirm = screen.getByRole('button', { name: 'Confirm' })
  fireEvent.click(confirm)
  expect(screen.getByRole('button', { name: 'Please wait…' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Please wait…' }))
  expect(api.confirm).toHaveBeenCalledTimes(1)
  resolveConfirm({ status: 'confirmed' })
  expect(await screen.findByText('Appointment confirmed.')).toBeInTheDocument()
  await waitFor(() => expect(api.pending).toHaveBeenCalledTimes(2))
})

test('reject requires a reason, handles backend error, then refreshes after success', async () => {
  api.pending.mockResolvedValue([appointment()]).mockResolvedValueOnce([appointment()]).mockResolvedValueOnce([])
  route(<PendingRequests />)
  fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))
  expect(await screen.findByText('A rejection reason is required.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Reason for rejection'), { target: { value: 'Unavailable clinic session.' } })
  api.reject.mockRejectedValue(new Error('API request failed with status 409'))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))
  expect(await screen.findByText('API request failed with status 409')).toBeInTheDocument()
  expect(api.reject).toHaveBeenCalledWith('a1', 'Unavailable clinic session.')
  api.reject.mockResolvedValue({ status: 'rejected' })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))
  expect(await screen.findByText('Appointment rejected.')).toBeInTheDocument()
  await waitFor(() => expect(api.pending).toHaveBeenCalledTimes(2))
})

test('schedule renders representative statuses, applies filters, and completes with refreshed server data', async () => {
  const confirmed = appointment({ status: 'confirmed' })
  api.schedule.mockResolvedValueOnce([confirmed, appointment({ id: 'a2', status: 'cancelled', profiles: { full_name: 'Casey Ray' } })]).mockResolvedValueOnce([confirmed]).mockResolvedValueOnce([appointment({ status: 'completed', profiles: { full_name: 'Morgan Lee' } })])
  api.complete.mockResolvedValue({ status: 'completed' })
  route(<DoctorSchedule />)
  expect(await screen.findByText('Morgan Lee')).toBeInTheDocument()
  expect(screen.getByText('Casey Ray')).toBeInTheDocument()
  expect(screen.getByText('Cancelled')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'confirmed' } })
  fireEvent.click(screen.getByText('Apply filters'))
  await waitFor(() => expect(api.schedule).toHaveBeenLastCalledWith({ date: '', status: 'confirmed' }))
  fireEvent.click(screen.getByRole('button', { name: 'Mark completed' }))
  await waitFor(() => expect(api.complete).toHaveBeenCalledWith('a1'))
  expect(await screen.findByText('Appointment marked completed.')).toBeInTheDocument()
})

test('schedule shows backend early-completion rejection without false completion feedback', async () => {
  api.schedule.mockResolvedValue([appointment({ status: 'confirmed' })])
  api.complete.mockRejectedValue(new Error('Visit cannot be finalized before it starts.'))
  route(<DoctorSchedule />)
  fireEvent.click(await screen.findByRole('button', { name: 'Mark completed' }))
  expect(await screen.findByText('Visit cannot be finalized before it starts.')).toBeInTheDocument()
  expect(screen.queryByText('Appointment marked completed.')).not.toBeInTheDocument()
})

test('schedule marks an eligible appointment no-show and refreshes from the server', async () => {
  api.schedule.mockResolvedValueOnce([appointment({ status: 'confirmed' })]).mockResolvedValueOnce([appointment({ status: 'no_show' })])
  api.noShow.mockResolvedValue({ status: 'no_show' })
  route(<DoctorSchedule />)
  fireEvent.click(await screen.findByRole('button', { name: 'Mark no-show' }))
  await waitFor(() => expect(api.noShow).toHaveBeenCalledWith('a1'))
  expect(await screen.findByText('Appointment marked no-show.')).toBeInTheDocument()
  expect(await screen.findByText('No-show')).toBeInTheDocument()
})

test('availability creates an interval and refreshes the server-confirmed list', async () => {
  api.availability.mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: 'v1', day_of_week: 0, start_time: '09:00:00', end_time: '17:00:00' }])
  api.createAvailability.mockResolvedValue({ id: 'v1' })
  route(<AvailabilityManagement />)
  await screen.findByText('No availability has been set.')
  fireEvent.click(screen.getByRole('button', { name: 'Add availability' }))
  await waitFor(() => expect(api.createAvailability).toHaveBeenCalledWith({ day_of_week: 0, start_time: '09:00', end_time: '17:00' }))
  expect(await screen.findByText('Availability added.')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Monday' })).toBeInTheDocument()
})

test('availability edits and deletes only after server calls then refreshes', async () => {
  const item = { id: 'v1', day_of_week: 1, start_time: '09:00:00', end_time: '17:00:00' }
  api.availability.mockResolvedValue([item]); api.updateAvailability.mockResolvedValue({}); api.deleteAvailability.mockResolvedValue(null)
  route(<AvailabilityManagement />)
  expect(await screen.findByRole('heading', { name: 'Tuesday' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: '16:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  await waitFor(() => expect(api.updateAvailability).toHaveBeenCalledWith('v1', { day_of_week: 1, start_time: '09:00', end_time: '16:00' }))
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(api.deleteAvailability).toHaveBeenCalledWith('v1'))
  expect(api.availability).toHaveBeenCalledTimes(3)
})

test('availability displays backend overlap validation errors', async () => {
  api.availability.mockResolvedValue([]); api.createAvailability.mockRejectedValue(new Error('Availability overlaps an existing interval.'))
  route(<AvailabilityManagement />)
  await screen.findByText('No availability has been set.')
  fireEvent.click(screen.getByRole('button', { name: 'Add availability' }))
  expect(await screen.findByText('Availability overlaps an existing interval.')).toBeInTheDocument()
})

test('leave management renders warning, creates and deletes leave, and refreshes', async () => {
  const leave = { id: 'l1', leave_date: '2035-02-01', reason: 'Conference' }
  api.leaves.mockResolvedValue([leave]); api.createLeave.mockResolvedValue(leave); api.deleteLeave.mockResolvedValue(null)
  route(<LeaveManagement />)
  expect(await screen.findByText('Adding leave may automatically cancel affected Pending and Confirmed appointments. The clinic will process those changes securely.')).toBeInTheDocument()
  expect(screen.getByText('2035-02-01')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Leave date'), { target: { value: '2035-03-01' } })
  fireEvent.change(screen.getByLabelText('Reason (optional)'), { target: { value: 'Annual leave' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add leave' }))
  await waitFor(() => expect(api.createLeave).toHaveBeenCalledWith({ leave_date: '2035-03-01', reason: 'Annual leave' }))
  expect(await screen.findByText(/Leave saved/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove leave' }))
  await waitFor(() => expect(api.deleteLeave).toHaveBeenCalledWith('l1'))
})

test('leave management displays backend rejection instead of false success', async () => {
  api.leaves.mockResolvedValue([]); api.createLeave.mockRejectedValue(new Error('Leave date must be in the future.'))
  route(<LeaveManagement />)
  await screen.findByText('No future leave is recorded.')
  fireEvent.change(screen.getByLabelText('Leave date'), { target: { value: '2035-03-01' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add leave' }))
  expect(await screen.findByText('Leave date must be in the future.')).toBeInTheDocument()
  expect(screen.queryByText(/Leave saved/)).not.toBeInTheDocument()
})

test('appointment detail reads an authorized note and doctor-authorized history', async () => {
  api.schedule.mockResolvedValue([appointment({ status: 'completed' })]); api.note.mockResolvedValue({ note_text: 'Review completed.' }); api.history.mockResolvedValue([{ id: 'h1', start_at: '2034-12-01T09:00:00Z', status: 'completed', visit_notes: [{ note_text: 'Prior authorized note.' }] }])
  route(<DoctorAppointmentDetail />, '/doctor/appointments/a1', '/doctor/appointments/:appointmentId')
  expect(await screen.findByText('Review completed.')).toBeInTheDocument()
  expect(screen.getByText('Prior authorized note.')).toBeInTheDocument()
  expect(api.history).toHaveBeenCalledWith('p1')
})

test('appointment detail supports no-note save', async () => {
  api.schedule.mockResolvedValue([appointment({ status: 'completed' })]); api.note.mockRejectedValue(new Error('Visit note not found.')); api.history.mockResolvedValue([]); api.saveNote.mockResolvedValue({})
  route(<DoctorAppointmentDetail />, '/doctor/appointments/a1', '/doctor/appointments/:appointmentId')
  expect(await screen.findByText('No visit note has been recorded yet.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Clinical note'), { target: { value: 'Secure follow-up note.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }))
  await waitFor(() => expect(api.saveNote).toHaveBeenCalledWith('a1', 'Secure follow-up note.'))
  expect(await screen.findByText('Visit note saved securely.')).toBeInTheDocument()
})
