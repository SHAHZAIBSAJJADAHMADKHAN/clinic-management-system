import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { RequireAuth } from './Guards'

const auth = vi.hoisted(() => ({ loading: false, error: null, profile: { role: 'patient' } }))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => auth,
}))

function protectedRoute(path, roles) {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path={path} element={<RequireAuth roles={roles}><p>Workspace</p></RequireAuth>} /><Route path="/sign-in" element={<p>Sign in</p>} /><Route path="/unauthorized" element={<p>Access restricted</p>} /></Routes></MemoryRouter>)
}

beforeEach(() => { auth.loading = false; auth.error = null; auth.profile = { role: 'patient' } })

test('allows an authenticated patient into a patient-protected route', () => {
  protectedRoute('/patient', ['patient'])
  expect(screen.getByText('Workspace')).toBeInTheDocument()
})

test.each(['/patient', '/doctor', '/admin'])('redirects an unauthenticated visitor from %s to sign-in', (path) => {
  auth.profile = null
  protectedRoute(path, [path.slice(1)])
  expect(screen.getByText('Sign in')).toBeInTheDocument()
  expect(screen.queryByText('Access restricted')).not.toBeInTheDocument()
})

test.each([
  ['patient', '/doctor', ['doctor']],
  ['patient', '/admin', ['admin']],
  ['doctor', '/patient', ['patient']],
  ['doctor', '/admin', ['admin']],
  ['admin', '/patient', ['patient']],
  ['admin', '/doctor', ['doctor']],
])('redirects authenticated %s users from %s to unauthorized', (role, path, roles) => {
  auth.profile = { role }
  protectedRoute(path, roles)
  expect(screen.getByText('Access restricted')).toBeInTheDocument()
})
