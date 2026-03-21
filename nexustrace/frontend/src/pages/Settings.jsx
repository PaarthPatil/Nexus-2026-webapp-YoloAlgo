import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';

export function Settings() {
  return (
    <div className="max-w-3xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">System Parameters</h1>
        <p className="text-sm text-slate-400 mt-1">Global administrative configurations and database maintenance.</p>
      </div>

      <Card className="border-slate-800/80 bg-slate-900/60 shadow-lg">
        <CardHeader className="border-b border-slate-800/40">
          <CardTitle className="text-lg">Storage Management</CardTitle>
          <CardDescription>Configure telemetry data and video retention limits.</CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <p className="text-sm text-amber-500 bg-amber-950/30 border border-amber-900/50 p-4 rounded-lg">
            Administative options are locked by the local orchestrator for this node deployed locally. Consult central server to purge persistent records.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
