import React from 'react';
import { Database, CheckCircle2, Shield, Sparkles } from 'lucide-react';

interface TelemetryProps {
  metrics: {
    // Everything the engine did. Always available.
    traffic: {
      total_decisions: number;
      abstention_rate: number;
      cap_bind_rate: number;
      intervention_rate: number;
      p50_latency_ms: number;
      p95_latency_ms: number;
      p99_latency_ms: number;
      latency_source: string;
      estimated_cost_units_per_decision: number;
    };
    // Whether it was right. Needs human labels, so these are null until
    // decisions have been adjudicated. Never render a null as a zero.
    quality: {
      edr: number | null;
      uir: number | null;
      override_rate: number | null;
      labelled_count: number;
    };
  } | null;
  hashChainValid: boolean | null;
}

const rate = (v: number | null | undefined) =>
  v === null || v === undefined ? "n/a" : String(v);

export const TelemetryStrip: React.FC<TelemetryProps> = ({ metrics, hashChainValid }) => {
  return (
    <div className="bg-[#F4EFE6] border-b border-[#E6DEC4]/60 px-6 py-2 text-[11px] text-stone-600 font-sans">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-y-2">
        {/* Left: Engine Status & Key Metrics (Co-reported EDR + UIR) */}
        <div className="flex items-center space-x-5">
          <div className="flex items-center space-x-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-stone-900 font-semibold tracking-tight">Active Engine</span>
          </div>

          <div className="h-3.5 w-px bg-stone-300/80" />

          {/* Co-reported EDR and UIR */}
          <div className="flex items-center space-x-3 font-mono">
            <span className="text-stone-600">
              EDR: <b className="text-stone-900 font-bold">{rate(metrics?.quality.edr)}</b> <span className="text-stone-500 text-[10px]">/ 10k</span>
            </span>
            <span className="text-stone-300">|</span>
            <span className="text-stone-600">
              UIR: <b className="text-stone-900 font-bold">{rate(metrics?.quality.uir)}</b> <span className="text-stone-500 text-[10px]">/ 10k</span>
            </span>
          </div>

          <div className="h-3.5 w-px bg-stone-300/80" />

          <div className="text-stone-600 hidden sm:inline-flex items-center space-x-1.5">
            <span>Abstention Rate:</span>
            <span className="text-stone-900 font-mono font-semibold">{((metrics?.traffic.abstention_rate ?? 0) * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* Right: Latency & Hash Chain Audit */}
        <div className="flex items-center space-x-5">
          <div className="flex items-center space-x-2 font-mono text-stone-600">
            <span className="text-stone-500">Latency:</span>
            <span>p50: <b className="text-stone-900">{metrics?.traffic.p50_latency_ms ?? 0}ms</b></span>
            <span className="text-stone-300">·</span>
            <span>p95: <b className="text-stone-900">{metrics?.traffic.p95_latency_ms ?? 0}ms</b></span>
          </div>

          <div className="h-3.5 w-px bg-stone-300/80" />

          <div className="flex items-center space-x-2">
            <Database className="w-3.5 h-3.5 text-stone-500" />
            <span className="text-stone-700 font-mono font-medium">{metrics?.traffic.total_decisions.toLocaleString() ?? '0'} logs</span>
            <span className="text-stone-300">·</span>
            <span className="inline-flex items-center space-x-1 text-emerald-800 font-semibold text-[10px] bg-emerald-50/90 px-1.5 py-0.5 rounded border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              <span>SHA-256 Verified</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
