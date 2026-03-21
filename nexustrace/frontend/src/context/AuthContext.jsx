import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const API_PREFIX = API_BASE_URL.endsWith('/api') ? API_BASE_URL : `${API_BASE_URL}/api`;

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('nexustrace_token') || '');
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const clearAuth = useCallback(() => {
    localStorage.removeItem('nexustrace_token');
    setAuthToken('');
    setCurrentUser(null);
  }, []);

  const apiFetch = useCallback(
    async (url, options = {}) => {
      const headers = new Headers(options.headers || {});
      if (authToken) headers.set('Authorization', `Bearer ${authToken}`);
      const response = await fetch(url, { ...options, headers });
      if (response.status === 401 && authToken) {
        clearAuth();
      }
      return response;
    },
    [authToken, clearAuth]
  );

  const validateToken = useCallback(async () => {
    if (!authToken) {
      setCurrentUser(null);
      setAuthLoading(false);
      return;
    }
    try {
      const res = await apiFetch(`${API_PREFIX}/auth/me`);
      if (!res.ok) throw new Error('Session expired');
      const data = await res.json();
      setCurrentUser(data.user || null);
    } catch (_) {
      clearAuth();
    } finally {
      setAuthLoading(false);
    }
  }, [apiFetch, authToken, clearAuth]);

  useEffect(() => {
    validateToken();
  }, [validateToken]);

  const login = async (username, password) => {
    const res = await fetch(`${API_PREFIX}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      let detail = 'Login failed';
      try {
        const data = await res.json();
        if (data?.detail) detail = data.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    const data = await res.json();
    const token = String(data.access_token || '');
    if (!token) throw new Error('No access token returned');
    
    localStorage.setItem('nexustrace_token', token);
    setAuthToken(token);
    setCurrentUser(data.user || null);
  };

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  return (
    <AuthContext.Provider
      value={{
        authToken,
        currentUser,
        authLoading,
        apiFetch,
        login,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
