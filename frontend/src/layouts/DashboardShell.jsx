import { Avatar } from '../components/ui'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
export function DashboardShell({ role = 'patient', title, children, navigation = [] }) {
  const { signOut } = useAuth()
  const navigate = useNavigate()
  const handleSignOut = async () => {
    await signOut()
    navigate('/sign-in', { replace: true })
  }
  return <div className="dashboard-shell"><aside className="sidebar"><a className="brand" href="/">ClinicCare</a><p>{role} workspace</p><nav>{navigation.map(item => <a href={item.href} key={item.label}>{item.label}</a>)}</nav></aside><header className="dashboard-header"><div><small>ClinicCare / {role}</small><h1>{title}</h1></div><div className="header-actions"><button aria-label="Notifications">◌</button><button type="button" onClick={handleSignOut}>Sign out</button><Avatar name={role} /></div></header><main className="dashboard-content">{children||<Outlet/>}</main></div>
}
