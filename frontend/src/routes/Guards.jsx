import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LoadingState, ErrorState } from '../components/ui'
export function RequireAuth({ roles, children }) { const {loading,profile,error}=useAuth();const location=useLocation();if(loading)return <LoadingState/>;if(error)return <ErrorState>Unable to verify your account.</ErrorState>;if(!profile)return <Navigate to="/sign-in" state={{from:location}} replace/>;if(roles&&!roles.includes(profile.role))return <Navigate to="/unauthorized" replace/>;return children }
