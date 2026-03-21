import React, { forwardRef } from 'react';
import { cn } from '../lib/utils';
import { ChevronDown } from 'lucide-react';

export const Select = forwardRef(({ className, label, options, error, ...props }, ref) => {
  return (
    <div className="w-full relative">
      {label && (
        <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-medium">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          className={cn(
            "flex h-9 w-full appearance-none rounded-md border border-slate-700 bg-slate-950/50 px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 disabled:cursor-not-allowed disabled:opacity-50 text-slate-100",
            error && "border-red-500/50 focus-visible:ring-red-500",
            className
          )}
          ref={ref}
          {...props}
        >
          {options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label || opt.value}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 opacity-50">
          <ChevronDown className="h-4 w-4" />
        </div>
      </div>
      {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
    </div>
  );
});
Select.displayName = "Select";
