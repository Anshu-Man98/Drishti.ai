import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AppShell } from './components/layout/AppShell';
import { Dashboard } from './pages/Dashboard';
import { ClaimsList } from './pages/ClaimsList';
import { ClaimDetail } from './pages/ClaimDetail';
import { UploadClaim } from './pages/UploadClaim';
import { RouteSkeleton } from './components/common/RouteSkeleton';

// Lazy-load heavier routes to reduce initial bundle size (C4)
const NetworkGraph = React.lazy(() =>
  import('./pages/NetworkGraph').then((m) => ({ default: m.NetworkGraph }))
);
const DuelArena = React.lazy(() =>
  import('./pages/DuelArena').then((m) => ({ default: m.DuelArena }))
);

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppShell>
          <Suspense fallback={<RouteSkeleton />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/claims" element={<ClaimsList />} />
              <Route path="/claims/:id" element={<ClaimDetail />} />
              <Route path="/upload" element={<UploadClaim />} />
              <Route path="/network" element={<NetworkGraph />} />
              <Route path="/duel" element={<DuelArena />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AppShell>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
