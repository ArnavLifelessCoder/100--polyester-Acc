import React, { useState, useEffect } from 'react';
import { Shield, ArrowRight, Layers, Sliders, FileSearch, MessageSquare, Database, Play, CheckCircle2, Lock, Cpu, Sparkles, TrendingDown, Scale, Activity } from 'lucide-react';

interface LandingPageProps {
  onLaunchConsole: (tab?: string) => void;
}

// Fallbacks for the first paint and for a cold API. They are the modelled tier
// budgets from constants.py, not invented figures, so the page is never wrong
// even before /v1/metrics answers.
const FALLBACK = {
  costPct: 3.5,
  p50: 12 + 90,
  p99: 12 + 90 + 450,
  tier0: 1.0,
  tier1: 1.0,
  tier2: 0.09,
  decisions: 3000,
};

export const LandingPage: React.FC<LandingPageProps> = ({ onLaunchConsole }) => {
  // Every headline number below is read from the running engine. Hardcoding
  // them is how a landing page ends up claiming a 2ms tier that now costs 12ms
  // and an 8% tier that now runs on everything.
  const [live, setLive] = useState(FALLBACK);

  useEffect(() => {
    fetch('/v1/metrics')
      .then((r) => r.json())
      .then((m) => {
        const t = m?.traffic;
        if (!t) return;
        setLive({
          costPct: Number((t.estimated_cost_units_per_decision * 100).toFixed(1)),
          p50: t.p50_latency_ms,
          p99: t.p99_latency_ms,
          tier0: t.tier_fire_rate?.tier0 ?? FALLBACK.tier0,
          tier1: t.tier_fire_rate?.tier1 ?? FALLBACK.tier1,
          tier2: t.tier_fire_rate?.tier2 ?? FALLBACK.tier2,
          decisions: t.total_decisions ?? FALLBACK.decisions,
        });
      })
      .catch(() => {
        /* keep the fallbacks; the page must render without an API */
      });
  }, []);

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 flex flex-col font-sans selection:bg-amber-100 selection:text-amber-900 animate-fade-in">
      {/* Top Navigation */}
      <nav className="border-b border-[#EAE2D4] bg-[#FFFDF9]/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-stone-900 flex items-center justify-center shadow-sm">
              <Shield className="w-4 h-4 text-amber-400" />
            </div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-base tracking-tight text-stone-900">
                ControlPlane<span className="text-amber-700 font-semibold">.ai</span>
              </span>
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                Round 2 Prototype
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-6">
            <div className="hidden md:flex items-center space-x-5 text-xs font-semibold text-stone-600">
              <a href="#problem" className="hover:text-stone-900 transition">The Core Theorem</a>
              <a href="#architecture" className="hover:text-stone-900 transition">3-Tier Cascade</a>
              <a href="#features" className="hover:text-stone-900 transition">Decision Engine</a>
              <a href="#ledger" className="hover:text-stone-900 transition">Audit Ledger</a>
            </div>

            <button
              onClick={() => onLaunchConsole('screen0')}
              className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold tracking-wide transition-all shadow-sm flex items-center space-x-1.5"
            >
              <span>Launch Console</span>
              <ArrowRight className="w-3.5 h-3.5 text-amber-400" />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 px-6 max-w-7xl mx-auto flex flex-col items-center text-center">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[#F3ECE0] border border-[#E2D8C6] text-xs font-semibold text-stone-800 mb-6 shadow-sm">
          <Sparkles className="w-3.5 h-3.5 text-amber-700" />
          <span>Consequence-Aware AI Intervention Layer</span>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-stone-900 tracking-tight max-w-4xl leading-[1.12]">
          Treat Model Outputs as <span className="text-amber-800 underline decoration-amber-300 decoration-4 underline-offset-4">Proposals to Adjudicate</span>, Not Artifacts to Observe.
        </h1>

        <p className="mt-6 text-base sm:text-lg text-stone-600 max-w-2xl leading-relaxed">
          Traditional guardrails rely on static global thresholds that trade false alarms against escaped risks.
          ControlPlane derives optimal per-workflow interventions mathematically via <b>constrained expected loss minimisation</b>.
        </p>

        {/* Hero CTA Buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={() => onLaunchConsole('screen0')}
            className="px-6 py-3.5 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-sm font-bold tracking-wide transition-all shadow-md flex items-center space-x-2"
          >
            <span>Explore Interactive Demos</span>
            <ArrowRight className="w-4 h-4 text-amber-400" />
          </button>
          <button
            onClick={() => onLaunchConsole('playground')}
            className="px-6 py-3.5 bg-white hover:bg-[#FAF5EC] text-stone-800 border border-[#D9CEBA] rounded-xl text-sm font-semibold transition-all shadow-sm flex items-center space-x-2"
          >
            <Play className="w-4 h-4 text-amber-700 fill-current" />
            <span>Open Live Playground</span>
          </button>
        </div>

        {/* Key Metrics Banner */}
        <div className="mt-14 w-full grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl text-left">
          <div className="surface-card p-4 rounded-xl border border-[#EAE2D4]">
            <span className="text-[11px] font-semibold text-stone-500 block uppercase">Inference Overhead</span>
            <span className="text-2xl font-bold font-mono text-stone-900 mt-1 block">{live.costPct}% spend</span>
            <span className="text-[11px] text-stone-500">Of one generation, per decision</span>
          </div>

          <div className="surface-card p-4 rounded-xl border border-[#EAE2D4]">
            <span className="text-[11px] font-semibold text-stone-500 block uppercase">Gateway Latency</span>
            <span className="text-2xl font-bold font-mono text-stone-900 mt-1 block">p50 {live.p50}ms</span>
            <span className="text-[11px] text-stone-500">Modelled tier budgets, p99 {live.p99}ms</span>
          </div>

          <div className="surface-card p-4 rounded-xl border border-[#EAE2D4]">
            <span className="text-[11px] font-semibold text-stone-500 block uppercase">Action Spectrum</span>
            <span className="text-2xl font-bold font-mono text-amber-800 mt-1 block">5 Actions</span>
            <span className="text-[11px] text-stone-500">ALLOW to BLOCK</span>
          </div>

          <div className="surface-card p-4 rounded-xl border border-[#EAE2D4]">
            <span className="text-[11px] font-semibold text-stone-500 block uppercase">Audit Chain</span>
            <span className="text-2xl font-bold font-mono text-emerald-800 mt-1 block">SHA-256</span>
            <span className="text-[11px] text-stone-500">Immutable ledger on SQLite</span>
          </div>
        </div>

        {/* Animated Data Flow */}
        <div className="mt-12 max-w-2xl mx-auto">
          <div className="flex items-center justify-center space-x-2 sm:space-x-4">
            <div className="flow-node px-3 py-2 rounded-lg bg-stone-100 border border-stone-200 text-xs font-semibold text-stone-700">
              AI Generates
            </div>
            <div className="flow-arrow">
              <svg width="32" height="12" viewBox="0 0 32 12" className="text-amber-600">
                <line x1="0" y1="6" x2="24" y2="6" stroke="currentColor" strokeWidth="2" className="animate-flow-dash" strokeDasharray="4 2" />
                <polygon points="24,1 32,6 24,11" fill="currentColor" />
              </svg>
            </div>
            <div className="flow-node px-3 py-2 rounded-lg bg-amber-50 border-2 border-amber-400 text-xs font-bold text-amber-900 shadow-sm animate-pulse-subtle">
              ControlPlane Decides
            </div>
            <div className="flow-arrow">
              <svg width="32" height="12" viewBox="0 0 32 12" className="text-emerald-600">
                <line x1="0" y1="6" x2="24" y2="6" stroke="currentColor" strokeWidth="2" className="animate-flow-dash" strokeDasharray="4 2" />
                <polygon points="24,1 32,6 24,11" fill="currentColor" />
              </svg>
            </div>
            <div className="flow-node px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800">
              Safe Outcome
            </div>
          </div>
        </div>
      </section>

      {/* Core Theorem: The Spectrum of 5 Graded Actions */}
      <section id="problem" className="py-16 px-6 bg-[#FFFDF9] border-y border-[#EAE2D4]">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="text-center max-w-3xl mx-auto">
            <span className="text-xs font-bold font-mono uppercase tracking-wider text-amber-800 bg-amber-50 px-2.5 py-1 rounded border border-amber-200">
              The Fundamental Flaw of Binary Guardrails
            </span>
            <h2 className="text-3xl font-extrabold text-stone-900 mt-3 tracking-tight">
              Binary Pass/Fail Destroys Utility. Five Graded Actions Preserve It.
            </h2>
            <p className="mt-3 text-stone-600 text-sm leading-relaxed">
              When models are guarded by blunt binary filters, small uncertainties cause whole workflows to block. ControlPlane introduces five calibrated intervention tiers.
            </p>
            <p className="mt-2 text-stone-500 text-xs max-w-3xl mx-auto leading-relaxed">
              Escalation destroys less utility than a block, U = 40 against 200, because review
              delays a response while a block discards it. Price them the same and BLOCK dominates
              ESCALATE at every probability, leaving the spectrum with no route to a human.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 stagger-children">
            <div className="surface-card p-5 rounded-xl border border-[#EAE2D4] flex flex-col justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono pill-allow">ALLOW</span>
                <h3 className="font-bold text-stone-900 text-sm mt-3">Clean Passthrough</h3>
                <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                  Zero friction. Expected defect cost is lower than any intervention penalty.
                </p>
              </div>
              <span className="text-[11px] font-mono text-emerald-800 font-semibold mt-4">ρ(a) = 1.0 · F = 0 · U = 0</span>
            </div>

            <div className="surface-card p-5 rounded-xl border border-[#EAE2D4] flex flex-col justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono pill-hold">HOLD</span>
                <h3 className="font-bold text-stone-900 text-sm mt-3">Async Human Audit</h3>
                <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                  Releases response under quarantine or secondary queue for batch review.
                </p>
              </div>
              <span className="text-[11px] font-mono text-amber-800 font-semibold mt-4">ρ(a) = 0.5 · F = ₹5 · U = 20</span>
            </div>

            <div className="surface-card p-5 rounded-xl border border-[#EAE2D4] flex flex-col justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono pill-constrain">CONSTRAIN</span>
                <h3 className="font-bold text-stone-900 text-sm mt-3">Capability Strip</h3>
                <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                  Redacts PII matches, removes unsafe tool scopes, or enforces structured json schema.
                </p>
              </div>
              <span className="text-[11px] font-mono text-blue-800 font-semibold mt-4">ρ(a) = 0.3 · F = ₹15 · U = 80</span>
            </div>

            <div className="surface-card p-5 rounded-xl border border-[#EAE2D4] flex flex-col justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono pill-escalate">ESCALATE</span>
                <h3 className="font-bold text-stone-900 text-sm mt-3">Synchronous Routing</h3>
                <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                  Interrupts automated pipeline to route transaction to senior human supervisor.
                </p>
              </div>
              <span className="text-[11px] font-mono text-purple-800 font-semibold mt-4">ρ(a) = 0.1 · F = ₹120 · U = 40</span>
            </div>

            <div className="surface-card p-5 rounded-xl border border-[#EAE2D4] flex flex-col justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono pill-block">BLOCK</span>
                <h3 className="font-bold text-stone-900 text-sm mt-3">Hard Circuit Break</h3>
                <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                  Strict rejection returning policy fallback text. Permitted only when precision ≥ 95%.
                </p>
              </div>
              <span className="text-[11px] font-mono text-rose-800 font-semibold mt-4">ρ(a) = 0.0 · F = ₹50 · U = 200</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3-Tier Cascade Architecture */}
      <section id="architecture" className="py-16 px-6 max-w-7xl mx-auto">
        <div className="space-y-10">
          <div className="text-center max-w-2xl mx-auto">
            <span className="text-xs font-bold font-mono uppercase tracking-wider text-amber-800 bg-amber-50 px-2.5 py-1 rounded border border-amber-200">
              Low-Latency Architecture
            </span>
            <h2 className="text-3xl font-extrabold text-stone-900 mt-3 tracking-tight">
              The 3-Tier Detection Cascade
            </h2>
            <p className="mt-2 text-stone-600 text-sm">
              Verification runs on every request. Only expensive judgement is gated, so tier 2 fires on {pct(live.tier2)} of traffic.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 stagger-children">
            <div className="surface-card p-6 rounded-xl border border-[#EAE2D4] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-800">Tier 0 · {pct(live.tier0)} traffic</span>
                <span className="text-xs font-mono font-semibold text-emerald-700">12ms</span>
              </div>
              <h3 className="font-bold text-base text-stone-900">Deterministic In-Process</h3>
              <p className="text-xs text-stone-600 leading-relaxed">
                PII regex with Luhn, PAN and Aadhaar validation, structured schema parsing, token z-score anomaly, deny-list matching, and protected-attribute screening.
              </p>
            </div>

            <div className="surface-card p-6 rounded-xl border border-[#EAE2D4] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-800">Tier 1 · {pct(live.tier1)} traffic</span>
                <span className="text-xs font-mono font-semibold text-amber-700">90ms</span>
              </div>
              <h3 className="font-bold text-base text-stone-900">NLI Grounding, always on</h3>
              <p className="text-xs text-stone-600 leading-relaxed">
                Real cross-encoder entailment, claim by claim, against the retrieved source. Verification is never gated: with no context, or no model, it triggers the <b>Abstention Path</b> rather than reporting a clean result.
              </p>
            </div>

            <div className="surface-card p-6 rounded-xl border border-[#EAE2D4] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-800">Tier 2 · {pct(live.tier2)} traffic</span>
                <span className="text-xs font-mono font-semibold text-purple-700">450ms</span>
              </div>
              <h3 className="font-bold text-base text-stone-900">Judgement & Counterfactual Bias</h3>
              <p className="text-xs text-stone-600 leading-relaxed">
                Multi-sample voting, structured LLM verdicts, and counterfactual fairness testing that re-asks the model with the protected attribute swapped.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Explore Console CTA Banner */}
      <section className="py-14 px-6 bg-[#FAF4EA] border-t border-[#EAE2D4]">
        <div className="max-w-5xl mx-auto text-center space-y-6">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            Ready to Inspect the Engine?
          </h2>
          <p className="text-stone-600 text-sm max-w-xl mx-auto">
            Walk the seven demo screens, inspect the {live.decisions.toLocaleString()}-decision cryptographic ledger, or run custom test inputs.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={() => onLaunchConsole('screen0')}
              className="px-6 py-3 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-bold tracking-wide transition shadow-sm flex items-center space-x-2"
            >
              <span>Launch Interactive Console</span>
              <ArrowRight className="w-3.5 h-3.5 text-amber-400" />
            </button>
            <button
              onClick={() => onLaunchConsole('ledger')}
              className="px-5 py-3 bg-white hover:bg-slate-50 text-stone-800 border border-[#D9CEBA] rounded-xl text-xs font-semibold transition shadow-sm flex items-center space-x-2"
            >
              <Database className="w-3.5 h-3.5 text-stone-600" />
              <span>Inspect Decision Ledger</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
