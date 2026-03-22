import React, { useState, useEffect } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { FileText, Download, Loader2, CheckSquare, Square, XCircle } from 'lucide-react';
import { readApiError, safeOpenInNewTab } from '../lib/api';

const formatDateTime = (isoText) => {
  if (!isoText) return '-';
  const date = new Date(isoText);
  if (Number.isNaN(date.getTime())) return isoText;
  return date.toLocaleString();
};

export function History() {
  const { apiFetch, authToken } = useAuth();
  
  const [sessions, setSessions] = useState([]);
  const [historyOptions, setHistoryOptions] = useState({ operators: [], products: [] });
  const [filters, setFilters] = useState({ search: '', operator_id: '', product_name: '' });
  
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [selectedSessionIds, setSelectedSessionIds] = useState(new Set());
  
  const [sessionDetails, setSessionDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [generatingMulti, setGeneratingMulti] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const res = await apiFetch(`${API_PREFIX}/sessions/history/filters`);
        if (res.ok) {
          const data = await res.json();
          setHistoryOptions({ operators: data.operators || [], products: data.products || [] });
          setError('');
        }
      } catch (err) {
        setError(err.message || 'Failed to fetch history filter options.');
      }
    };
    fetchOptions();
  }, [apiFetch]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const params = new URLSearchParams();
        if (filters.search) params.set('search', filters.search);
        if (filters.operator_id) params.set('operator_id', filters.operator_id);
        if (filters.product_name) params.set('product_name', filters.product_name);
        
        const query = params.toString();
        const res = await apiFetch(`${API_PREFIX}/sessions/history/detailed${query ? `?${query}` : ''}`);
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions || []);
          setError('');
        }
      } catch (err) {
        setError(err.message || 'Failed to fetch session history.');
      }
    };
    const to = setTimeout(fetchHistory, 300);
    return () => clearTimeout(to);
  }, [apiFetch, filters]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSessionDetails(null);
      return;
    }
    const fetchDetails = async () => {
      setLoadingDetails(true);
      try {
        const res = await apiFetch(`${API_PREFIX}/sessions/${selectedSessionId}/details`);
        if (res.ok) {
          setSessionDetails(await res.json());
          setError('');
        } else {
          setSessionDetails(null);
          setError(await readApiError(res, 'Failed to fetch session details.'));
        }
      } catch (err) {
        setSessionDetails(null);
        setError(err.message || `Failed to fetch details for session ${selectedSessionId}.`);
      }
      setLoadingDetails(false);
    };
    fetchDetails();
  }, [apiFetch, selectedSessionId]);

  const toggleSessionSelection = (e, sid) => {
    e.stopPropagation();
    setSelectedSessionIds(prev => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedSessionIds.size === sessions.length) {
      setSelectedSessionIds(new Set());
    } else {
      setSelectedSessionIds(new Set(sessions.map(s => s.id)));
    }
  };

  const handleDownloadChallan = async (sessionId) => {
    try {
      const res = await apiFetch(`${API_PREFIX}/challans/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to generate challan'));
      const data = await res.json();
      downloadFile(data.challan_file);
    } catch (err) {
      setError(err.message || `Failed to download challan for session ${sessionId}.`);
    }
  };

  const handleBatchChallan = async () => {
    setGeneratingMulti(true);
    try {
      const res = await apiFetch(`${API_PREFIX}/challans/generate-multi`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_ids: Array.from(selectedSessionIds) })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to generate batch challan'));
      const data = await res.json();
      downloadFile(data.challan_file);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingMulti(false);
    }
  };

  const downloadFile = async (fileName) => {
    try {
      const fileRes = await apiFetch(`${API_PREFIX}/challans/files/${encodeURIComponent(fileName)}`);
      if (!fileRes.ok) throw new Error(await readApiError(fileRes, 'Failed to download file'));

      const blob = await fileRes.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="h-full flex flex-col space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-height-[calc(100vh-6rem)] relative">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Session Audit History</h1>
        <p className="text-sm text-slate-400 mt-1">Review past inspections, generate challans, and playback surveillance logs.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-4 items-end justify-between">
        <div className="flex gap-4 items-end flex-wrap">
          <div className="w-full md:w-64">
            <Input placeholder="Search batch or operator" value={filters.search} onChange={(e) => setFilters(prev => ({...prev, search: e}))} />
          </div>
          <div className="w-full md:w-48">
            <Select 
              options={[{value: '', label: 'All Operators'}, ...historyOptions.operators.map(o => ({value:o}))]} 
              value={filters.operator_id} 
              onChange={(e) => setFilters(prev => ({...prev, operator_id: e}))} 
            />
          </div>
        </div>

        {selectedSessionIds.size > 0 && (
          <div className="flex items-center gap-3 animate-in fade-in slide-in-from-right-4">
            <span className="text-xs font-bold text-cyan-500 uppercase tracking-widest bg-cyan-950/30 px-3 py-1.5 rounded-full border border-cyan-800/50">
              {selectedSessionIds.size} Sessions Selected
            </span>
            <Button 
               onClick={handleBatchChallan} 
               disabled={generatingMulti}
               className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/20 h-9"
            >
              {generatingMulti ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Download className="h-4 w-4 mr-2" />}
              Generate Batch Challan
            </Button>
            <Button variant="ghost" className="text-slate-400 hover:text-red-400 h-9 px-2" onClick={() => setSelectedSessionIds(new Set())}>
              <XCircle className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6">
        <Card className="flex-1 border-slate-800/80 bg-slate-900/60 shadow-lg overflow-hidden flex flex-col">
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm text-left border-collapse">
              <thead className="bg-slate-950/80 text-slate-400 sticky top-0 z-10 backdrop-blur-md border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 w-10">
                    <button onClick={selectAll} className="text-slate-500 hover:text-cyan-400 transition-colors">
                      {selectedSessionIds.size === sessions.length && sessions.length > 0 ? <CheckSquare className="h-4 w-4 text-cyan-500" /> : <Square className="h-4 w-4" />}
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">Session ID</th>
                  <th className="px-4 py-3 font-medium">Operator</th>
                  <th className="px-4 py-3 font-medium">Count</th>
                  <th className="px-4 py-3 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40">
                {sessions.map(session => (
                  <tr 
                    key={session.id} 
                    onClick={() => setSelectedSessionId(session.id)}
                    className={`cursor-pointer transition-colors hover:bg-cyan-900/10 ${selectedSessionId === session.id ? 'bg-cyan-900/20' : ''}`}
                  >
                    <td className="px-4 py-3" onClick={(e) => toggleSessionSelection(e, session.id)}>
                      {selectedSessionIds.has(session.id) ? <CheckSquare className="h-4 w-4 text-cyan-500" /> : <Square className="h-4 w-4 text-slate-700" />}
                    </td>
                    <td className="px-4 py-3 font-mono text-cyan-400">#{session.id}</td>
                    <td className="px-4 py-3 text-slate-300">{session.operator_id || '-'}</td>
                    <td className="px-4 py-3 font-semibold text-slate-200">{session.final_count}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{formatDateTime(session.timestamp)}</td>
                  </tr>
                ))}
                {!sessions.length && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500">No telemetry data found for these filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {selectedSessionId && (
          <Card className="flex-1 lg:max-w-md border-slate-800/80 bg-slate-900/80 shadow-2xl flex flex-col animate-in slide-in-from-right-8 duration-300">
            {loadingDetails ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-cyan-600" />
              </div>
            ) : sessionDetails ? (
              <div className="p-5 overflow-auto space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-100">Session #{sessionDetails.session.id}</h3>
                  <div className="flex items-center gap-4 text-xs mt-2 text-slate-400">
                    <span>OP: <strong className="text-slate-300">{sessionDetails.session.operator_id || 'N/A'}</strong></span>
                    <span>Batch: <strong className="text-slate-300">{sessionDetails.session.batch_id || 'N/A'}</strong></span>
                  </div>
                </div>

                {sessionDetails.video_url ? (
                  <div className="rounded-lg overflow-hidden border border-slate-800 bg-black aspect-video relative group">
                    <video src={`${sessionDetails.video_url}${sessionDetails.video_url.includes('?') ? '&' : '?'}token=${authToken}`} controls className="w-full h-full object-contain" />
                  </div>
                ) : (
                  <div className="aspect-video bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-center text-slate-500 text-sm">
                    No Video Asset Retained
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 mb-2">
                  <Button variant="secondary" className="w-full bg-cyan-700/80 hover:bg-cyan-600/80 text-white border border-cyan-500/50" onClick={() => handleDownloadChallan(selectedSessionId)}>
                    <Download className="h-4 w-4 mr-2" /> Single Challan
                  </Button>
                  {sessionDetails.video_url && (
                    <Button variant="outline" className="w-full border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10" onClick={() => safeOpenInNewTab(`${sessionDetails.video_url}${sessionDetails.video_url.includes('?') ? '&' : '?'}token=${authToken}`)}>
                      <FileText className="h-4 w-4 mr-2" /> Play Original
                    </Button>
                  )}
                </div>

                {/* --- Challan Preview UI --- */}
                <div>
                  <h4 className="text-sm font-semibold text-cyan-400 mt-2 mb-3 border-b border-slate-800 pb-2">Challan Document Preview</h4>
                  <div className="border border-slate-600 bg-[#1e1e1e] text-[#d4d4d4] rounded-sm text-[11px] font-sans w-full overflow-x-auto shadow-inner">
                    <table className="w-full border-collapse">
                      <tbody>
                        <tr className="border-b border-slate-600">
                          <td className="p-2 border-r border-slate-600 w-1/4">Customer Detail</td>
                          <td className="p-2 border-r border-slate-600 w-1/4"></td>
                          <td className="p-2 border-r border-slate-600 w-1/4">Challan No.</td>
                          <td className="p-2">{(sessionDetails.session?.id || '').toString().padStart(9, '0')}</td>
                        </tr>
                        <tr className="border-b border-slate-600">
                          <td className="p-2 border-r border-slate-600">M/S</td>
                          <td className="p-2 border-r border-slate-600"></td>
                          <td className="p-2 border-r border-slate-600">Pickup Date</td>
                          <td className="p-2">{new Date(sessionDetails.session?.timestamp || Date.now()).toLocaleDateString('en-GB')}</td>
                        </tr>
                        <tr className="border-b border-slate-600">
                          <td className="p-2 border-r border-slate-600">Transporter ID</td>
                          <td className="p-2 border-r border-slate-600"></td>
                          <td className="p-2 border-r border-slate-600">Lot No.</td>
                          <td className="p-2">{sessionDetails.session?.batch_id || '10'}</td>
                        </tr>
                        <tr className="border-b border-slate-600">
                          <td className="p-2 border-r border-slate-600">Courier Partner</td>
                          <td className="p-2 border-r border-slate-600"></td>
                          <td className="p-2 border-r border-slate-600">No. of Boxes</td>
                          <td className="p-2">{sessionDetails.session?.final_count || '0'}</td>
                        </tr>
                        <tr className="border-b border-slate-600 bg-slate-700/20 h-4">
                          <td colSpan={4}></td>
                        </tr>
                        <tr className="border-b border-slate-600">
                          <td className="p-2 border-r border-slate-600 font-semibold" colSpan={1}>Sr. No.</td>
                          <td className="p-2 border-r border-slate-600 font-semibold" colSpan={1}>Name of Product</td>
                          <td className="p-2 border-r border-slate-600 font-semibold" colSpan={1}>Qty</td>
                          <td className="p-2 font-semibold"></td>
                        </tr>
                        
                        {(sessionDetails.products && sessionDetails.products.length > 0) ? (
                          sessionDetails.products.map((p, idx) => (
                            <tr key={idx} className="border-b border-slate-600">
                              <td className="p-2 border-r border-slate-600" colSpan={1}>{idx + 1}.</td>
                              <td className="p-2 border-r border-slate-600" colSpan={1}>{p.product_name}</td>
                              <td className="p-2 border-r border-slate-600" colSpan={1}>{p.count}</td>
                              <td className="p-2" colSpan={1}></td>
                            </tr>
                          ))
                        ) : (
                          <tr className="border-b border-slate-600">
                            <td className="p-2 border-r border-slate-600" colSpan={1}>1.</td>
                            <td className="p-2 border-r border-slate-600" colSpan={1}>All Products</td>
                            <td className="p-2 border-r border-slate-600" colSpan={1}>{sessionDetails.session?.final_count || '0'}</td>
                            <td className="p-2" colSpan={1}></td>
                          </tr>
                        )}
                        
                        <tr>
                          <td className="p-2 border-r border-slate-600" colSpan={1}></td>
                          <td className="p-2 border-r border-slate-600 font-semibold" colSpan={1}>Total</td>
                          <td className="p-2 border-r border-slate-600 font-semibold" colSpan={1}>
                            {sessionDetails.products?.reduce((acc, p) => acc + parseInt(p.count || 0), 0) || sessionDetails.session?.final_count || '0'}
                          </td>
                          <td className="p-2" colSpan={1}></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}
          </Card>
        )}
      </div>
    </div>
  );
}
