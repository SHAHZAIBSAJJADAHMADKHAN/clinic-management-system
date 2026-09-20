import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AuthShell } from '../layouts/AuthShell'
import { Button, Input, ErrorState } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export function SignInPage() {
  const { signIn } = useAuth()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  const submit = async (e) => {
    e.preventDefault()

    if (busy) return

    const values = new FormData(e.currentTarget)

    setError('')
    setBusy(true)

    try {
      const { profile } = await signIn(
        values.get('email'),
        values.get('password')
      )

      const destination = {
        patient: '/patient',
        doctor: '/doctor',
        admin: '/admin',
      }[profile.role]

      if (!destination) {
        throw Error('Your account role is not authorized.')
      }

      nav(destination, { replace: true })
    } catch (failure) {
      setError(failure?.message || 'Unable to sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Welcome back">
      <form onSubmit={submit}>
        <Input
          id="email"
          name="email"
          label="Email"
          type="email"
          required
        />

        <Input
          id="password"
          name="password"
          label="Password"
          type="password"
          required
        />

        {error && <ErrorState>{error}</ErrorState>}

        <Button loading={busy}>Sign in</Button>

        <p>
          <Link to="/sign-up">Create a patient account</Link>
        </p>
      </form>
    </AuthShell>
  )
}

export function SignUpPage() {
  const { signUp } = useAuth()
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  const submit = async (e) => {
    e.preventDefault()

    if (busy) return

    const values = new FormData(e.currentTarget)

    setSuccess('')
    setBusy(true)

    try {
      const { session } = await signUp({
        fullName: values.get('fullName'),
        phone: values.get('phone'),
        email: values.get('email'),
        password: values.get('password'),
      })

      setError('')

      if (session) {
        nav('/patient', { replace: true })
      } else {
        setSuccess(
          'Account created. Please check your email to confirm your account.'
        )
      }
    } catch (failure) {
      setSuccess('')
      setError(failure?.message || 'Unable to create your account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create your patient account">
      <form onSubmit={submit}>
        <Input
          id="name"
          name="fullName"
          label="Full name"
          required
        />

        <Input
          id="phone"
          name="phone"
          label="Phone"
        />

        <Input
          id="email"
          name="email"
          label="Email"
          type="email"
          required
        />

        <Input
          id="password"
          name="password"
          label="Password"
          type="password"
          required
        />

        {error && <ErrorState>{error}</ErrorState>}

        {success && (
          <p role="status">
            {success}{' '}
            <Link to="/sign-in">Sign in</Link>
          </p>
        )}

        <Button loading={busy}>Create account</Button>
      </form>
    </AuthShell>
  )
}

export function SetPasswordPage() {
  const { updatePassword } = useAuth()
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  const submit = async (e) => {
    e.preventDefault()

    if (busy) return

    const values = new FormData(e.currentTarget)
    const password = values.get('password')
    const confirmPassword = values.get('confirmPassword')

    setError('')
    setSuccess('')

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (!password || password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setBusy(true)

    try {
      await updatePassword(password)

      setSuccess('Your password has been set successfully.')

      setTimeout(() => {
        nav('/doctor', { replace: true })
      }, 1000)
    } catch (failure) {
      setError(
        failure?.message ||
          'Unable to set your password. The setup link may be invalid or expired.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Set your password">
      <form onSubmit={submit}>
        <p>
          Create a secure password for your ClinicCare doctor account.
        </p>

        <Input
          id="password"
          name="password"
          label="New password"
          type="password"
          required
        />

        <Input
          id="confirmPassword"
          name="confirmPassword"
          label="Confirm password"
          type="password"
          required
        />

        {error && <ErrorState>{error}</ErrorState>}

        {success && <p role="status">{success}</p>}

        <Button loading={busy}>Set password</Button>
      </form>
    </AuthShell>
  )
}