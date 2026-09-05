import React from "react";
import { ShieldCheck, Layers, Building2, UserCircle2, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export function Navbar() {
  const { user, activeMerchant, merchants, setActiveMerchantId, signOut } = useAuth();

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center space-x-3">
        <div className="h-8 w-8 rounded bg-teal-600/20 border border-teal-500/30 flex items-center justify-center text-teal-400">
          <Layers className="h-5 w-5" />
        </div>
        <div>
          <span className="font-bold tracking-tight text-white text-lg">RecoveryOS</span>
          <span className="ml-2 text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            CONTROL PLANE
          </span>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Merchant Selector */}
        {activeMerchant && (
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded border border-slate-800">
            <Building2 className="h-3.5 w-3.5 text-teal-400" />
            <select
              value={activeMerchant.id}
              onChange={(e) => setActiveMerchantId(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
              aria-label="Active Merchant"
            >
              {merchants.map((m) => (
                <option key={m.id} value={m.id} className="bg-slate-900 text-slate-200">
                  {m.name} ({m.role})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* User Identity or Policy Badge */}
        {user ? (
          <div className="flex items-center space-x-2 text-xs text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded border border-slate-800">
            <UserCircle2 className="h-3.5 w-3.5 text-teal-400" />
            <span className="font-mono">{user.email || user.id.slice(0, 12)}</span>
            <button
              onClick={signOut}
              title="Sign Out"
              className="ml-2 text-slate-400 hover:text-rose-400 transition-colors"
            >
              <LogOut className="h-3 w-3" />
            </button>
          </div>
        ) : (
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2.5 py-1 rounded">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span className="font-medium">Phase 3 RBAC Enforced</span>
          </div>
        )}
      </div>
    </header>
  );
}

