"use client";

import React, { useState } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar, NavTab } from "@/components/layout/Sidebar";
import { SystemStatus } from "@/components/system/SystemStatus";
import { PlaceholderView } from "@/components/views/Placeholders";
import {
  ShieldAlert,
  ShieldCheck,
  Zap,
  Lock,
  FileSpreadsheet,
} from "lucide-react";

export default function Home() {
  const [currentTab, setCurrentTab] = useState<NavTab>("overview");

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar />

      <div className="flex-1 flex flex-col md:flex-row">
        <Sidebar currentTab={currentTab} onTabChange={setCurrentTab} />

        <main className="flex-1 p-6 md:p-8 max-w-7xl overflow-y-auto space-y-8">
          {currentTab === "overview" && (
            <>
              {/* Header Hero */}
              <div className="space-y-3">
                <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-teal-950/80 border border-teal-800/60 text-xs font-mono text-teal-300">
                  <Zap className="h-3.5 w-3.5 text-teal-400" />
                  <span>Razorpay AI Buildathon — AI Revenue Recovery Track</span>
                </div>
                <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white">
                  RecoveryOS
                </h1>
                <p className="text-lg text-slate-300 font-medium max-w-3xl">
                  Payment Reliability & Revenue Recovery Control Plane
                </p>
                <p className="text-sm text-slate-400 max-w-2xl">
                  Autonomous diagnostic intelligence with deterministic policy guardrails to intercept,
                  diagnose, authorize, execute, and reconcile lost e-commerce and SaaS revenue.
                </p>
              </div>

              {/* Invariant Banner */}
              <div className="rounded-xl border border-teal-900/50 bg-gradient-to-r from-teal-950/40 via-slate-900/60 to-slate-950 p-5 shadow-sm">
                <div className="text-xs font-mono uppercase tracking-wider text-teal-400 mb-2 font-semibold">
                  Architectural Invariant (Non-Negotiable)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
                  <div className="flex items-center space-x-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                    <Zap className="h-4 w-4 text-teal-400 shrink-0" />
                    <div>
                      <div className="font-bold text-white uppercase">AI Proposes</div>
                      <div className="text-slate-400 text-[11px]">Recovery plans & strategies</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                    <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
                    <div>
                      <div className="font-bold text-white uppercase">Policy Authorizes</div>
                      <div className="text-slate-400 text-[11px]">Deterministic rule engine</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                    <Lock className="h-4 w-4 text-blue-400 shrink-0" />
                    <div>
                      <div className="font-bold text-white uppercase">Infra Executes</div>
                      <div className="text-slate-400 text-[11px]">Idempotent execution engine</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                    <FileSpreadsheet className="h-4 w-4 text-indigo-400 shrink-0" />
                    <div>
                      <div className="font-bold text-white uppercase">Ledger Verifies</div>
                      <div className="text-slate-400 text-[11px]">Double-entry reconciliation</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Live System Status Section */}
              <section className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-white tracking-tight">
                    Runtime Infrastructure Status
                  </h2>
                  <span className="text-xs font-mono text-slate-400">Phase 0 Foundation</span>
                </div>

                <SystemStatus initialAutoPoll={false} />
              </section>

              {/* Honest Setup Notice */}
              <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-6 space-y-3">
                <div className="flex items-center space-x-2 text-slate-200 font-semibold text-sm">
                  <ShieldAlert className="h-4 w-4 text-teal-400" />
                  <span>Phase 0 Verified Environment Active</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  The monorepo, FastAPI backend, PostgreSQL 16, Redis 7, Alembic migration harness, and Next.js frontend are running in verified local development mode. No financial domain entities or simulated numbers are active in Phase 0.
                </p>
              </section>
            </>
          )}

          {currentTab === "revenue_at_risk" && (
            <PlaceholderView
              title="Revenue at Risk"
              subtitle="Real-time loss detection and recoverable volume analytics."
              badge="PHASE 8"
              reason="No recovery data yet"
              plannedPhase="Phase 8 (Revenue-Loss Detection)"
            />
          )}

          {currentTab === "recovery_cases" && (
            <PlaceholderView
              title="Recovery Cases"
              subtitle="Active investigation and autonomous remediation workflows."
              badge="PHASE 1"
              reason="No recovery data yet"
              plannedPhase="Phase 1 (Domain Model & Financial State Machines)"
            />
          )}

          {currentTab === "payment_journeys" && (
            <PlaceholderView
              title="Payment Journeys"
              subtitle="End-to-end timeline reconstruction across payment gateway events."
              badge="PHASE 7"
              reason="Provider integration not configured"
              plannedPhase="Phase 7 (Payment Journey Engine)"
            />
          )}

          {currentTab === "strategies" && (
            <PlaceholderView
              title="Recovery Strategies"
              subtitle="Contextual intelligence for optimal recovery routing."
              badge="PHASE 9"
              reason="System setup in progress"
              plannedPhase="Phase 9 (Recovery Intelligence)"
            />
          )}

          {currentTab === "reconciliation" && (
            <PlaceholderView
              title="Reconciliation"
              subtitle="Audit ledger verifying recovered capital against bank payouts."
              badge="PHASE 12"
              reason="No recovery data yet"
              plannedPhase="Phase 12 (Outcome & Reconciliation)"
            />
          )}

          {currentTab === "policies" && (
            <PlaceholderView
              title="Deterministic Policies"
              subtitle="Strict merchant guardrails authorizing automated recovery actions."
              badge="PHASE 10"
              reason="System setup in progress"
              plannedPhase="Phase 10 (Policy & Authorization Engine)"
            />
          )}

          {currentTab === "audit" && (
            <PlaceholderView
              title="Audit & Compliance Log"
              subtitle="Immutable event trace recording every proposal, authorization, and execution."
              badge="PHASE 14"
              reason="System setup in progress"
              plannedPhase="Phase 14 (Auditability & Observability)"
            />
          )}
        </main>
      </div>
    </div>
  );
}
