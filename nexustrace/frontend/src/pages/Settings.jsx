import React, { useState, useEffect } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Save, Trash2, Building2, Settings2, Database, Loader2, AlertTriangle } from 'lucide-react';
import { readApiError } from '../lib/api';

export function Settings() {
  const { apiFetch } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await apiFetch(`${API_PREFIX}/system/settings`);
        if (res.ok) {
          const data = await res.json();
          setSettings(data.settings || {});
        }
      } catch (err) {
        setError('Failed to fetch system settings.');
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, [apiFetch]);

  const handleUpdate = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSuccess('');
    setError('');
  };

  const saveSettings = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await apiFetch(`${API_PREFIX}/system/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to save settings'));
      setSuccess('Settings saved successfully.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handlePurge = async () => {
    try {
      const res = await apiFetch(`${API_PREFIX}/system/purge`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to purge data'));
      setSuccess('All session and history data has been purged.');
      setShowPurgeConfirm(false);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="h-8 w-8 animate-spin mb-2" />
        <p>Initializing Control Node...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Global Configuration</h1>
          <p className="text-sm text-slate-400 mt-1">Manage industrial parameters, company identifiers, and local storage.</p>
        </div>
        <Button 
          onClick={saveSettings} 
          disabled={saving}
          className="bg-cyan-600 hover:bg-cyan-500 text-white"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
          Save Changes
        </Button>
      </div>

      {(error || success) && (
        <div className={`px-4 py-3 rounded-lg border text-sm animate-in fade-in zoom-in-95 ${
          error ? 'bg-red-950/30 border-red-900/50 text-red-300' : 'bg-green-950/30 border-green-900/50 text-green-300'
        }`}>
          {error || success}
        </div>
      )}

      <div className="flex gap-2 p-1 bg-slate-900/60 border border-slate-800 rounded-xl w-fit">
        {[
          { id: 'profile', icon: Building2, label: 'Company Profile' },
          { id: 'engine', icon: Settings2, label: 'Vision Engine' },
          { id: 'storage', icon: Database, label: 'Maintenance' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id 
                ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-900/20' 
                : 'text-slate-400 hover:text-slate-100 hove:bg-slate-800/50'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      <Card className="border-slate-800/80 bg-slate-900/60 shadow-lg overflow-hidden">
        <CardContent className="p-6">
          {activeTab === 'profile' && (
            <div className="grid gap-6">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Company Registered Name</label>
                  <Input 
                    value={settings.company_name || ''} 
                    onChange={(e) => handleUpdate('company_name', e)}
                    placeholder="Nexus Industrial Trace"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">GST/Tax Identification</label>
                  <Input 
                    value={settings.company_gst_id || ''} 
                    onChange={(e) => handleUpdate('company_gst_id', e)}
                    placeholder="GST-NEXUS-01"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Corporate Address</label>
                <Input 
                  value={settings.company_address || ''} 
                  onChange={(e) => handleUpdate('company_address', e)}
                  placeholder="Global HQ, Tech Sector 7"
                />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Contact Line</label>
                  <Input 
                    value={settings.company_contact || ''} 
                    onChange={(e) => handleUpdate('company_contact', e)}
                    placeholder="+91-000-000-0000"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Logo Asset URL</label>
                  <Input 
                    value={settings.company_logo_url || ''} 
                    onChange={(e) => handleUpdate('company_logo_url', e)}
                    placeholder="https://..."
                  />
                  <p className="text-[10px] text-slate-500 italic">This logo will be embedded in generated Challan PDFs.</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'engine' && (
            <div className="grid gap-6">
              <div className="grid md:grid-cols-3 gap-6">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Default Confidence</label>
                  <Input 
                    type="number" step="0.01" min="0" max="1"
                    value={settings.default_conf_threshold || '0.50'} 
                    onChange={(e) => handleUpdate('default_conf_threshold', e)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Default IOU</label>
                  <Input 
                    type="number" step="0.01" min="0" max="1"
                    value={settings.default_iou_threshold || '0.65'} 
                    onChange={(e) => handleUpdate('default_iou_threshold', e)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">ROI Padding (%)</label>
                  <Input 
                    type="number" min="0" max="50"
                    value={settings.default_roi_padding || '5'} 
                    onChange={(e) => handleUpdate('default_roi_padding', e)}
                  />
                </div>
              </div>
              <p className="text-xs text-slate-500 bg-slate-950/50 p-4 rounded-lg border border-slate-800">
                These values are used as baseline parameters for the vision engine. Individual sessions can still override these using the Advanced Params toggle on the dashboard.
              </p>
            </div>
          )}

          {activeTab === 'storage' && (
            <div className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">Automatic Log Purging</label>
                  <div className="flex items-center gap-3">
                    <Input 
                      type="number" min="1" max="365"
                      value={settings.retention_days || '30'} 
                      onChange={(e) => handleUpdate('retention_days', e)}
                    />
                    <span className="text-sm text-slate-400">Days</span>
                  </div>
                  <p className="text-[10px] text-slate-500">Sessions older than this will be scheduled for cleanup.</p>
                </div>
                
                <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-4 flex flex-col justify-center">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-slate-400">Local Database Health</span>
                    <span className="text-xs font-mono text-green-500">OPTIMIZED</span>
                  </div>
                  <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 w-[12%]" />
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-slate-800">
                <div className="bg-red-950/10 border border-red-900/30 rounded-xl p-6">
                  <div className="flex gap-4">
                    <div className="h-12 w-12 rounded-full bg-red-900/20 flex items-center justify-center shrink-0">
                      <AlertTriangle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="space-y-2">
                      <h4 className="font-bold text-red-400">Destructive Actions</h4>
                      <p className="text-xs text-red-300/80 leading-relaxed">
                        Purging telemetry data will permanently remove all historical session records, product counts, and associated video asset references from this node. This action cannot be undone.
                      </p>
                      
                      {!showPurgeConfirm ? (
                        <button 
                          onClick={() => setShowPurgeConfirm(true)}
                          className="mt-4 flex items-center gap-2 py-2 px-4 rounded-lg bg-red-900/30 hover:bg-red-900/50 border border-red-800 text-red-100 text-sm font-semibold transition-all"
                        >
                          <Trash2 className="h-4 w-4" /> Purge Persistent Records
                        </button>
                      ) : (
                        <div className="mt-4 flex flex-wrap items-center gap-3 p-3 bg-red-950/50 border border-red-900/50 rounded-lg animate-in zoom-in-95">
                          <span className="text-xs font-bold text-red-200 uppercase tracking-tighter">Are you absolutely sure?</span>
                          <button onClick={handlePurge} className="py-1.5 px-3 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-bold">YES, PURGE NOW</button>
                          <button onClick={() => setShowPurgeConfirm(false)} className="py-1.5 px-3 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold">CANCEL</button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
