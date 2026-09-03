import React from "react";
import { Info, Shield, Layers } from "lucide-react";

interface PlaceholderViewProps {
  title: string;
  subtitle: string;
  badge: string;
  reason: string;
  plannedPhase: string;
}

export function PlaceholderView({
  title,
  subtitle,
  badge,
  reason,
  plannedPhase,
}: PlaceholderViewProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center max-w-2xl mx-auto my-8 space-y-6">
      <div className="h-12 w-12 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto text-slate-400">
        <Layers className="h-6 w-6" />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-center space-x-2">
          <h2 className="text-xl font-bold text-white tracking-tight">{title}</h2>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            {badge}
          </span>
        </div>
        <p className="text-sm text-slate-400">{subtitle}</p>
      </div>

      <div className="rounded-lg bg-slate-950/80 border border-slate-800 p-4 text-left space-y-2 text-xs font-mono text-slate-300">
        <div className="flex items-center space-x-2 text-amber-400">
          <Info className="h-4 w-4 shrink-0" />
          <span className="font-semibold">Honest State: {reason}</span>
        </div>
        <p className="text-slate-400 pl-6">
          Phase 0 establishes foundational architecture only. Financial domain logic, payment
          entities, and telemetry streams will be scaffolded in {plannedPhase}.
        </p>
      </div>

      <div className="text-xs text-slate-400 flex items-center justify-center space-x-2">
        <Shield className="h-3.5 w-3.5 text-teal-400" />
        <span>Architectural Invariant: AI Proposes · Policy Authorizes · Infrastructure Executes · Ledger Verifies</span>
      </div>
    </div>
  );
}
