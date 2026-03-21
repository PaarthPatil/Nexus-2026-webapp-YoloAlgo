import React from 'react';
import { cn } from '../lib/utils';

export function Card({ className, ...props }) {
  return (
    <div className={cn("rounded-xl border border-slate-800/60 bg-slate-900/50 text-slate-100 shadow-sm backdrop-blur-sm", className)} {...props} />
  );
}

export function CardHeader({ className, ...props }) {
  return (
    <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  );
}

export function CardTitle({ className, ...props }) {
  return (
    <h3 className={cn("font-semibold leading-none tracking-tight text-white", className)} {...props} />
  );
}

export function CardDescription({ className, ...props }) {
  return (
    <p className={cn("text-sm text-slate-400", className)} {...props} />
  );
}

export function CardContent({ className, ...props }) {
  return (
    <div className={cn("p-6 pt-0", className)} {...props} />
  );
}

export function CardFooter({ className, ...props }) {
  return (
    <div className={cn("flex items-center p-6 pt-0", className)} {...props} />
  );
}
