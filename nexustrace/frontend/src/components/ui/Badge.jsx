import React from 'react';
import { cn } from '../lib/utils';

export function Badge({ className, variant = 'default', children, ...props }) {
  const baseStyles = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2";
  
  const variants = {
    default: "border-transparent bg-cyan-600 outline-none text-white hover:bg-cyan-700 shadow-sm",
    secondary: "border-transparent bg-slate-800 text-slate-100 hover:bg-slate-700",
    destructive: "border-transparent bg-red-600 text-white hover:bg-red-700",
    outline: "text-slate-300 border-slate-700",
    success: "border-transparent bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
    warning: "border-transparent bg-amber-600 text-white hover:bg-amber-700 shadow-sm"
  };

  return (
    <div className={cn(baseStyles, variants[variant], className)} {...props}>
      {children}
    </div>
  );
}
