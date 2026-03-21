import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth, API_PREFIX } from './AuthContext';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const API_ROOT_URL = API_BASE_URL.endsWith('/api') ? API_BASE_URL.slice(0, -4) : API_BASE_URL;
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ||
  (API_ROOT_URL.startsWith('https://') ? API_ROOT_URL.replace('https://', 'wss://') : API_ROOT_URL.replace('http://', 'ws://'));

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const { authToken, apiFetch, currentUser } = useAuth();
  const wsRef = useRef(null);

  const [isRunning, setIsRunning] = useState(false);
  const [count, setCount] = useState(0);
  const [fps, setFps] = useState(0);
  const [confidence, setConfidence] = useState(0);
  const [sessionDuration, setSessionDuration] = useState(0);
  const [sessionProducts, setSessionProducts] = useState([]);
  const [productCounts, setProductCounts] = useState({});
  const [imageSrc, setImageSrc] = useState('');

  const [operatorId, setOperatorId] = useState('');
  const [batchId, setBatchId] = useState('');

  const closeWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (!authToken) return;
    closeWebSocket();
    const ws = new WebSocket(`${WS_BASE_URL}/ws/live-feed?token=${encodeURIComponent(authToken)}`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.frame) setImageSrc(`data:image/jpeg;base64,${data.frame}`);
        if (data.count !== undefined) setCount(Number(data.count || 0));
        if (data.product_counts) setProductCounts(data.product_counts);
        if (data.fps !== undefined) setFps(Number(data.fps || 0));
        if (data.detection_confidence !== undefined) setConfidence(Number(data.detection_confidence || 0));
        if (data.duration_seconds !== undefined) setSessionDuration(Number(data.duration_seconds || 0));
        if (data.is_running !== undefined) setIsRunning(Boolean(data.is_running));
      } catch (_) {}
    };

    ws.onclose = () => {
      setIsRunning(false);
    };

    wsRef.current = ws;
  }, [authToken, closeWebSocket]);

  useEffect(() => {
    if (isRunning) connectWebSocket();
    else closeWebSocket();
  }, [connectWebSocket, closeWebSocket, isRunning]);

  const fetchCurrentSession = useCallback(async () => {
    if (!currentUser) return;
    try {
      const res = await apiFetch(`${API_PREFIX}/sessions/current`);
      if (!res.ok) return;
      const data = await res.json();
      const session = data.session || {};
      setIsRunning(Boolean(session.is_running));
      setCount(Number(session.count || 0));
      setFps(Number(session.fps || 0));
      setConfidence(Number(session.detection_confidence || 0));
      setSessionDuration(Number(session.duration_seconds || 0));
      setProductCounts(session.product_counts || {});
      setSessionProducts(session.products || []);
      if (session.operator_id) setOperatorId(session.operator_id);
      if (session.batch_id) setBatchId(session.batch_id);
    } catch (_) {}
  }, [apiFetch, currentUser]);

  useEffect(() => {
    fetchCurrentSession();
    const timer = setInterval(fetchCurrentSession, 1000);
    return () => {
      clearInterval(timer);
      closeWebSocket();
    };
  }, [fetchCurrentSession, closeWebSocket]);

  return (
    <SessionContext.Provider
      value={{
        isRunning, setIsRunning,
        count, setCount,
        fps, setFps,
        confidence, setConfidence,
        sessionDuration, setSessionDuration,
        sessionProducts, setSessionProducts,
        productCounts, setProductCounts,
        imageSrc, setImageSrc,
        operatorId, setOperatorId,
        batchId, setBatchId,
        fetchCurrentSession
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
