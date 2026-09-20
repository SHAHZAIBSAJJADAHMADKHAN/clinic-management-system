import { Link, Outlet, useLocation } from 'react-router-dom'

export function AppLayout() {
  const { pathname } = useLocation()

  if (pathname === '/') return <Outlet />

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/">ClinicCare</Link>
        <span className="phase-label">Phase 01 Foundation</span>
      </header>
      <main><Outlet /></main>
      <footer className="site-footer">A professional clinic management platform.</footer>
    </div>
  )
}
