import React, { useEffect, useState, useMemo } from 'react';
import { useAuth, API_PREFIX } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Activity, Layers, PlayCircle, StopCircle, Video, ListTree } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

function MetricCard({ title, value, icon: Icon, colorClass }) {
  return (
    <Card className="border-slate-800/60 bg-slate-900/40 hover:bg-slate-900/60 transition-colors">
      <CardContent className="p-5 flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colorClass} bg-opacity-10 border border-current border-opacity-20`}>
          <Icon className="h-5 w-5 opacity-90" />
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">{title}</p>
          <p className="text-2xl font-bold tracking-tight text-slate-100 mt-0.5">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const { apiFetch } = useAuth();
  const { isRunning, imageSrc, count, fps, confidence, sessionDuration, productCounts } = useSession();
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await apiFetch(`${API_PREFIX}/dashboard/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats(data.stats);
        }
      } catch (err) {}
    };
    fetchStats();
  }, [apiFetch, isRunning]);

  const productRows = useMemo(
    () => Object.entries(productCounts || {}).sort((a, b) => b[1] - a[1]),
    [productCounts]
  );

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Live Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">Real-time object detection and inspection metrics.</p>
        </div>
        <div className="flex gap-3">
          {isRunning ? (
            <Badge variant="success" className="animate-pulse shadow-[0_0_15px_rgba(16,185,129,0.3)] px-3 py-1">
              <Activity className="h-3.5 w-3.5 mr-1" /> ACTIVE FEED
            </Badge>
          ) : (
            <Badge variant="secondary" className="px-3 py-1 text-slate-400 border border-slate-700">
              <StopCircle className="h-3.5 w-3.5 mr-1" /> SYSTEM IDLE
            </Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Sessions" value={stats?.total_sessions ?? 0} icon={Layers} colorClass="text-cyan-400" />
        <MetricCard title="Cumulative Count" value={stats?.total_count ?? 0} icon={ListTree} colorClass="text-indigo-400" />
        <MetricCard title="Today's Ops" value={stats?.today_sessions ?? 0} icon={Activity} colorClass="text-emerald-400" />
        <MetricCard 
          title="Session State" 
          value={isRunning ? "Live" : "Idle"} 
          icon={isRunning ? PlayCircle : StopCircle} 
          colorClass={isRunning ? "text-emerald-400" : "text-amber-400"} 
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main Feed */}
        <Card className="xl:col-span-2 border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden flex flex-col">
          <CardHeader className="border-b border-slate-800/60 bg-slate-900/80 py-4 px-5">
            <div className="flex items-center gap-2 text-cyan-400">
              <Video className="h-4 w-4" />
              <CardTitle className="text-base font-medium">Live Video Stream</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0 flex-1 relative min-h-[400px] bg-black flex items-center justify-center group">
            {isRunning && imageSrc ? (
              <img src={imageSrc} alt="Live feed" className="w-full h-full object-contain" />
            ) : (
              <div className="text-center p-8 space-y-4">
                <div className="mx-auto w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600 mb-4">
                  <Video className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-medium text-slate-300">Camera Offline</h3>
                <p className="text-sm text-slate-500 max-w-sm">No active session is running. Navigate to Session Setup to configure and start stream.</p>
                <div className="pt-4">
                  <button onClick={() => navigate('/setup')} className="text-sm font-medium text-cyan-400 hover:text-cyan-300 transition-colors">
                    Go to Session Setup → 
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Live Analytics Panel */}
        <div className="space-y-6 flex flex-col">
          <Card className="flex-none border-slate-800/80 bg-slate-900/60 shadow-lg relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/5 rounded-full blur-3xl" />
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Real-Time Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6 mt-2">
                <div>
                  <div className="flex justify-between items-end mb-1">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Global Count</span>
                    <span className="text-3xl font-bold text-cyan-400 tabular-nums">{count}</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 w-full animate-[pulse_2s_ease-in-out_infinite]" style={{ transformOrigin: 'left', transform: isRunning ? 'scaleX(1)' : 'scaleX(0)', transition: 'transform 1s ease' }} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg border border-slate-800/50 bg-slate-950/50">
                    <span className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Processing Speed</span>
                    <span className="text-xl font-semibold text-slate-200 tabular-nums">{fps.toFixed(1)} <span className="text-xs text-slate-500 font-normal">fps</span></span>
                  </div>
                  <div className="p-3 rounded-lg border border-slate-800/50 bg-slate-950/50">
                    <span className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Inference Conf</span>
                    <span className="text-xl font-semibold text-slate-200 tabular-nums">{(confidence * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="flex-1 flex flex-col border-slate-800/80 bg-slate-900/60 shadow-lg">
            <CardHeader className="pb-3 border-b border-slate-800/40">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-slate-200">Product Breakdown</CardTitle>
                <Badge variant="secondary" className="font-mono text-[10px]">{productRows.length} classes</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 overflow-auto">
              <div className="divide-y divide-slate-800/40">
                {productRows.length > 0 ? (
                  productRows.map(([name, productCount]) => (
                    <div key={name} className="flex justify-between items-center p-4 hover:bg-slate-800/30 transition-colors group">
                      <div className="flex items-center gap-3">
                        <div className="h-2 w-2 rounded-full bg-cyan-500 group-hover:shadow-[0_0_8px_rgba(6,182,212,0.6)] transition-shadow" />
                        <span className="text-sm font-medium text-slate-300">{name}</span>
                      </div>
                      <span className="text-sm font-bold text-slate-100 bg-slate-800 px-2.5 py-1 rounded-md">{productCount}</span>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center text-sm text-slate-500">
                    No products detected.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
