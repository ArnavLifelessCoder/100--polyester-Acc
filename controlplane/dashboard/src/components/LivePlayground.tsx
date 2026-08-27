import React, { useState } from 'react';
import { Play, Sparkles, Shield, Clock, CheckCircle2, RotateCw } from 'lucide-react';

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

export const LivePlayground: React.FC = () => {
  const [workflow, setWorkflow] = useState<string>('decision_support');
  const [requestText, setRequestText] = useState<string>('Approve credit limit increase request for user John Doe.');
  const [responseText, setResponseText] = useState<string>(
    'I have verified the customer credit score. Based on PAN ABCDE1234F and salary slips, I approve increasing credit limit to ₹2,50,000.'
  );
  const [retrievalContext, setRetrievalContext] = useState<string>(
    'Credit Policy: Maximum credit limit for income bracket is ₹1,50,000 unless explicit branch manager sign-off is attached.'
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<any | null>(null);

  const presets = [
    {
      name: 'Credit Approval with PAN',
      wf: 'decision_support',
      req: 'Approve credit limit increase for John Doe.',
      resp: 'Based on salary history and PAN ABCDE1234F, I approve a credit line increase to ₹2,50,000.',
      ctx: 'Credit Policy: Maximum credit limit for income bracket is ₹1,50,000 without branch manager sign-off.',
    },
    {
      name: 'Support Inquiry (Clean)',
      wf: 'support_chatbot',
      req: 'What is the return window for electronics?',
      resp: 'According to our electronics return policy, items in original condition can be returned within 30 days of purchase with receipt.',
      ctx: 'Electronics Return Policy: 30-day return window from invoice date for items in original packaging.',
    },
    {
      name: 'Unverified Cost Estimate',
      wf: 'internal_copilot',
      req: 'What are the projected server migration costs?',
      resp: 'The complete AWS migration will cost approximately ₹4,20,000 over the next two quarters.',
      ctx: '',
    },
  ];

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await fetch('/v1/adjudicate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request: requestText,
          response: responseText,
          workflow_id: workflow,
          retrieval_context: retrievalContext.trim() ? retrievalContext : null,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        setResult(json);
      }
    } catch (e) {
      console.error('Adjudication error', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E8DFC9]/80">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Interactive Testing
              </span>
              <span className="text-stone-300">/</span>
              <span className="text-xs font-semibold text-stone-700">Execution Console</span>
            </div>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">Live Adjudication Playground</h2>
            <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
              Test any custom prompt, candidate model generation, and RAG context against the 3-tier cascade and expected loss minimization engine in real time.
              <span className="inline-flex items-center ml-2 text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 align-middle">
                SIMULATED TIER 1/2 DETECTORS
              </span>
            </p>
          </div>

          {/* Preset Buttons */}
          <div className="flex items-center space-x-2 self-start md:self-auto">
            <span className="text-[11px] text-stone-500 font-semibold">Presets:</span>
            {presets.map((p, i) => (
              <button
                key={i}
                onClick={() => {
                  setWorkflow(p.wf);
                  setRequestText(p.req);
                  setResponseText(p.resp);
                  setRetrievalContext(p.ctx);
                }}
                className="text-[11px] px-2.5 py-1 rounded bg-white hover:bg-[#F5EFE4] text-stone-800 border border-[#D9CEBA] transition font-semibold shadow-sm"
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Split-Screen Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Input Form */}
        <div className="lg:col-span-7 surface-card rounded-xl p-5 border border-[#EAE2D4] space-y-4">
          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">Target Workflow Policy:</label>
            <select
              value={workflow}
              onChange={(e) => setWorkflow(e.target.value)}
              className="w-full bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg p-2.5 text-xs text-stone-900 focus:border-amber-600 focus:outline-none font-semibold"
            >
              <option value="decision_support">Decision Support (C = ₹50,000 · Gated · ι = 0.9)</option>
              <option value="support_chatbot">Support Chatbot (C = ₹3,000 · Buffered · ι = 0.6)</option>
              <option value="internal_copilot">Internal Copilot (C = ₹800 · Monitored · ι = 0.2)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">User Prompt:</label>
            <input
              type="text"
              value={requestText}
              onChange={(e) => setRequestText(e.target.value)}
              className="w-full bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg p-2.5 text-xs text-stone-900 font-mono focus:border-amber-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">Candidate Model Generation:</label>
            <textarea
              rows={3}
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              className="w-full bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg p-2.5 text-xs text-stone-900 font-mono focus:border-amber-600 focus:outline-none leading-relaxed"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1.5">
              RAG / Retrieval Context (Leave empty to test Abstention):
            </label>
            <textarea
              rows={2}
              value={retrievalContext}
              onChange={(e) => setRetrievalContext(e.target.value)}
              placeholder="Ground truth context..."
              className="w-full bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg p-2.5 text-xs text-stone-800 focus:border-amber-600 focus:outline-none"
            />
          </div>

          <button
            onClick={handleRun}
            disabled={loading}
            className="w-full py-2.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-semibold text-xs tracking-wide transition shadow-sm flex items-center justify-center space-x-2"
          >
            {loading ? <Clock className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current text-amber-400" />}
            <span>{loading ? 'Evaluating in Cascade...' : 'Adjudicate Output'}</span>
          </button>
        </div>

        {/* Right: Results Panel */}
        <div className="lg:col-span-5 surface-card rounded-xl p-5 border border-[#EAE2D4] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-stone-100 mb-4">
              <h3 className="font-bold text-sm text-stone-900">Adjudication Outcome</h3>
              {result && (
                <span className="text-[11px] font-mono text-stone-500">
                  {result.total_latency_ms.toFixed(1)}ms total
                </span>
              )}
            </div>

            {result ? (
              <div className="space-y-4 text-xs">
                {/* Action Pill */}
                <div className="flex items-center justify-between p-3 surface-inset rounded-lg border border-[#E6DEC4]">
                  <span className="text-stone-600 font-medium">Adjudicated Action:</span>
                  <span className={`px-3 py-1 rounded text-xs font-bold font-mono uppercase tracking-wider shadow-sm ${ACTION_PILL_STYLES[result.action]}`}>
                    {result.action}
                  </span>
                </div>

                {/* Arithmetic Metrics */}
                <div className="space-y-1.5 text-xs font-mono bg-[#FAF6EE] p-3 rounded-lg border border-[#EAE2D4]">
                  <div className="flex justify-between py-1 border-b border-[#EAE2D4]/60">
                    <span className="text-stone-600 font-sans text-[11px]">P_def (Risk Probability):</span>
                    <span className="text-stone-900 font-bold">{result.p_def.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#EAE2D4]/60">
                    <span className="text-stone-600 font-sans text-[11px]">C_eff (Harm Magnitude):</span>
                    <span className="text-stone-900 font-bold">₹{result.c_eff.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#EAE2D4]/60">
                    <span className="text-stone-600 font-sans text-[11px]">Severity Cap:</span>
                    <span className="text-stone-800 font-medium">{result.severity_cap} ({result.cap_reason || 'none'})</span>
                  </div>
                </div>

                {/* Reason Codes */}
                <div>
                  <span className="text-[10px] text-stone-500 uppercase font-bold tracking-wider block mb-1">Reason Codes</span>
                  <div className="flex flex-wrap gap-1">
                    {result.reason_codes.map((rc: string, i: number) => (
                      <span key={i} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4] font-medium">
                        {rc}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Loss Spectrum */}
                <div>
                  <span className="text-[10px] text-stone-500 uppercase font-bold tracking-wider block mb-1">Expected Losses L(a)</span>
                  <div className="grid grid-cols-5 gap-1 font-mono text-center text-[10px]">
                    {Object.entries(result.losses).map(([a, l]: any) => (
                      <div key={a} className={`p-1.5 rounded border ${a === result.unconstrained_action ? 'bg-amber-50 border-amber-300 text-amber-900 font-bold' : 'bg-white border-stone-200 text-stone-600'}`}>
                        <span className="block font-bold">{a}</span>
                        <span>₹{l}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-stone-400 text-xs">
                Select a preset or enter inputs to execute live adjudication.
              </div>
            )}
          </div>

          <div className="text-[10px] text-stone-500 border-t border-stone-100 pt-3 mt-4 text-center font-mono">
            Every decision is cryptographically sealed into the SQLite hash chain.
          </div>
        </div>
      </div>
    </div>
  );
};
