import React, { useState, useEffect } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { FileText, Download, Share2, Eye, FileOutput, Loader2 } from 'lucide-react';

const formatDateTime = (isoText) => {
  if (!isoText) return '-';
  const date = new Date(isoText);
  if (Number.isNaN(date.getTime())) return isoText;
  return date.toLocaleString();
};

export function History() {
  const { apiFetch } = useAuth();
  
  const [sessions, setSessions] = useState([]);
  const [historyOptions, setHistoryOptions] = useState({ operators: [], products: [] });
  const [filters, setFilters] = useState({ search: '', operator_id: '', product_name: '' });
  
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const res = await apiFetch(`${API_PREFIX}/sessions/history/filters`);
        if (res.ok) {
          const data = await res.json();
          setHistoryOptions({ operators: data.operators || [], products: data.products || [] });
        }
      } catch (err) {}
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
        }
      } catch (err) {}
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
        }
      } catch (err) {}
      setLoadingDetails(false);
    };
    fetchDetails();
  }, [apiFetch, selectedSessionId]);

  const handleDownloadChallan = async (sessionId) => {
    try {
      const res = await apiFetch(`${API_PREFIX}/challans/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.challan_file) {
          const fileRes = await apiFetch(`${API_PREFIX}/challans/files/${encodeURIComponent(data.challan_file)}`);
          if (fileRes.ok) {
            const blob = await fileRes.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.challan_file;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
          }
        }
      }
    } catch (err) {}
  };

  return (
    <div className="h-full flex flex-col space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-h-[calc(100vh-6rem)]">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Session Audit History</h1>
        <p className="text-sm text-slate-400 mt-1">Review past inspections, generate challans, and playback surveillance logs.</p>
      </div>

      <div className="flex flex-wrap gap-4 items-end">
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

      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6">
        <Card className="flex-1 border-slate-800/80 bg-slate-900/60 shadow-lg overflow-hidden flex flex-col">
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm text-left border-collapse">
              <thead className="bg-slate-950/80 text-slate-400 sticky top-0 z-10 backdrop-blur-md border-b border-slate-800">
                <tr>
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
                    className={`cursor-pointer transition-colors hover:bg-cyan-900/20 ${selectedSessionId === session.id ? 'bg-cyan-900/30 border-l-2 border-cyan-500' : 'border-l-2 border-transparent'}`}
                  >
                    <td className="px-4 py-3 font-mono text-cyan-400">#{session.id}</td>
                    <td className="px-4 py-3 text-slate-300">{session.operator_id || '-'}</td>
                    <td className="px-4 py-3 font-semibold text-slate-200">{session.final_count}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{formatDateTime(session.timestamp)}</td>
                  </tr>
                ))}
                {!sessions.length && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">No telemetry data found for these filters.</td>
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
                    <video src={sessionDetails.video_url} controls className="w-full h-full object-contain" />
                  </div>
                ) : (
                  <div className="aspect-video bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-center text-slate-500 text-sm">
                    No Video Asset Retained
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 mb-2">
                  <Button variant="secondary" className="w-full bg-cyan-700/80 hover:bg-cyan-600/80 text-white border border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.15)]" onClick={() => handleDownloadChallan(selectedSessionId)}>
                    <Download className="h-4 w-4 mr-2" /> Download Challan PDF
                  </Button>
                  {sessionDetails.video_url && (
                    <Button variant="outline" className="w-full border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10" onClick={() => window.open(sessionDetails.video_url, '_blank')}>
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
