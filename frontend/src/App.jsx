import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Login from './pages/Login.jsx'
import Shell from './components/Shell.jsx'
import EmployeePortal from './pages/EmployeePortal.jsx'
import ManagementPortal from './pages/ManagementPortal.jsx'
import CounselPortal from './pages/CounselPortal.jsx'
import ClientPortal from './pages/ClientPortal.jsx'
import TenantPortal from './pages/TenantPortal.jsx'
import AuditorPortal from './pages/AuditorPortal.jsx'
import AdminPortal from './pages/AdminPortal.jsx'

const PORTAL_COMPONENTS = {
  employee: EmployeePortal,
  management: ManagementPortal,
  counsel: CounselPortal,
  client: ClientPortal,
  tenant: TenantPortal,
  auditor: AuditorPortal,
  admin: AdminPortal,
}

function PortalRoute({ portal }) {
  const { user, checking } = useAuth()
  if (checking) return <div className="page-center">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.portal !== portal) {
    // Signed in, but not for this portal — bounce to their own portal.
    return <Navigate to={`/portal/${user.portal}`} replace />
  }
  const Page = PORTAL_COMPONENTS[portal]
  return (
    <Shell>
      <Page />
    </Shell>
  )
}

export default function App() {
  const { user, checking } = useAuth()
  return (
    <Routes>
      <Route path="/" element={
        checking ? <div className="page-center">Loading…</div>
          : user ? <Navigate to={`/portal/${user.portal}`} replace />
          : <Navigate to="/login" replace />
      } />
      <Route path="/login" element={<Login />} />
      {Object.keys(PORTAL_COMPONENTS).map((p) => (
        <Route key={p} path={`/portal/${p}`} element={<PortalRoute portal={p} />} />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}