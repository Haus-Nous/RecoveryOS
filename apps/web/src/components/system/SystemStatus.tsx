"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  RefreshCw,
  Database,
  Server,
  Radio,
  Clock,
  AlertOctagon,
} from "lucide-react";
import {
  checkFullSystemStatus,
  SystemHealthState,
} from "@/lib/api-client";

interface SystemStatusProps {
  initialAutoPoll?: boolean;
}

export function SystemStatus({ initialAutoPoll = false }: SystemStatusProps) {
  const [state, setState] = useState<SystemHealthState>({
    isChecking: true,
    isHealthy: false,
    healthData: null,
    readinessData: null,
    errorMessage: null,
    lastChecked: null,
    latencyMs: null,
  });

  const [autoPoll, setAutoPoll] = useState(initialAutoPoll);

  const checkStatus = useCallback(async () => {
    setState((prev) => ({ ...prev, isChecking: true }));
    try {
      const { health, readiness, latencyMs } = await checkFullSystemStatus();
      const isHealthy =
        health.status === "ok" &&
        readiness.status === "ready" &&
        readiness.dependencies.postgres === "connected" &&
        readiness.dependencies.redis === "connected";

      setState({
        isChecking: false,
        isHealthy,
        healthData: health,
        readinessData: readiness,
        errorMessage: isHealthy ? null : (readiness.errors?.[0] || "System dependencies degraded"),
        lastChecked: new Date(),
        latencyMs,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect to RecoveryOS API";
      setState({
        isChecking: false,
        isHealthy: false,
        healthData: null,
        readinessData: null,
        errorMessage: message,
        lastChecked: new Date(),
        latencyMs: null,
      });
    }
  }, []);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  useEffect(() => {
    if (!autoPoll) return;
    const interval = setInterval(() => {
      checkStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [autoPoll, checkStatus]);

  const postgresStatus = state.readinessData?.dependencies?.postgres || "unknown";
  const redisStatus = state.readinessData?.dependencies?.redis || "unknown";

  return (
    <div
      data-testid="system-status-card"
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-sm backdrop-blur"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div className="flex items-center space-x-3">
          <div
            className={`h-10 w-10 rounded-lg flex items-center justify-center ${
              state.isChecking
                ? "bg-amber-950/40 border border-amber-800/40 text-amber-400"
                : state.isHealthy
                ? "bg-emerald-950/50 border border-emerald-800/40 text-emerald-400"
                : "bg-rose-950/50 border border-rose-800/40 text-rose-400"
            }`}
          >
            {state.isChecking ? (
              <RefreshCw className="h-5 w-5 animate-spin" />
            ) : state.isHealthy ? (
              <CheckCircle2 className="h-5 w-5" />
            ) : (
              <XCircle className="h-5 w-5" />
            )}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-white">System Runtime & Readiness</h2>
              <span
                data-testid="status-badge"
                className={`text-xs px-2 py-0.5 rounded-full font-mono font-medium ${
                  state.isChecking
                    ? "bg-amber-950 text-amber-300 border border-amber-800/60"
                    : state.isHealthy
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800/60"
                    : "bg-rose-950 text-rose-300 border border-rose-800/60"
                }`}
              >
                {state.isChecking
                  ? "CHECKING"
                  : state.isHealthy
                  ? "SYSTEM OPERATIONAL"
                  : "SERVICE DEGRADED"}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Live verification against FastAPI backend, PostgreSQL 16, and Redis 7
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setAutoPoll(!autoPoll)}
            className={`text-xs px-2.5 py-1.5 rounded border transition-colors ${
              autoPoll
                ? "bg-teal-950/80 text-teal-300 border-teal-800"
                : "bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-300"
            }`}
          >
            Auto-Poll: {autoPoll ? "ON (10s)" : "OFF"}
          </button>
          <button
            data-testid="refresh-button"
            onClick={checkStatus}
            disabled={state.isChecking}
            className="flex items-center space-x-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-3.5 py-1.5 rounded-lg text-xs font-medium border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${state.isChecking ? "animate-spin" : ""}`} />
            <span>{state.isHealthy ? "Refresh Status" : "Retry Connection"}</span>
          </button>
        </div>
      </div>

      {/* Dependency Matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
        {/* API Process */}
        <div
          data-testid="api-card"
          className="rounded-lg bg-slate-950/60 border border-slate-800/80 p-4 space-y-2"
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center space-x-2">
              <Server className="h-4 w-4 text-slate-400" />
              <span className="font-medium text-slate-300">FastAPI Process</span>
            </div>
            <span
              className={`font-mono text-[11px] px-1.5 py-0.5 rounded ${
                state.healthData?.status === "ok"
                  ? "text-emerald-400 bg-emerald-950/60 border border-emerald-800/40"
                  : "text-rose-400 bg-rose-950/60 border border-rose-800/40"
              }`}
            >
              {state.healthData?.status || "UNREACHABLE"}
            </span>
          </div>
          <div className="text-xs font-mono text-slate-400">
            Endpoint: <code className="text-slate-300">GET /health</code>
          </div>
        </div>

        {/* PostgreSQL */}
        <div
          data-testid="postgres-card"
          className="rounded-lg bg-slate-950/60 border border-slate-800/80 p-4 space-y-2"
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center space-x-2">
              <Database className="h-4 w-4 text-slate-400" />
              <span className="font-medium text-slate-300">PostgreSQL (SQLAlchemy)</span>
            </div>
            <span
              className={`font-mono text-[11px] px-1.5 py-0.5 rounded ${
                postgresStatus === "connected"
                  ? "text-emerald-400 bg-emerald-950/60 border border-emerald-800/40"
                  : "text-rose-400 bg-rose-950/60 border border-rose-800/40"
              }`}
            >
              {postgresStatus.toUpperCase()}
            </span>
          </div>
          <div className="text-xs font-mono text-slate-400">
            Engine: <code className="text-slate-300">asyncpg / pool_pre_ping</code>
          </div>
        </div>

        {/* Redis */}
        <div
          data-testid="redis-card"
          className="rounded-lg bg-slate-950/60 border border-slate-800/80 p-4 space-y-2"
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center space-x-2">
              <Radio className="h-4 w-4 text-slate-400" />
              <span className="font-medium text-slate-300">Redis Cache & Bus</span>
            </div>
            <span
              className={`font-mono text-[11px] px-1.5 py-0.5 rounded ${
                redisStatus === "connected"
                  ? "text-emerald-400 bg-emerald-950/60 border border-emerald-800/40"
                  : "text-rose-400 bg-rose-950/60 border border-rose-800/40"
              }`}
            >
              {redisStatus.toUpperCase()}
            </span>
          </div>
          <div className="text-xs font-mono text-slate-400">
            Client: <code className="text-slate-300">redis-py async / PING</code>
          </div>
        </div>
      </div>

      {/* Error Banner when degraded */}
      {state.errorMessage && (
        <div
          data-testid="error-banner"
          className="mt-4 rounded-lg bg-rose-950/40 border border-rose-800/50 p-3.5 flex items-start space-x-3 text-xs text-rose-300"
        >
          <AlertOctagon className="h-4 w-4 text-rose-400 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold text-rose-200">Dependency Connection Fault</p>
            <p className="font-mono text-rose-300/90">{state.errorMessage}</p>
          </div>
        </div>
      )}

      {/* Diagnostic telemetry */}
      <div className="mt-4 pt-4 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400 font-mono">
        <div className="flex items-center space-x-4">
          <span className="flex items-center space-x-1.5">
            <Clock className="h-3.5 w-3.5 text-slate-400" />
            <span>
              Last Checked:{" "}
              {state.lastChecked
                ? state.lastChecked.toLocaleTimeString()
                : "Never"}
            </span>
          </span>
          {state.latencyMs !== null && (
            <span>Roundtrip Latency: {state.latencyMs}ms</span>
          )}
        </div>
        <div>Service: recoveryos-api</div>
      </div>
    </div>
  );
}
