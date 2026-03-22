import React, { useState, useEffect } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { ChevronDown, Play, Settings2, PlusCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { readApiError, safeOpenInNewTab } from '../lib/api';

const DEFAULT_PROCESSING_OPTIONS = [
  { value: 'run_yolo.py', label: 'run_yolo.py (YOLOv2 Baseline)' },
  { value: 'run_yolo2.py', label: 'run_yolo2.py (YOLOv2 Style)' },
  { value: 'run_yolo3.py', label: 'run_yolo3.py (YOLOv3 Optimized)' },
  { value: 'run_yolo4.py', label: 'run_yolo4.py (YOLOv4 Optimized)' },
  { value: 'run_yolo5.py', label: 'run_yolo5.py (YOLOv5 Hysteresis)' },
  { value: 'run_yoloraspPi.py', label: 'run_yoloraspPi.py (Raspberry Pi)' }
];

const parseFloatSetting = (value, label, { min = Number.NEGATIVE_INFINITY, max = Number.POSITIVE_INFINITY } = {}) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label} must be a number between ${min} and ${max}.`);
  }
  return parsed;
};

const parseIntegerSetting = (value, label, { min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER } = {}) => {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label} must be a whole number between ${min} and ${max}.`);
  }
  return parsed;
};

export function SessionSetup() {
  const { apiFetch } = useAuth();
  const { isRunning, operatorId, setOperatorId, batchId, setBatchId, fetchCurrentSession, sessionProducts } = useSession();
  const navigate = useNavigate();

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

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchSessionOptions = async () => {
      try {
        const res = await apiFetch(`${API_PREFIX}/sessions/options`);
        if (!res.ok) return;
        const data = await res.json();
        
        const scriptOptions = (data.runner_scripts || []).map(item => ({
          value: item.script_name,
          label: item.label ? `${item.script_name} (${item.label})` : item.script_name
        }));
        if (scriptOptions.length) {
          setProcessingOptions(scriptOptions);
        }

        const nextModelOptions = (data.model_files || []).map(item => ({
          value: item.path, label: item.name || item.path
        }));
        setModelOptions(nextModelOptions);
      } catch (err) {
        console.error('Failed to fetch session setup options', err);
      }
    };
    fetchSessionOptions();
  }, [apiFetch]);

  const parseProducts = (value) => String(value || '').split(',').map(i => i.trim()).filter(Boolean);

  const handleStart = async (e) => {
    e.preventDefault();
    if (isRunning) return;
    setError('');

    if (!videoSource.trim()) {
      setError('Video source is required to begin.');
      return;
    }

    setLoading(true);
    const parsedProducts = parseProducts(productsInput);
    
    try {
      const nextConfThreshold = countMode === 'roi_current'
        ? parseFloatSetting(confThreshold, 'Confidence threshold', { min: 0, max: 1 })
        : null;
      const nextIouThreshold = countMode === 'roi_current'
        ? parseFloatSetting(iouThreshold, 'IOU threshold', { min: 0, max: 1 })
        : null;
      const nextRoiPadding = countMode === 'roi_current'
        ? parseIntegerSetting(roiPadding, 'ROI padding', { min: 0, max: 500 })
        : null;

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
          conf_threshold: nextConfThreshold,
          iou_threshold: nextIouThreshold,
          roi_padding: nextRoiPadding,
          roi_label_keyword: countMode === 'roi_current' ? roiLabelKeyword : null,
          small_label_keyword: countMode === 'roi_current' ? smallLabelKeyword : null,
          product_type: parsedProducts[0] || null,
          products: parsedProducts
        })
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to start session'));
      await fetchCurrentSession();
      navigate('/');
    } catch (err) {
      setError(err.message || 'Error executing session start sequence.');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setError('');
    const selected = parseProducts(challanProductsInput);
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
      setError(err.message || 'Error halting the session.');
    }
  };

  const handleAddLiveProducts = async () => {
    const parsed = parseProducts(addProductsInput);
    if (!parsed.length) {
      setError('Enter at least one product name before injecting.');
      return;
    }
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
      setError(e.message || 'Failed to add live products.');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Session Setup</h1>
        <p className="text-sm text-slate-400 mt-1">Configure AI detection models, processing scripts, and operators before launching a pipeline.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <form onSubmit={handleStart} className="lg:col-span-2 space-y-6">
          <Card className="border-slate-800/80 bg-slate-900/60 shadow-lg">
            <CardHeader className="border-b border-slate-800/40">
              <CardTitle className="text-lg">Core Parameters</CardTitle>
            </CardHeader>
            <CardContent className="pt-6 space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <Input label="Operator ID" placeholder="OP-01" value={operatorId} onChange={(e) => setOperatorId(e)} disabled={isRunning} />
                <Input label="Batch ID" placeholder="B-2024-X" value={batchId} onChange={(e) => setBatchId(e)} disabled={isRunning} />
              </div>

              <Input 
                label="Video Resource Source" 
                placeholder="RTSP url, file path, or 0 for camera loop" 
                value={videoSource} 
                onChange={(e) => setVideoSource(e)} 
                disabled={isRunning} 
              />
              
              <Input 
                label="Products to Detect (comma separated)" 
                placeholder="Box Type A, Box Type B..." 
                value={productsInput} 
                onChange={(e) => setProductsInput(e)} 
                disabled={isRunning} 
              />
              
              <Select 
                label="Model Path (Detected files)" 
                options={[{value: '', label: 'Custom path (type in advanced)'}, ...modelOptions]} 
                value={modelOptions.some((o) => o.value === modelPath) ? modelPath : ''} 
                onChange={(e) => { if(e) setModelPath(e)}} 
                disabled={isRunning} 
              />
            </CardContent>
          </Card>

          <Card className="border-slate-800/80 bg-slate-900/60 shadow-lg cursor-pointer transition-colors hover:bg-slate-900/80" onClick={() => !isRunning && setAdvancedOpen(!advancedOpen)}>
            <div className="px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings2 className="h-5 w-5 text-slate-400" />
                <CardTitle className="text-base text-slate-300">Advanced Engine Settings</CardTitle>
              </div>
              <ChevronDown className={`h-5 w-5 text-slate-500 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
            </div>
            
            {advancedOpen && !isRunning && (
              <div className="px-6 pb-6 pt-2 space-y-5 border-t border-slate-800/40 mt-2" onClick={(e) => e.stopPropagation()}>
                <Select label="Inference Script" options={processingOptions} value={processingMode} onChange={(e) => setProcessingMode(e)} />
                <Input label="Custom Model Override" value={modelPath} onChange={(e) => setModelPath(e)} />
                <Select 
                  label="Count Mode Integration" 
                  options={[{value: 'roi_current', label: 'ROI Standard'}, {value: 'track_unique', label: 'YOLO Tracking Native'}]} 
                  value={countMode} 
                  onChange={(e) => setCountMode(e)} 
                />
                <Input
                  label="YOLOv5 Repo Path (optional)"
                  placeholder="D:/Nexus/yolov5"
                  value={yolov5RepoPath}
                  onChange={(e) => setYolov5RepoPath(e)}
                />
                 
                {countMode === 'roi_current' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4 bg-slate-950/50 p-4 rounded-lg border border-slate-800">
                    <Input label="Conf" value={confThreshold} onChange={(e) => setConfThreshold(e)} />
                    <Input label="IOU" value={iouThreshold} onChange={(e) => setIouThreshold(e)} />
                    <Input label="Pad" value={roiPadding} onChange={(e) => setRoiPadding(e)} />
                    <Input label="ROI Key" value={roiLabelKeyword} onChange={(e) => setRoiLabelKeyword(e)} />
                    <Input label="Small Key" value={smallLabelKeyword} onChange={(e) => setSmallLabelKeyword(e)} />
                  </div>
                )}
              </div>
            )}
          </Card>

          {error && <div className="p-3 bg-red-950/40 border border-red-900/50 text-red-400 text-sm rounded-lg">{error}</div>}

          {isRunning && (
            <Input
              label="Challan Products (optional, comma separated)"
              placeholder="Leave empty for all products"
              value={challanProductsInput}
              onChange={(e) => setChallanProductsInput(e)}
            />
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" size="lg" disabled={isRunning} isLoading={loading} className="flex-1 bg-emerald-600 hover:bg-emerald-700 shadow-emerald-900/20">
              <Play className="h-4 w-4 mr-2" /> Ignite Sequence
            </Button>
            {isRunning && (
              <Button type="button" size="lg" variant="destructive" onClick={handleStop} className="w-1/3">
                Stop Run
              </Button>
            )}
          </div>
        </form>

        <div className="space-y-6">
          <Card className="border-slate-800/80 bg-slate-900/60 shadow-lg border-t-2 border-t-indigo-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-slate-200 text-indigo-100">Live Injector</CardTitle>
              <CardDescription>Inject tracking targets into active stream.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-slate-950/70 p-3 rounded text-xs text-slate-300 font-mono border border-slate-800">
                Active Targets: <br/> {sessionProducts.length ? sessionProducts.join(', ') : 'Global (ALL)'}
              </div>
              <Input label="Append Classes" placeholder="New Entity..." value={addProductsInput} onChange={(e) => setAddProductsInput(e)} disabled={!isRunning} />
              <Button type="button" className="w-full bg-indigo-600 hover:bg-indigo-700" disabled={!isRunning} onClick={handleAddLiveProducts}>
                <PlusCircle className="mr-2 h-4 w-4" /> Inject Live
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
