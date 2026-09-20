import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { DashboardShell } from './DashboardShell'

const auth = vi.hoisted(() => ({ signOut: vi.fn() }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }))

test('signs out and redirects to the public sign-in route', async () => {
  auth.signOut.mockResolvedValue(undefined)
  render(<MemoryRouter initialEntries={['/patient']}><Routes><Route path="/patient" element={<DashboardShell title="Patient workspace"><p>Patient content</p></DashboardShell>} /><Route path="/sign-in" element={<p>Sign in</p>} /></Routes></MemoryRouter>)

  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(auth.signOut).toHaveBeenCalledTimes(1)
  expect(await screen.findByText('Sign in')).toBeInTheDocument()
})
