import React from 'react';
import { cn } from '../../lib/utils';
import { Loader2 } from 'lucide-react';

export function Button({ 
  className, 
  variant = 'default', 
  size = 'default', 
  isLoading, 
  children, 
  disabled, 
  ...props 
}) {
  const baseStyles = "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    default: "bg-cyan-600 text-white hover:bg-cyan-700 shadow-sm shadow-cyan-900/20",
    destructive: "bg-red-600 text-white hover:bg-red-700 shadow-sm shadow-red-900/20",
    outline: "border border-slate-700 bg-transparent hover:bg-slate-800 text-slate-100",
    secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700",
    ghost: "hover:bg-slate-800 hover:text-slate-100 text-slate-300",
    link: "text-cyan-400 underline-offset-4 hover:underline",
  };

  const sizes = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-md px-3 text-xs",
    lg: "h-10 rounded-md px-8",
    icon: "h-9 w-9",
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}
