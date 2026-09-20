import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '../context/AuthContext'
import { SetPasswordPage, SignInPage, SignUpPage } from './AuthPages'

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }))

function renderSignUp() {
  return render(<MemoryRouter initialEntries={['/sign-up']}><Routes><Route path="/sign-up" element={<SignUpPage />} /><Route path="/patient" element={<p>Patient portal</p>} /><Route path="/sign-in" element={<p>Sign in page</p>} /></Routes></MemoryRouter>)
}

function renderSignIn() {
  return render(<MemoryRouter initialEntries={['/sign-in']}><Routes><Route path="/sign-in" element={<SignInPage />} /><Route path="/patient" element={<p>Patient portal</p>} /><Route path="/doctor" element={<p>Doctor portal</p>} /><Route path="/admin" element={<p>Admin portal</p>} /></Routes></MemoryRouter>)
}

function renderSetPassword() {
  return render(<MemoryRouter initialEntries={['/set-password']}><Routes><Route path="/set-password" element={<SetPasswordPage />} /><Route path="/doctor" element={<p>Doctor portal</p>} /></Routes></MemoryRouter>)
}

function submitSignIn() {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'safe-password' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Sign in' }).closest('form'))
}

function submitForm() {
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Test Patient' } })
  fireEvent.change(screen.getByLabelText('Phone'), { target: { value: '03001234567' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'patient@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'safe-password' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form'))
}

describe('SignUpPage', () => {
  beforeEach(() => vi.mocked(useAuth).mockReset())

  it('redirects a successful session-backed signup to the patient portal', async () => {
    const signUp = vi.fn().mockResolvedValue({ session: { access_token: 'test-session' } })
    vi.mocked(useAuth).mockReturnValue({ signUp })
    renderSignUp()

    submitForm()

    expect(await screen.findByText('Patient portal')).toBeInTheDocument()
    expect(signUp).toHaveBeenCalledWith({ fullName: 'Test Patient', phone: '03001234567', email: 'patient@example.test', password: 'safe-password' })
  })

  it('shows confirmation guidance when Supabase creates an account without a session', async () => {
    vi.mocked(useAuth).mockReturnValue({ signUp: vi.fn().mockResolvedValue({ session: null }) })
    renderSignUp()

    submitForm()

    expect(await screen.findByRole('status')).toHaveTextContent('Account created. Please check your email to confirm your account.')
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in')
    expect(screen.queryByText('Patient portal')).not.toBeInTheDocument()
  })

  it('shows the signup error and does not redirect', async () => {
    const signUp = vi.fn().mockRejectedValue({ message: 'Email address is already registered.' })
    vi.mocked(useAuth).mockReturnValue({ signUp })
    renderSignUp()

    submitForm()

    await waitFor(() => expect(signUp).toHaveBeenCalledTimes(1))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email address is already registered.')
    expect(screen.queryByText('Patient portal')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create account' })).not.toBeDisabled()
  })

  it('prevents duplicate submission and clears loading after completion', async () => {
    let resolveSignUp
    const signUp = vi.fn().mockImplementation(() => new Promise(resolve => { resolveSignUp = resolve }))
    vi.mocked(useAuth).mockReturnValue({ signUp })
    renderSignUp()

    submitForm()
    const button = screen.getByRole('button', { name: 'Please wait…' })
    expect(button).toBeDisabled()
    fireEvent.submit(button.closest('form'))
    expect(signUp).toHaveBeenCalledTimes(1)

    resolveSignUp({ session: null })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create account' })).not.toBeDisabled())
  })
})

describe('SignInPage', () => {
  beforeEach(() => vi.mocked(useAuth).mockReset())

  it.each([
    ['patient', 'Patient portal'],
    ['doctor', 'Doctor portal'],
    ['admin', 'Admin portal'],
  ])('redirects a %s using the profile returned by signIn', async (role, portal) => {
    const signIn = vi.fn().mockResolvedValue({ session: { access_token: 'test-session' }, profile: { role } })
    vi.mocked(useAuth).mockReturnValue({ signIn })
    renderSignIn()

    submitSignIn()

    expect(await screen.findByText(portal)).toBeInTheDocument()
    expect(signIn).toHaveBeenCalledWith('user@example.test', 'safe-password')
  })

  it('shows an accessible error and remains on sign-in for invalid credentials', async () => {
    vi.mocked(useAuth).mockReturnValue({ signIn: vi.fn().mockRejectedValue(new Error('Invalid login credentials')) })
    renderSignIn()

    submitSignIn()

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid login credentials')
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(screen.queryByText(/portal$/)).not.toBeInTheDocument()
  })
})

describe('SetPasswordPage', () => {
  beforeEach(() => vi.mocked(useAuth).mockReset())

  it('updates the password and redirects the recovered doctor session to its portal', async () => {
    const updatePassword = vi.fn().mockResolvedValue({ profile: { role: 'doctor' } })
    vi.mocked(useAuth).mockReturnValue({ updatePassword })
    renderSetPassword()

    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'safe-password' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'safe-password' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Set password' }).closest('form'))

    expect(await screen.findByRole('status')).toHaveTextContent('Your password has been set successfully.')
    expect(updatePassword).toHaveBeenCalledWith('safe-password')
    expect(await screen.findByText('Doctor portal', {}, { timeout: 1500 })).toBeInTheDocument()
  })
})
