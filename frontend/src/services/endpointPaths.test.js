import { expect, test, vi } from 'vitest'
import { adminApi } from './adminApi'
import { doctorApi } from './doctorApi'
import { patientApi } from './patientApi'

function expectRelativePaths(request) {
  expect(request.mock.calls.map(([path]) => path).every((path) => !path.startsWith('/api/v1/'))).toBe(true)
}

test('patient API passes only relative endpoint paths to the shared client', () => {
  const request = vi.fn(); const api = patientApi(request)
  api.doctors(); api.slots('doctor-id', '2030-01-02'); api.appointments(); api.detail('appointment-id')
  api.book({}); api.cancel('appointment-id'); api.reschedule('appointment-id', {}); api.note('appointment-id')
  expectRelativePaths(request)
})

test('doctor API passes only relative endpoint paths to the shared client', () => {
  const request = vi.fn(); const api = doctorApi(request)
  api.availability(); api.createAvailability({}); api.updateAvailability('availability-id', {}); api.deleteAvailability('availability-id')
  api.leaves(); api.createLeave({}); api.deleteLeave('leave-id'); api.pending(); api.schedule({ date: '2030-01-02', status: 'pending' })
  api.confirm('appointment-id'); api.reject('appointment-id', 'reason'); api.complete('appointment-id'); api.noShow('appointment-id')
  api.note('appointment-id'); api.saveNote('appointment-id', 'note'); api.history('patient-id')
  expectRelativePaths(request)
})

test('admin API passes only relative endpoint paths to the shared client', () => {
  const request = vi.fn(); const api = adminApi(request)
  api.dashboard(); api.doctors(); api.createDoctor({}); api.deactivateDoctor('doctor-id'); api.patients('Ada')
  api.appointments({ status: 'pending' }); api.cancelAppointment('appointment-id', 'reason')
  expectRelativePaths(request)
})
