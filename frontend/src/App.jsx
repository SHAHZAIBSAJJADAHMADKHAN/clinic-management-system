import { BrowserRouter } from 'react-router-dom'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { AppRoutes } from './routes/AppRoutes'
import { AuthProvider } from './context/AuthContext'

export function App() {
  return (
    <AppErrorBoundary>
      <AuthProvider><BrowserRouter><AppRoutes /></BrowserRouter></AuthProvider>
    </AppErrorBoundary>
  )
}
