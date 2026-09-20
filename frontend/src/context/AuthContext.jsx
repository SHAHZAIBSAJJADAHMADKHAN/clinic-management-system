import { createContext, useContext, useEffect, useRef, useState } from 'react'

import { supabase } from '../services/supabase'
import { apiRequest } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const activeSessionToken = useRef(null)
  const authStateVersion = useRef(0)
  const loadedProfile = useRef(null)
  const profileLoads = useRef(new Map())
  const profileErrors = useRef(new Map())
  const [state, setState] = useState({
    loading: true,
    session: null,
    profile: null,
    error: null,
  })

  const load = async (session, version = authStateVersion.current) => {
    if (version !== authStateVersion.current) return null

    const sessionToken = session?.access_token ?? null
    activeSessionToken.current = sessionToken

    if (!session) {
      loadedProfile.current = null
      profileErrors.current.clear()
      setState({
        loading: false,
        session: null,
        profile: null,
        error: null,
      })
      return null
    }

    const existingLoad = profileLoads.current.get(sessionToken)
    if (existingLoad) return existingLoad

    const profileLoad = (async () => {
    profileErrors.current.delete(sessionToken)
    try {
      const profile = await apiRequest(
        '/auth/me',
        {},
        session.access_token
      )

      if (
        activeSessionToken.current === sessionToken
        && version === authStateVersion.current
      ) {
        loadedProfile.current = { sessionToken, profile }
        setState({
          loading: false,
          session,
          profile,
          error: null,
        })
      }

      return profile
    } catch (error) {
      profileErrors.current.set(sessionToken, error)
      if (
        activeSessionToken.current === sessionToken
        && version === authStateVersion.current
      ) {
        loadedProfile.current = null
        setState({
          loading: false,
          session,
          profile: null,
          error,
        })
      }

      return null
    } finally {
      if (profileLoads.current.get(sessionToken) === profileLoad) {
        profileLoads.current.delete(sessionToken)
      }
    }
    })()

    profileLoads.current.set(sessionToken, profileLoad)
    return profileLoad
  }

  const activateSession = (session) => {
    const sessionToken = session?.access_token ?? null
    if (activeSessionToken.current !== sessionToken) {
      authStateVersion.current += 1
    }
    return load(session, authStateVersion.current)
  }

  useEffect(() => {
    if (!supabase) {
      setState({
        loading: false,
        session: null,
        profile: null,
        error: null,
      })
      return
    }

    let active = true

    const initialAuthStateVersion = authStateVersion.current

    supabase.auth.getSession().then(({ data }) => {
      if (active && authStateVersion.current === initialAuthStateVersion) {
        load(data.session, initialAuthStateVersion)
      }
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_, session) => {
      if (active) {
        activateSession(session)
      }
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [])

  const signOut = async () => {
    try {
      if (!supabase) return

      const { error } = await supabase.auth.signOut()

      if (error) throw error
    } finally {
      await activateSession(null)
    }
  }

  const updatePassword = async (password) => {
    if (!supabase) {
      throw Error('Authentication is not configured.')
    }

    const { error } = await supabase.auth.updateUser({
      password,
    })

    if (error) throw error

    // A recovery link establishes a browser session before this page loads.
    // Resolve its profile here so the subsequent doctor-portal redirect cannot
    // race the auth-state listener's asynchronous /auth/me request.
    const {
      data: { session },
    } = await supabase.auth.getSession()

    if (!session) {
      throw Error('Your password was updated, but the setup session is no longer available. Please sign in.')
    }

    const profile = await activateSession(session)

    if (!profile) {
      throw profileErrors.current.get(session.access_token)
        || Error('Your password was updated, but your account could not be verified. Please sign in.')
    }

    return { session, profile }
  }

  const signIn = async (email, password) => {
    if (!supabase) {
      throw Error('Authentication is not configured.')
    }

    // Invalidate a delayed startup getSession() result before it can replace
    // the session established by this explicit sign-in operation.
    authStateVersion.current += 1

    const { data, error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) throw error

    // Supabase persists the authenticated session before this resolves. Read
    // that authoritative current session so a token refresh/auth event cannot
    // leave this request using an older token from the credential response.
    const { data: current } = await supabase.auth.getSession()
    const session = current.session ?? data.session
    const sessionToken = session?.access_token
    if (!sessionToken) {
      throw Error('Sign-in completed without an authenticated session.')
    }

    const cachedProfile = loadedProfile.current
    const profile = cachedProfile?.sessionToken === sessionToken
      ? cachedProfile.profile
      : await activateSession(session)

    if (!profile) {
      throw profileErrors.current.get(sessionToken)
        || Error('Unable to load your account profile.')
    }

    return {
      session,
      profile,
    }
  }

  const signUp = async (data) => {
    if (!supabase) {
      throw Error('Authentication is not configured.')
    }

    const { data: result, error } = await supabase.auth.signUp({
      email: data.email,
      password: data.password,
      options: {
        data: {
          full_name: data.fullName,
          phone: data.phone,
        },
      },
    })

    if (error) throw error

    if (result.session) {
      await activateSession(result.session)
    }

    return {
      session: result.session,
    }
  }

  const value = {
    ...state,
    signIn,
    signUp,
    signOut,
    updatePassword,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
