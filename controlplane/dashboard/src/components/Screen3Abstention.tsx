import React, { useState, useEffect } from 'react';
import { ToggleLeft, ToggleRight, CheckCircle2, ShieldAlert } from 'lucide-react';

interface AbstentionDemoData {
  action: string;
  p_def: number;
  reason_codes: string[];
  unverifiable_tags: string[];
}

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

export const Screen3Abstention: React.FC = () => {
  const [hasContext, setHasContext] = useState<boolean>(true);
  const [data, setData] = useState<Record<string, AbstentionDemoData> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const claimText = "The quarterly earnings show a 15% increase in revenue, driven by strong performance in the Asia-Pacific region.";
  const contextText = "Q3 earnings report: Enterprise revenue grew by 15% year-over-year, largely propelled by 28% expansion in APAC regional operations.";

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch('/demo/screen3');
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error('Failed to fetch screen 3 data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const ctxKey = hasContext ? 'with_context' : 'without_context';
  const dsVerdict = data ? data[`${ctxKey}_decision_support`] : null;
  const cpVerdict = data ? data[`${ctxKey}_internal_copilot`] : null;

  return (
    <div className="space-y-6">
      {/* Top Banner & Interactive Context Toggle */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E8DFC9]/80">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Screen 3
              </span>
              <span className="text-stone-300">/</span>
              <span className="text-xs font-semibold text-stone-700">The Abstention Path</span>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 ml-auto">
                SIMULATED GROUNDING
              </span>
            </div>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">Unverifiable Claims Without Special-Case Code</h2>
            <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
              When knowledge-base context is absent, the detector cannot verify the claim. The engine emits <span className="font-mono text-stone-900 font-semibold">verifiable = false</span>,
              substitutes the workflow prior <span className="font-mono text-stone-900 font-semibold">π_w</span>, and caps severity producing divergent actions through identical arithmetic.
            </p>
          </div>

          {/* Toggle Control */}
          <div className="bg-[#F2ECE1] p-1 rounded-lg border border-[#E4DBCB] flex items-center space-x-3 self-start md:self-auto">
            <span className="text-xs text-stone-700 font-semibold pl-2">RAG Context:</span>
            <button
              onClick={() => setHasContext(!hasContext)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center space-x-1.5 shadow-sm ${
                hasContext
                  ? 'bg-emerald-700 text-white border border-emerald-800'
                  : 'bg-amber-600 text-white border border-amber-700'
              }`}
            >
              {hasContext ? <CheckCircle2 className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
              <span>{hasContext ? 'Context Attached' : 'Context Stripped'}</span>
            </button>
          </div>
        </div>

        {/* Claim & Context Previews */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="surface-inset p-3.5 rounded-lg border border-[#E6DEC4]">
            <span className="text-stone-500 block text-[10px] font-sans font-semibold uppercase mb-1">Generated Claim</span>
            <p className="text-stone-800 font-sans leading-relaxed text-xs font-medium">
              "{claimText}"
            </p>
          </div>

          <div className={`p-3.5 rounded-lg border transition-colors ${hasContext ? 'surface-inset border-[#E6DEC4]' : 'bg-amber-50/80 border-amber-200'}`}>
            <span className="text-stone-500 block text-[10px] font-sans font-semibold uppercase mb-1">
              RAG Knowledge Context ({hasContext ? 'Available' : 'Missing'})
            </span>
            <p className={`font-sans leading-relaxed text-xs font-medium ${hasContext ? 'text-stone-800' : 'text-amber-900 italic'}`}>
              {hasContext ? `"${contextText}"` : 'No retrieval context returned from knowledge base.'}
            </p>
          </div>
        </div>
      </div>

      {/* Side-by-Side Workflow Divergence */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Decision Support Card */}
        <div className="surface-card rounded-xl p-5 border border-[#EAE2D4] flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-amber-800/80 tracking-wider block">Regulated Workflow</span>
                <h3 className="font-bold text-base text-stone-900 mt-0.5">Decision Support</h3>
                <p className="text-xs text-stone-500 mt-0.5">C = ₹50,000 · Prior π = 0.9% · p* = 0.27%</p>
              </div>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-[#F4EFE6] text-stone-800 border border-[#E2D8C6]">
                Gated
              </span>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Detector Signal:</span>
                <span className="text-stone-900 font-semibold">
                  {hasContext ? 'p̂ = 0.00 (verifiable = true)' : 'p̂ = 0.00 (verifiable = false)'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Substituted Probability:</span>
                <span className="text-stone-900 font-semibold">
                  {hasContext ? 'P_def = 0.0000' : 'P_def = 0.0090 (prior π_w)'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Severity Cap:</span>
                <span className="text-stone-800 font-medium">
                  {hasContext ? 'BLOCK (precision > 0.95)' : 'CONSTRAIN (unverifiable cap)'}
                </span>
              </div>
            </div>

            {/* Reason Codes */}
            {dsVerdict && (
              <div>
                <span className="text-[10px] text-stone-500 uppercase font-bold tracking-wider block mb-1">Reason Codes</span>
                <div className="flex flex-wrap gap-1">
                  {dsVerdict.reason_codes.map((rc, i) => (
                    <span key={i} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4] font-medium">
                      {rc}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="mt-5 pt-3 border-t border-stone-100 flex items-center justify-between">
            <span className="text-[11px] text-stone-600 font-medium">Adjudicated Verdict:</span>
            <span className={`px-3 py-1 rounded-md text-xs font-bold font-mono uppercase tracking-wider shadow-sm ${ACTION_PILL_STYLES[dsVerdict?.action || 'ALLOW']}`}>
              {dsVerdict?.action || 'EVALUATING'}
            </span>
          </div>
        </div>

        {/* Internal Copilot Card */}
        <div className="surface-card rounded-xl p-5 border border-[#EAE2D4] flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-amber-800/80 tracking-wider block">Productivity Workflow</span>
                <h3 className="font-bold text-base text-stone-900 mt-0.5">Internal Copilot</h3>
                <p className="text-xs text-stone-500 mt-0.5">C = ₹800 · Prior π = 1.8% · p* = 16.67%</p>
              </div>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-[#F4EFE6] text-stone-800 border border-[#E2D8C6]">
                Monitored
              </span>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Detector Signal:</span>
                <span className="text-stone-900 font-semibold">
                  {hasContext ? 'p̂ = 0.00 (verifiable = true)' : 'p̂ = 0.00 (verifiable = false)'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Substituted Probability:</span>
                <span className="text-stone-900 font-semibold">
                  {hasContext ? 'P_def = 0.0000' : 'P_def = 0.0180 (prior π_w)'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-600 font-sans text-[11px]">Severity Cap:</span>
                <span className="text-stone-800 font-medium">
                  {hasContext ? 'BLOCK (precision > 0.95)' : 'CONSTRAIN (unverifiable cap)'}
                </span>
              </div>
            </div>

            {/* Reason Codes */}
            {cpVerdict && (
              <div>
                <span className="text-[10px] text-stone-500 uppercase font-bold tracking-wider block mb-1">Reason Codes</span>
                <div className="flex flex-wrap gap-1">
                  {cpVerdict.reason_codes.map((rc, i) => (
                    <span key={i} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4] font-medium">
                      {rc}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="mt-5 pt-3 border-t border-stone-100 flex items-center justify-between">
            <span className="text-[11px] text-stone-600 font-medium">Adjudicated Verdict:</span>
            <span className={`px-3 py-1 rounded-md text-xs font-bold font-mono uppercase tracking-wider shadow-sm ${ACTION_PILL_STYLES[cpVerdict?.action || 'ALLOW']}`}>
              {cpVerdict?.action || 'ALLOW'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
