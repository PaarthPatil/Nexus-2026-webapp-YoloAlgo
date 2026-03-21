import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { SessionProvider } from './context/SessionContext';
import { AppLayout } from './components/layout/AppLayout';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { SessionSetup } from './pages/SessionSetup';
import { History } from './pages/History';
import { Settings } from './pages/Settings';

function ProtectedRoute({ children }) {
  const { currentUser, authLoading } = useAuth();
  
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0b1220] flex items-center justify-center">
        <div className="animate-pulse rounded-lg border border-slate-800 bg-slate-900/80 px-6 py-4 flex items-center gap-3 shadow-2xl">
          <div className="h-4 w-4 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
          <span className="text-sm font-medium text-slate-300 tracking-wide">Initializing Core...</span>
        </div>
      </div>
    );
  }
  
  if (!currentUser) {
    return <Login />;
  }
  
  return children;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ProtectedRoute>
          <SessionProvider>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="setup" element={<SessionSetup />} />
                <Route path="history" element={<History />} />
                <Route path="settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </SessionProvider>
        </ProtectedRoute>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
