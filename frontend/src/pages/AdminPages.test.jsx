import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { RequireAuth } from '../routes/Guards'
import { AdminAppointments, AdminDashboard, AdminDoctors, AdminPatients } from './AdminPages'

const auth = vi.hoisted(() => ({ session: { access_token: 'test-token' }, loading: false, error: null, profile: { role: 'admin' } }))
const api = vi.hoisted(() => ({ dashboard: vi.fn(), doctors: vi.fn(), createDoctor: vi.fn(), deactivateDoctor: vi.fn(), patients: vi.fn(), appointments: vi.fn(), cancelAppointment: vi.fn() }))

vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../services/adminApi', () => ({ adminApi: () => api }))

const route = (element, url = '/', path = '*') => render(<MemoryRouter initialEntries={[url]}><Routes><Route path={path} element={element} /><Route path="/unauthorized" element={<p>Access restricted</p>} /></Routes></MemoryRouter>)
const doctor = (overrides = {}) => ({ id: 'd1', specialty: 'Cardiology', is_active: true, profiles: { full_name: 'Dr. Rowan', email: 'rowan@example.test', phone: '555-0123' }, ...overrides })
const appointment = (overrides = {}) => ({ id: 'a1', doctor_id: 'd1', patient_profile_id: 'p1', start_at: '2035-01-01T09:00:00Z', status: 'pending', profiles: { full_name: 'Morgan Lee' }, doctors: { profiles: { full_name: 'Dr. Rowan' } }, ...overrides })

beforeEach(() => { vi.clearAllMocks(); auth.loading = false; auth.error = null; auth.profile = { role: 'admin' } })

test('admin role guard allows administrators and redirects patient and doctor roles', () => {
  route(<RequireAuth roles={['admin']}><p>Admin workspace</p></RequireAuth>, '/admin', '/admin')
  expect(screen.getByText('Admin workspace')).toBeInTheDocument()
  auth.profile = { role: 'patient' }
  route(<RequireAuth roles={['admin']}><p>Admin workspace</p></RequireAuth>, '/admin', '/admin')
  expect(screen.getByText('Access restricted')).toBeInTheDocument()
  auth.profile = { role: 'doctor' }
  route(<RequireAuth roles={['admin']}><p>Admin workspace</p></RequireAuth>, '/admin', '/admin')
  expect(screen.getAllByText('Access restricted')).toHaveLength(2)
})

test('dashboard renders today appointments, all required status counts, and per-doctor counts', async () => {
  const counts = { pending: 1, confirmed: 1, completed: 1, no_show: 1, cancelled: 1 }
  api.dashboard.mockResolvedValue({ date: '2035-01-01', today_appointments: ['pending', 'confirmed', 'completed', 'no_show', 'cancelled'].map((status, index) => appointment({ id: `a${index}`, status })), per_doctor_counts: { d1: counts } })
  route(<AdminDashboard />)
  expect((await screen.findAllByText('Morgan Lee')).length).toBe(5)
  expect(screen.getAllByText(/2:00 PM/).length).toBeGreaterThan(0)
  for (const label of ['Pending', 'Confirmed', 'Completed', 'No-show', 'Cancelled']) expect(screen.getAllByText(label).length).toBeGreaterThan(0)
  expect(screen.getByRole('heading', { name: 'Dr. Rowan' })).toBeInTheDocument()
  expect(screen.getAllByText('pending').length).toBeGreaterThan(0)
})

test('dashboard handles a zero-appointment response', async () => {
  api.dashboard.mockResolvedValue({ date: '2035-01-01', today_appointments: [], per_doctor_counts: {} })
  route(<AdminDashboard />)
  expect(await screen.findByText('No appointments are scheduled for today.')).toBeInTheDocument()
  expect(screen.getByText('No per-doctor counts are available for today.')).toBeInTheDocument()
})

test('doctor list renders supported details and active/inactive actions', async () => {
  api.doctors.mockResolvedValue([doctor(), doctor({ id: 'd2', is_active: false, profiles: { full_name: 'Dr. Avery', email: 'avery@example.test' } })])
  route(<AdminDoctors />)
  expect(await screen.findByText('Dr. Rowan')).toBeInTheDocument()
  expect(screen.getAllByText('Cardiology')).toHaveLength(2)
  expect(screen.getByText('Inactive')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument()
})

test('doctor creation uses the FastAPI abstraction, prevents duplicates, and refreshes the list', async () => {
  let resolveCreate
  api.doctors.mockResolvedValueOnce([]).mockResolvedValueOnce([doctor()])
  api.createDoctor.mockImplementation(() => new Promise(resolve => { resolveCreate = resolve }))
  route(<AdminDoctors />)
  await screen.findByText('No doctors have been added yet.')
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Dr. Rowan' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'rowan@example.test' } })
  fireEvent.change(screen.getByLabelText('Specialty'), { target: { value: 'Cardiology' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create doctor' }))
  expect(screen.getByRole('button', { name: 'Please wait…' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Please wait…' }))
  expect(api.createDoctor).toHaveBeenCalledTimes(1)
  expect(api.createDoctor).toHaveBeenCalledWith({ full_name: 'Dr. Rowan', email: 'rowan@example.test', specialty: 'Cardiology', phone: null })
  resolveCreate({ id: 'd1' })
  expect(await screen.findByText(/secure invitation and password-setup process has been queued/i)).toBeInTheDocument()
  expect(await screen.findByText('Dr. Rowan')).toBeInTheDocument()
  expect(api.doctors).toHaveBeenCalledTimes(2)
})

test('doctor creation displays backend errors without false success', async () => {
  api.doctors.mockResolvedValue([]); api.createDoctor.mockRejectedValue(new Error('API request failed with status 409'))
  route(<AdminDoctors />)
  await screen.findByText('No doctors have been added yet.')
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Dr. Duplicate' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'duplicate@example.test' } })
  fireEvent.change(screen.getByLabelText('Specialty'), { target: { value: 'Cardiology' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create doctor' }))
  expect(await screen.findByText('API request failed with status 409')).toBeInTheDocument()
  expect(screen.queryByText(/secure invitation and password-setup process has been queued/i)).not.toBeInTheDocument()
})

test('doctor deactivation requires confirmation, prevents duplicates, and refreshes inactive state', async () => {
  let resolveDeactivate
  api.doctors.mockResolvedValueOnce([doctor()]).mockResolvedValueOnce([doctor({ is_active: false })])
  api.deactivateDoctor.mockImplementation(() => new Promise(resolve => { resolveDeactivate = resolve }))
  route(<AdminDoctors />)
  fireEvent.click(await screen.findByRole('button', { name: 'Deactivate' }))
  const dialog = screen.getByRole('dialog', { name: 'Deactivate doctor' })
  expect(dialog).toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Deactivate doctor' }))
  expect(within(dialog).getByRole('button', { name: 'Please wait…' })).toBeDisabled()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Please wait…' }))
  expect(api.deactivateDoctor).toHaveBeenCalledTimes(1)
  resolveDeactivate({})
  expect(await screen.findByText('Dr. Rowan is now inactive.')).toBeInTheDocument()
  expect(await screen.findByText('Inactive')).toBeInTheDocument()
})

test('patient list renders only safe fields and server-side search refreshes with no-results state', async () => {
  api.patients.mockResolvedValueOnce([{ id: 'p1', full_name: 'Morgan Lee', email: 'morgan@example.test', phone: '555-0199', is_active: true }]).mockResolvedValueOnce([])
  route(<AdminPatients />)
  expect(await screen.findByText('Morgan Lee')).toBeInTheDocument()
  expect(screen.getByText('morgan@example.test')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Search name, email, or phone'), { target: { value: 'Morgan' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
  await waitFor(() => expect(api.patients).toHaveBeenLastCalledWith('Morgan'))
  expect(await screen.findByText('No patients match this search.')).toBeInTheDocument()
})

test('appointment list filters doctor, date, and status through the Admin API', async () => {
  api.appointments.mockResolvedValue([appointment()]); api.doctors.mockResolvedValue([doctor()])
  route(<AdminAppointments />)
  expect(await screen.findByText('Morgan Lee')).toBeInTheDocument()
  expect(screen.getByText('Dr. Rowan')).toBeInTheDocument()
  expect(screen.getByText('Pending')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Doctor'), { target: { value: 'd1' } })
  fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2035-01-01' } })
  fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'confirmed' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }))
  await waitFor(() => expect(api.appointments).toHaveBeenLastCalledWith({ doctorId: 'd1', date: '2035-01-01', status: 'confirmed' }))
})

test('admin cancellation requires confirmation, prevents duplicates, and shows refreshed cancelled result', async () => {
  let resolveCancel
  api.appointments.mockResolvedValueOnce([appointment()]).mockResolvedValueOnce([appointment({ status: 'cancelled' })]); api.doctors.mockResolvedValue([doctor()]); api.cancelAppointment.mockImplementation(() => new Promise(resolve => { resolveCancel = resolve }))
  route(<AdminAppointments />)
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel appointment' }))
  const dialog = screen.getByRole('dialog', { name: 'Cancel appointment' })
  expect(dialog).toBeInTheDocument()
  fireEvent.change(within(dialog).getByLabelText('Cancellation reason (optional)'), { target: { value: 'Clinic closure' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm cancellation' }))
  expect(within(dialog).getByRole('button', { name: 'Please wait…' })).toBeDisabled()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Please wait…' }))
  expect(api.cancelAppointment).toHaveBeenCalledTimes(1)
  expect(api.cancelAppointment).toHaveBeenCalledWith('a1', 'Clinic closure')
  resolveCancel({ status: 'cancelled' })
  expect(await screen.findByText(/Appointment cancelled. The server-confirmed schedule has been refreshed/i)).toBeInTheDocument()
  expect(await screen.findByText('Cancelled')).toBeInTheDocument()
})

test('admin cancellation surfaces backend errors without false cancelled feedback', async () => {
  api.appointments.mockResolvedValue([appointment()]); api.doctors.mockResolvedValue([doctor()]); api.cancelAppointment.mockRejectedValue(new Error('Appointment cannot be cancelled in its current state.'))
  route(<AdminAppointments />)
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel appointment' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm cancellation' }))
  expect(await screen.findByText('Appointment cannot be cancelled in its current state.')).toBeInTheDocument()
  expect(screen.queryByText(/server-confirmed schedule has been refreshed/i)).not.toBeInTheDocument()
})

test('admin appointment and patient screens never render defensive visit-note fields or private-history actions', async () => {
  api.appointments.mockResolvedValue([{ ...appointment(), visit_note: 'PRIVATE NOTE — DO NOT SHOW', visit_notes: [{ note_text: 'PRIVATE NOTE — DO NOT SHOW' }] }]); api.doctors.mockResolvedValue([doctor()])
  route(<AdminAppointments />)
  await screen.findByText('Morgan Lee')
  expect(screen.queryByText('PRIVATE NOTE — DO NOT SHOW')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /visit note|history/i })).not.toBeInTheDocument()
})
