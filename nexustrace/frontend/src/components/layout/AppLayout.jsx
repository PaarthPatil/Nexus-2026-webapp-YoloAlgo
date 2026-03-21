import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function AppLayout() {
  return (
    <div className="flex h-screen w-full bg-[#0b1220] text-slate-100 overflow-hidden font-sans selection:bg-cyan-900/50">
      <Sidebar />
      <div className="flex-1 flex flex-col relative overflow-hidden">
        {/* Ambient subtle glow background */}
        <div className="absolute top-0 left-1/4 w-[500px] h-[300px] bg-cyan-900/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
        
        <Header />
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-[#0b1220] p-6 lg:p-8 relative z-10 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
          <div className="max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
