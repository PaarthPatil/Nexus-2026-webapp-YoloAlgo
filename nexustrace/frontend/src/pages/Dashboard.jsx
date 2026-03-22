import React, { useEffect, useState, useMemo } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { 
  Activity, Layers, PlayCircle, StopCircle, Video, ListTree, 
  Settings2, Play, Download, ChevronDown, PlusCircle, Monitor, Zap, Loader2, Info
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { readApiError, safeOpenInNewTab } from '../lib/api';

const DEFAULT_PROCESSING_OPTIONS = [
  { value: 'nexus_optimized', label: 'Nexus Optimized (Accurate)' },
  { value: 'run_yolo_nexus_optimized.py', label: 'run_yolo_nexus_optimized.py (High Accuracy)' },
  { value: 'run_yolo3.py', label: 'run_yolo3.py (YOLOv3 Optimized)' },
  { value: 'run_yolo4.py', label: 'run_yolo4.py (YOLOv4 Optimized)' },
  { value: 'run_yolo5.py', label: 'run_yolo5.py (YOLOv5 Hysteresis)' },
  { value: 'run_yoloraspPi.py', label: 'run_yoloraspPi.py (Raspberry Pi)' }
];

const MetricCard = React.memo(function MetricCard({ title, value, icon: Icon, colorClass }) {
  return (
    <Card className="border-slate-800/60 bg-slate-900/40 hover:bg-slate-900/60 transition-all duration-300 transform hover:scale-[1.02]">
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClass} bg-opacity-10 border border-current border-opacity-20`}>
          <Icon className="h-4 w-4 opacity-90" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{title}</p>
          <p className="text-xl font-bold tracking-tight text-slate-100">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
});

export function Dashboard() {
  const { apiFetch } = useAuth();
  const { 
    isRunning, imageSrc, count, fps, confidence, productCounts,
    operatorId, setOperatorId, batchId, setBatchId, fetchCurrentSession, sessionProducts
  } = useSession();
  const navigate = useNavigate();

  // Session Setup States
  const [videoSource, setVideoSource] = useState('');
  const [modelPath, setModelPath] = useState('box_detection.pt');
  const [processingMode, setProcessingMode] = useState('run_yolo3.py');
  const [processingOptions, setProcessingOptions] = useState(DEFAULT_PROCESSING_OPTIONS);
  const [modelOptions, setModelOptions] = useState([]);
  const [countMode, setCountMode] = useState('roi_current');
  const [yolov5RepoPath, setYolov5RepoPath] = useState('');
  const [confThreshold, setConfThreshold] = useState('0.50');
  const [iouThreshold, setIouThreshold] = useState('0.65');
  const [roiPadding, setRoiPadding] = useState('5');
  const [roiLabelKeyword, setRoiLabelKeyword] = useState('bigger');
  const [smallLabelKeyword, setSmallLabelKeyword] = useState('box');
  const [productsInput, setProductsInput] = useState('');
  const [addProductsInput, setAddProductsInput] = useState('');
  const [challanProductsInput, setChallanProductsInput] = useState('');
  const [realTime, setRealTime] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dashboardStats, setDashboardStats] = useState(null);
  const [localVideos, setLocalVideos] = useState([]);

  useEffect(() => {
    const fetchStatsAndOptions = async () => {
      try {
        const [statsRes, optionsRes, settingsRes] = await Promise.all([
          apiFetch(`${API_PREFIX}/dashboard/stats`),
          apiFetch(`${API_PREFIX}/sessions/options`),
          apiFetch(`${API_PREFIX}/system/settings`)
        ]);

        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setDashboardStats(statsData.stats);
        }

        if (optionsRes.ok) {
          const optionsData = await optionsRes.json();
          const scriptOptions = (optionsData.runner_scripts || []).map(item => ({
            value: item.script_name,
            label: item.label ? `${item.script_name} (${item.label})` : item.script_name
          }));
          if (scriptOptions.length) setProcessingOptions(scriptOptions);

          const nextModelOptions = (optionsData.model_files || []).map(item => ({
            value: item.path, label: item.name || item.path
          }));
          setModelOptions(nextModelOptions);
        }

        if (settingsRes.ok) {
          const sData = await settingsRes.json();
          const s = sData.settings || {};
          if (s.default_conf_threshold) setConfThreshold(s.default_conf_threshold);
          if (s.default_iou_threshold) setIouThreshold(s.default_iou_threshold);
          if (s.default_roi_padding) setRoiPadding(s.default_roi_padding);
        }

        const videosRes = await apiFetch(`${API_PREFIX}/system/local-videos`);
        if (videosRes.ok) {
          const vData = await videosRes.json();
          setLocalVideos(vData.videos || []);
        }
      } catch (err) {
        console.error('Failed to fetch dashboard data', err);
      }
    };
    fetchStatsAndOptions();
  }, [apiFetch, isRunning]);

  const parseProducts = (value) => String(value || '').split(',').map(i => i.trim()).filter(Boolean);

  const handleStart = async (e) => {
    e.preventDefault();
    if (isRunning) return;
    setError('');
    if (!videoSource.trim()) {
      setError('Video source is required.');
      return;
    }

    setLoading(true);
    const parsedProducts = parseProducts(productsInput);
    
    try {
      const res = await apiFetch(`${API_PREFIX}/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          batch_id: batchId,
          video_source: videoSource,
          model_path: modelPath,
          processing_mode: processingMode,
          count_mode: countMode,
          yolov5_repo_path: yolov5RepoPath || null,
          conf_threshold: parseFloat(confThreshold),
          iou_threshold: parseFloat(iouThreshold),
          roi_padding: parseInt(roiPadding),
          roi_label_keyword: countMode === 'roi_current' ? roiLabelKeyword : null,
          small_label_keyword: countMode === 'roi_current' ? smallLabelKeyword : null,
          products: parsedProducts,
          real_time: realTime
        })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to start session'));
      await fetchCurrentSession();
    } catch (err) {
      setError(err.message || 'Error starting session.');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setError('');
    const selected = parseProducts(challanProductsInput);
    setLoading(true);
    try {
      const res = await apiFetch(`${API_PREFIX}/sessions/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          batch_id: batchId,
          challan_products: selected.length ? selected : null
        })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to stop session'));
      const data = await res.json();
      await fetchCurrentSession();
      if (data.challan_file) {
        safeOpenInNewTab(`${API_PREFIX}/challans/files/${encodeURIComponent(data.challan_file)}`);
      }
    } catch (err) {
      setError(err.message || 'Error stopping session.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddLiveProducts = async () => {
    const parsed = parseProducts(addProductsInput);
    if (!parsed.length) return;
    try {
      setError('');
      const res = await apiFetch(`${API_PREFIX}/sessions/products`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ products: parsed })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to add products'));
      setAddProductsInput('');
      fetchCurrentSession();
    } catch (e) {
      setError(e.message);
    }
  };

  const productRows = useMemo(
    () => Object.entries(productCounts || {}).sort((a, b) => b[1] - a[1]),
    [productCounts]
  );

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Live Mission Control</h1>
          <p className="text-sm text-slate-400 mt-1">Industrial Vision Intelligence System (Nexus-IVIS)</p>
        </div>
        <div className="flex gap-3">
          {isRunning ? (
            <Badge variant="success" className="animate-pulse shadow-[0_0_15px_rgba(16,185,129,0.3)] px-3 py-1">
              <Activity className="h-3.5 w-3.5 mr-1" /> ACTIVE FEED
            </Badge>
          ) : (
            <Badge variant="secondary" className="px-3 py-1 text-slate-400 border border-slate-700 bg-slate-900/50">
              <StopCircle className="h-3.5 w-3.5 mr-1" /> SYSTEM IDLE
            </Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="System Sessions" value={dashboardStats?.total_sessions ?? 0} icon={Layers} colorClass="text-cyan-400" />
        <MetricCard title="Objects Detected" value={dashboardStats?.total_count ?? 0} icon={ListTree} colorClass="text-indigo-400" />
        <MetricCard title="Processing FPS" value={isRunning ? fps.toFixed(1) : '0.0'} icon={Zap} colorClass="text-amber-400" />
        <MetricCard
          title="Avg Confidence"
          value={isRunning ? `${(confidence * 100).toFixed(1)}%` : '0%'}
          icon={Activity}
          colorClass="text-emerald-400"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Main Observation Deck */}
        <div className="xl:col-span-8 flex flex-col gap-6">
          <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden flex flex-col">
            <CardHeader className="border-b border-slate-800/60 bg-slate-900/80 py-3 px-5 flex flex-row items-center justify-between">
              <div className="flex items-center gap-2 text-cyan-400">
                <Video className="h-4 w-4" />
                <CardTitle className="text-sm font-medium uppercase tracking-widest">Observation Feed</CardTitle>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Latency: <span className="text-slate-300">{(1000/fps || 0).toFixed(0)}ms</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 relative min-h-[480px] bg-black flex items-center justify-center group">
              {isRunning && imageSrc ? (
                <img src={imageSrc} alt="Live feed" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center p-12 space-y-6">
                  <div className="w-20 h-20 rounded-full bg-slate-900/50 border border-slate-800 flex items-center justify-center text-slate-700 mx-auto shadow-inner">
                    <Monitor className="h-8 w-8" />
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-slate-300">Feed Disconnected</h3>
                    <p className="text-sm text-slate-500 max-w-sm mt-2">Initialize parameters on the right to start a high-performance detection sequence.</p>
                  </div>
                </div>
              )}
              
              {/* Overlay HUD */}
              {isRunning && (
                <div className="absolute top-4 left-4 p-3 rounded-lg bg-slate-950/80 border border-slate-800/50 backdrop-blur-md space-y-2 pointer-events-none">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Global Tally</div>
                  <div className="text-3xl font-black text-cyan-400 tabular-nums leading-none tracking-tight">{count}</div>
                  <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden mt-1">
                    <div className="h-full bg-cyan-500 animate-[pulse_1s_ease-in-out_infinite]" style={{ width: '100%' }} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Product Breakdown Grid */}
          <Card className="border-slate-800/80 bg-slate-900/40 shadow-lg">
            <CardHeader className="py-3 border-b border-slate-800/40 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-bold uppercase tracking-widest text-slate-400">Tactical Breakdown</CardTitle>
              <Badge variant="outline" className="text-[10px] border-slate-700 text-slate-500">{productRows.length} Categories</Badge>
            </CardHeader>
            <CardContent className="p-0">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 divide-x divide-y divide-slate-800/40">
                {productRows.length > 0 ? (
                  productRows.map(([name, productCount]) => (
                    <div key={name} className="p-4 flex flex-col gap-1 group hover:bg-slate-800/20 transition-colors">
                      <span className="text-[10px] font-bold text-slate-500 uppercase truncate">{name}</span>
                      <span className="text-2xl font-bold text-slate-200 tabular-nums">{productCount}</span>
                    </div>
                  ))
                ) : (
                  <div className="col-span-full p-8 text-center text-sm text-slate-500 italic">
                    Waiting for detections...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tactical Control Panel */}
        <div className="xl:col-span-4 space-y-6">
          <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl border-t-2 border-t-cyan-500">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Operations Control</CardTitle>
                <Badge variant={isRunning ? 'success' : 'secondary'} className="font-mono text-[10px]">
                  {isRunning ? 'TX_LEVEL_HIGH' : 'STDBY'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              {!isRunning ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="Operator" placeholder="OP-01" value={operatorId} onChange={setOperatorId} />
                    <Input label="Batch" placeholder="BETA-9" value={batchId} onChange={setBatchId} />
                  </div>
                  <Input 
                    label="Source Location" 
                    placeholder="URL, Path or 0" 
                    value={videoSource} 
                    onChange={setVideoSource} 
                    list="local-video-list"
                  />
                  <datalist id="local-video-list">
                    {localVideos.map((vid, idx) => (
                      <option key={idx} value={vid.path}>{vid.name}</option>
                    ))}
                  </datalist>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/50 border border-slate-800 mt-2">
                    <div className="flex items-center gap-2">
                      <Monitor className="h-4 w-4 text-cyan-400" />
                      <div>
                        <div className="text-xs font-bold text-slate-300">Real-time Throttling</div>
                        <div className="text-[10px] text-slate-500">Sync playback to original FPS</div>
                      </div>
                    </div>
                    <button 
                      onClick={() => setRealTime(!realTime)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${realTime ? 'bg-cyan-600' : 'bg-slate-700'}`}
                    >
                      <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${realTime ? 'translate-x-5' : 'translate-x-1'}`} />
                    </button>
                  </div>

                  <Button onClick={handleStart} className="w-full bg-cyan-600 hover:bg-cyan-500 shadow-lg shadow-cyan-900/20 py-6 text-base font-bold" isLoading={loading}>
                    <Play className="h-5 w-5 mr-2 fill-current" /> EXECUTE SEQUENCE
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/50 space-y-3">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500 font-bold uppercase">Active Operator</span>
                      <span className="text-cyan-400 font-mono">{operatorId}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500 font-bold uppercase">Target Batch</span>
                      <span className="text-cyan-400 font-mono">{batchId}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500 font-bold uppercase">Source</span>
                      <span className="text-slate-300 truncate max-w-[150px] font-mono">{videoSource}</span>
                    </div>
                  </div>

                  <Input
                    label="Final Challan Filter (optional)"
                    placeholder="Filtered items..."
                    value={challanProductsInput}
                    onChange={setChallanProductsInput}
                  />

                  <Button variant="destructive" onClick={handleStop} className="w-full py-6 text-base font-bold shadow-lg shadow-red-900/20" isLoading={loading}>
                    <StopCircle className="h-5 w-5 mr-2" /> TERMINATE RUN
                  </Button>
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-950/30 border border-red-900/50 text-red-400 text-[11px] animate-in fade-in zoom-in-95">
                  <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <button 
                onClick={() => setAdvancedOpen(!advancedOpen)}
                className="w-full flex items-center justify-between text-[10px] font-bold text-slate-500 uppercase tracking-widest hover:text-slate-300 transition-colors py-2 border-t border-slate-800/50"
              >
                <span>Advanced Engine Params</span>
                <ChevronDown className={`h-3 w-3 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
              </button>

              {advancedOpen && (
                <div className="space-y-4 pt-2 animate-in slide-in-from-top-2 duration-300">
                  <Select label="Algorithm" options={processingOptions} value={processingMode} onChange={setProcessingMode} disabled={isRunning} />
                  <Input label="Model Asset" value={modelPath} onChange={setModelPath} disabled={isRunning} />
                  <Input label="ROI Key" value={roiLabelKeyword} onChange={setRoiLabelKeyword} disabled={isRunning} />
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="Confidence" value={confThreshold} onChange={setConfThreshold} disabled={isRunning} />
                    <Input label="IOU" value={iouThreshold} onChange={setIouThreshold} disabled={isRunning} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-slate-800/80 bg-slate-900/40 border-t-2 border-t-indigo-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                <Zap className="h-3 w-3 text-indigo-400" /> Live Target Injector
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 gap-2">
                <Input 
                  placeholder="New product name..." 
                  value={addProductsInput} 
                  onChange={setAddProductsInput} 
                  disabled={!isRunning}
                  className="bg-slate-950/50"
                />
                <Button 
                  size="sm" 
                  className="bg-indigo-600 hover:bg-indigo-500 transition-all font-bold text-[11px]" 
                  disabled={!isRunning} 
                  onClick={handleAddLiveProducts}
                >
                  <PlusCircle className="mr-2 h-3.5 w-3.5" /> INJECT CLASS
                </Button>
              </div>
              <div className="p-2 rounded bg-slate-950/50 border border-slate-800/50">
                <div className="text-[9px] text-slate-500 uppercase font-black mb-1">Active Scope</div>
                <div className="text-[10px] text-slate-300 font-mono truncate">
                  {sessionProducts.length ? sessionProducts.join(', ') : 'BROAD_SCAN (ALL)'}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
