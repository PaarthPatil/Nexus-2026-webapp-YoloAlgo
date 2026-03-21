import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlaySquare, History, Settings, Box } from 'lucide-react';

const NAV_ITEMS = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Session Setup', path: '/setup', icon: PlaySquare },
  { name: 'History', path: '/history', icon: History },
  { name: 'Settings', path: '/settings', icon: Settings }
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-slate-800/60 bg-slate-950/80 p-4 flex flex-col backdrop-blur-md">
      <div className="mb-8 flex items-center gap-3 px-2 mt-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400">
          <Box className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-wide text-slate-100">NexusTrace</h1>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">Warehouse AI</p>
        </div>
      </div>
      
      <nav className="space-y-1 flex-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-cyan-900/40 text-cyan-300 border border-cyan-800/50 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]'
                    : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {item.name}
            </NavLink>
          );
        })}
      </nav>
      
      <div className="mt-auto px-3 py-4 rounded-xl bg-slate-900/50 border border-slate-800 flex items-center gap-3">
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-900/50 border border-indigo-700/50 text-indigo-300">
          <span className="text-xs font-bold">OP</span>
          <div className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-slate-950"></div>
        </div>
        <div className="flex flex-col overflow-hidden">
          <span className="text-xs font-medium text-slate-200 truncate">System Online</span>
          <span className="text-[10px] text-slate-500 truncate">WebSocket Connected</span>
        </div>
      </div>
    </aside>
  );
}
