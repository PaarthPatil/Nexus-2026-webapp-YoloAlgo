import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { useSession } from '../../context/SessionContext';
import { LogOut, Activity, Clock } from 'lucide-react';
import { Button } from '../ui/Button';

const formatDuration = (seconds) => {
  const total = Number(seconds || 0);
  const hh = String(Math.floor(total / 3600)).padStart(2, '0');
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  if (hh === '00') return `${mm}:${ss}`;
  return `${hh}:${mm}:${ss}`;
};

export function Header() {
  const { currentUser, logout } = useAuth();
  const { isRunning, sessionDuration, operatorId, batchId } = useSession();

  return (
    <header className="h-16 border-b border-slate-800/60 bg-slate-950/40 px-6 flex items-center justify-between backdrop-blur-md sticky top-0 z-40">
      <div className="flex items-center gap-6">
        {/* Status Indicator */}
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            {isRunning && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isRunning ? 'bg-emerald-500' : 'bg-slate-600'}`}></span>
          </span>
          <span className={`text-sm font-semibold tracking-wide ${isRunning ? 'text-emerald-400' : 'text-slate-400'}`}>
            {isRunning ? 'LIVE SESSION' : 'SYSTEM IDLE'}
          </span>
        </div>

        {/* Live Metrics (Only visible if running) */}
        {isRunning && (
          <div className="flex items-center gap-4 border-l border-slate-800 pl-4">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Clock className="h-3.5 w-3.5" />
              <span className="font-mono text-slate-200">{formatDuration(sessionDuration)}</span>
            </div>
            {(operatorId || batchId) && (
              <div className="flex items-center gap-3 text-xs">
                {operatorId && <span>Operator: <strong className="text-slate-200 font-medium">{operatorId}</strong></span>}
                {batchId && <span>Batch: <strong className="text-slate-200 font-medium">{batchId}</strong></span>}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right hidden sm:block">
          <p className="text-xs font-medium text-slate-200">{currentUser?.username || 'User'}</p>
          <p className="text-[10px] text-slate-500">Administrator</p>
        </div>
        <Button variant="ghost" size="icon" onClick={logout} title="Logout" className="hover:text-red-400 hover:bg-red-950/30">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
