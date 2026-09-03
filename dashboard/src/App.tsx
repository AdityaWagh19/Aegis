import { Navigate, Route, Routes } from 'react-router-dom';
import Landing from './pages/Landing';
import Docs from './pages/Docs';
import Login from './pages/Login';
import Dashboard from './pages/app/Dashboard';
import Batch from './pages/app/Batch';
import Audit from './pages/app/Audit';
import UPIPay from './pages/pay/UPIPay';

/**
 * Route table (design.md §5.2): public marketing + docs, demo-gated console.
 * AppShell performs its own auth check; unknown paths fall through to 404-free
 * landing redirect to keep the demo surface tight.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/docs" element={<Docs />} />
      <Route path="/login" element={<Login />} />
      <Route path="/pay/:mandate_id" element={<UPIPay />} />
      <Route path="/app" element={<Dashboard />} />
      <Route path="/app/batch" element={<Batch />} />
      <Route path="/app/audit" element={<Audit />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
