import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, expect, test, vi } from 'vitest'

const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signOut: vi.fn(),
  signInWithPassword: vi.fn(),
  updateUser: vi.fn(),
  apiRequest: vi.fn(),
}))

vi.mock('../services/supabase', () => ({ supabase: { auth: { getSession: auth.getSession, onAuthStateChange: auth.onAuthStateChange, signOut: auth.signOut, signInWithPassword: auth.signInWithPassword, updateUser: auth.updateUser } } }))
vi.mock('../services/api', () => ({ apiRequest: auth.apiRequest }))

import { AuthProvider, useAuth } from './AuthContext'

function SessionProbe({ canSignOut = false, canSetPassword = false, canSignIn = false }) {
  const { loading, profile, signOut, signIn, updatePassword } = useAuth()
  const [signInError, setSignInError] = useState('')
  return <><p>{loading ? 'Loading' : profile?.role || 'Signed out'}</p>{signInError && <p role="alert">{signInError}</p>}{canSignOut && <button onClick={signOut}>Sign out</button>}{canSetPassword && <button onClick={() => updatePassword('new-password')}>Set password</button>}{canSignIn && <button onClick={() => signIn('admin@example.test', 'safe-password').catch(error => setSignInError(error.message))}>Sign in</button>}</>
}

beforeEach(() => {
  vi.clearAllMocks()
  auth.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
})

test('restores a Supabase session and resolves its profile with the session access token', async () => {
  const session = { access_token: 'restored-access-token' }
  auth.getSession.mockResolvedValue({ data: { session } })
  auth.apiRequest.mockResolvedValue({ role: 'patient' })

  render(<AuthProvider><SessionProbe /></AuthProvider>)

  expect(await screen.findByText('patient')).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledWith('/auth/me', {}, 'restored-access-token')
})

test('clears local session and profile after Supabase sign-out', async () => {
  const session = { access_token: 'restored-access-token' }
  auth.getSession.mockResolvedValue({ data: { session } })
  auth.apiRequest.mockResolvedValue({ role: 'patient' })
  auth.signOut.mockResolvedValue({ error: null })

  render(<AuthProvider><SessionProbe canSignOut /></AuthProvider>)
  await screen.findByText('patient')
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

  await waitFor(() => expect(auth.signOut).toHaveBeenCalledTimes(1))
  expect(await screen.findByText('Signed out')).toBeInTheDocument()
})

test('loads the recovery session profile before completing a password update', async () => {
  const recoverySession = { access_token: 'recovery-access-token' }
  auth.getSession
    .mockResolvedValueOnce({ data: { session: null } })
    .mockResolvedValueOnce({ data: { session: recoverySession } })
  auth.updateUser.mockResolvedValue({ error: null })
  auth.apiRequest.mockResolvedValue({ role: 'doctor' })

  render(<AuthProvider><SessionProbe canSetPassword /></AuthProvider>)
  await screen.findByText('Signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Set password' }))

  await waitFor(() => expect(auth.updateUser).toHaveBeenCalledWith({ password: 'new-password' }))
  expect(await screen.findByText('doctor')).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledWith('/auth/me', {}, 'recovery-access-token')
})

test.each(['patient', 'doctor', 'admin'])('loads and retains a %s profile from one normal sign-in request', async role => {
  const session = { access_token: `${role}-access-token` }
  let authStateCallback
  auth.getSession.mockResolvedValue({ data: { session: null } })
  auth.onAuthStateChange.mockImplementation(callback => {
    authStateCallback = callback
    return { data: { subscription: { unsubscribe: vi.fn() } } }
  })
  auth.signInWithPassword.mockImplementation(async () => {
    authStateCallback('SIGNED_IN', session)
    return { data: { session }, error: null }
  })
  auth.getSession.mockResolvedValueOnce({ data: { session: null } }).mockResolvedValueOnce({ data: { session } })
  auth.apiRequest.mockResolvedValue({ role })

  render(<AuthProvider><SessionProbe canSignIn /></AuthProvider>)
  await screen.findByText('Signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByText(role)).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledTimes(1)
  expect(auth.apiRequest).toHaveBeenCalledWith('/auth/me', {}, `${role}-access-token`)
})

test('ignores a delayed previous-session snapshot while a new sign-in resolves', async () => {
  const previousSession = { access_token: 'previous-access-token' }
  const newSession = { access_token: 'new-access-token' }
  let resolveInitialSession
  auth.getSession
    .mockReturnValueOnce(new Promise(resolve => { resolveInitialSession = resolve }))
    .mockResolvedValueOnce({ data: { session: newSession } })
  auth.signInWithPassword.mockResolvedValue({ data: { session: newSession }, error: null })
  auth.apiRequest.mockResolvedValue({ role: 'doctor' })

  render(<AuthProvider><SessionProbe canSignIn /></AuthProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await act(async () => { resolveInitialSession({ data: { session: previousSession } }) })

  expect(await screen.findByText('doctor')).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledTimes(1)
  expect(auth.apiRequest).toHaveBeenCalledWith('/auth/me', {}, 'new-access-token')
})

test('uses the current Supabase session token rather than an older sign-in response token', async () => {
  const responseSession = { access_token: 'response-access-token' }
  const currentSession = { access_token: 'current-access-token' }
  auth.getSession
    .mockResolvedValueOnce({ data: { session: null } })
    .mockResolvedValueOnce({ data: { session: currentSession } })
  auth.signInWithPassword.mockResolvedValue({ data: { session: responseSession }, error: null })
  auth.apiRequest.mockResolvedValue({ role: 'admin' })

  render(<AuthProvider><SessionProbe canSignIn /></AuthProvider>)
  await screen.findByText('Signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByText('admin')).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledWith('/auth/me', {}, 'current-access-token')
})

test('surfaces the useful profile API failure from a normal sign-in', async () => {
  const session = { access_token: 'current-access-token' }
  auth.getSession
    .mockResolvedValueOnce({ data: { session: null } })
    .mockResolvedValueOnce({ data: { session } })
  auth.signInWithPassword.mockResolvedValue({ data: { session }, error: null })
  auth.apiRequest.mockRejectedValue(Object.assign(new Error('Invalid or expired bearer token.'), { status: 401 }))

  render(<AuthProvider><SessionProbe canSignIn /></AuthProvider>)
  await screen.findByText('Signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or expired bearer token.')
  expect(screen.queryByText('Unable to load your account profile.')).not.toBeInTheDocument()
})

test('preserves invalid credential errors without requesting a profile', async () => {
  auth.getSession.mockResolvedValue({ data: { session: null } })
  auth.signInWithPassword.mockResolvedValue({ data: { session: null }, error: new Error('Invalid login credentials') })

  render(<AuthProvider><SessionProbe canSignIn /></AuthProvider>)
  await screen.findByText('Signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid login credentials')
  expect(auth.apiRequest).not.toHaveBeenCalled()
})

test('does not let a completed stale profile request overwrite a signed-out state', async () => {
  const session = { access_token: 'stale-access-token' }
  let authStateCallback
  let resolveProfile
  auth.getSession.mockResolvedValue({ data: { session: null } })
  auth.onAuthStateChange.mockImplementation(callback => {
    authStateCallback = callback
    return { data: { subscription: { unsubscribe: vi.fn() } } }
  })
  auth.apiRequest.mockReturnValue(new Promise(resolve => { resolveProfile = resolve }))

  render(<AuthProvider><SessionProbe /></AuthProvider>)
  await screen.findByText('Signed out')
  await act(async () => { authStateCallback('SIGNED_IN', session) })
  await waitFor(() => expect(auth.apiRequest).toHaveBeenCalledTimes(1))
  await act(async () => { authStateCallback('SIGNED_OUT', null) })
  expect(await screen.findByText('Signed out')).toBeInTheDocument()
  await act(async () => { resolveProfile({ role: 'admin' }) })
  await waitFor(() => expect(screen.getByText('Signed out')).toBeInTheDocument())
})

test('does not let a delayed initial session check clear a newer admin session', async () => {
  const session = { access_token: 'admin-access-token' }
  let authStateCallback
  let resolveInitialSession
  auth.getSession.mockReturnValue(new Promise(resolve => { resolveInitialSession = resolve }))
  auth.onAuthStateChange.mockImplementation(callback => {
    authStateCallback = callback
    return { data: { subscription: { unsubscribe: vi.fn() } } }
  })
  auth.apiRequest.mockResolvedValue({ role: 'admin' })

  render(<AuthProvider><SessionProbe /></AuthProvider>)
  await act(async () => { authStateCallback('SIGNED_IN', session) })
  expect(await screen.findByText('admin')).toBeInTheDocument()
  await act(async () => { resolveInitialSession({ data: { session: null } }) })

  expect(await screen.findByText('admin')).toBeInTheDocument()
  expect(auth.apiRequest).toHaveBeenCalledTimes(1)
})
