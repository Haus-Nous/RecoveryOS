import React from "react";
import {
  LayoutDashboard,
  AlertTriangle,
  Briefcase,
  GitFork,
  Cpu,
  Scale,
  FileCheck2,
  FileSearch,
} from "lucide-react";

export type NavTab =
  | "overview"
  | "revenue_at_risk"
  | "recovery_cases"
  | "payment_journeys"
  | "strategies"
  | "reconciliation"
  | "policies"
  | "audit";

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

const NAV_ITEMS: Array<{ id: NavTab; label: string; icon: React.ElementType }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "revenue_at_risk", label: "Revenue at Risk", icon: AlertTriangle },
  { id: "recovery_cases", label: "Recovery Cases", icon: Briefcase },
  { id: "payment_journeys", label: "Payment Journeys", icon: GitFork },
  { id: "strategies", label: "Strategies", icon: Cpu },
  { id: "reconciliation", label: "Reconciliation", icon: Scale },
  { id: "policies", label: "Policies", icon: FileCheck2 },
  { id: "audit", label: "Audit", icon: FileSearch },
];

export function Sidebar({ currentTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950 min-h-[calc(100vh-4rem)] p-4 flex flex-col justify-between">
      <nav className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          OPERATIONS CONSOLE
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-teal-950/60 text-teal-300 border border-teal-800/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-teal-400" : "text-slate-400"}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="pt-4 border-t border-slate-900 text-xs text-slate-400 space-y-1 px-3 font-mono">
        <p>RecoveryOS v0.1.0</p>
        <p className="text-[10px] text-slate-400">Deterministic Engine</p>
      </div>
    </aside>
  );
}
