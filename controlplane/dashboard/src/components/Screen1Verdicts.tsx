import React, { useState, useEffect } from 'react';
import { Shield, ArrowRight, RotateCw, Sparkles, CheckCircle2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface VerdictData {
  action: string;
  p_def: number;
  c_eff: number;
  losses: Record<string, number>;
  unconstrained_action: string;
  severity_cap: string;
  cap_reason: string | null;
  reason_codes: string[];
}

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

const WORKFLOW_METADATA: Record<string, { title: string; subtitle: string; consequence: string; irreversibility: number; mode: string; role: string }> = {
  internal_copilot: {
    title: 'Internal Copilot',
    subtitle: 'Employee productivity & draft synthesis',
    consequence: '₹800',
    irreversibility: 0.2,
    mode: 'Monitored',
    role: 'Low Consequence',
  },
  support_chatbot: {
    title: 'Support Chatbot',
    subtitle: 'Customer ticketing & billing assistance',
    consequence: '₹3,000',
    irreversibility: 0.6,
    mode: 'Buffered',
    role: 'Medium Consequence',
  },
  decision_support: {
    title: 'Decision Support',
    subtitle: 'Automated claim adjudication & clinical triage',
    consequence: '₹50,000',
    irreversibility: 0.9,
    mode: 'Gated',
    role: 'High Consequence',
  },
};

// The payload carries the adjudicated text and context alongside one entry per
// workflow, so it is not a plain Record<string, VerdictData>.
interface Screen1Payload {
  response?: string;
  retrieval_context?: string;
  distinct_actions?: string[];
  columns?: Record<string, VerdictData>;
  [workflowId: string]: any;
}

export const Screen1Verdicts: React.FC = () => {
  const [data, setData] = useState<Screen1Payload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Rendered from the API payload, never hardcoded. A pinned string here drifts
  // from the fixture the engine actually scores, and the screen ends up showing
  // one response while the verdicts below it describe another.
  const sampleResponse: string = data?.response ?? '';
  const sampleContext: string = data?.retrieval_context ?? '';

  const fetchVerdicts = async () => {
    setLoading(true);
    try {
      const res = await fetch('/demo/screen1');
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error('Failed to fetch screen 1 demo', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVerdicts();
  }, []);

  const workflows = ['internal_copilot', 'support_chatbot', 'decision_support'];

  return (
    <div className="space-y-6">
      {/* Top Context & Prompt Card */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E8DFC9]/80">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Screen 1
              </span>
              <span className="text-stone-300">/</span>
              <span className="text-xs font-semibold text-stone-700">The Decision Spectrum</span>
            </div>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">Identical Output, Three Graded Actions</h2>
            <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
              Evaluating the exact same candidate output across three enterprise workflows. The detector outputs are invariant.
              The resulting actions diverge solely due to the workflow consequence model (<span className="font-mono text-stone-900 font-semibold">C_w</span>) and irreversibility factor (<span className="font-mono text-stone-900 font-semibold">ι</span>).
            </p>
          </div>
          <button
            onClick={fetchVerdicts}
            disabled={loading}
            className="px-3.5 py-1.5 bg-[#FFFDF9] hover:bg-[#F5EFE4] text-stone-800 border border-[#D9CEBA] rounded-lg text-xs font-semibold shadow-sm transition flex items-center space-x-1.5 self-start md:self-auto"
          >
            <RotateCw className={`w-3.5 h-3.5 text-stone-500 ${loading ? 'animate-spin' : ''}`} />
            <span>Re-adjudicate</span>
          </button>
        </div>

        {/* Evaluated Output Snippet */}
        <div className="mt-4 pt-1">
          <div className="flex items-center justify-between text-[11px] text-stone-500 mb-1.5">
            <span className="font-semibold text-stone-700">Evaluated candidate response:</span>
            <span className="font-mono text-stone-500 text-[10px]">Checked claim by claim against the source</span>
          </div>
          <div className="surface-inset p-3.5 rounded-lg text-xs text-stone-800 font-mono leading-relaxed border border-[#E6DEC4]">
            "{sampleResponse}"
          </div>
          <div className="mt-2 text-[11px] text-stone-600">
            <span className="font-semibold text-stone-700">Source document: </span>
            <span className="font-mono">{sampleContext}</span>
          </div>
        </div>
      </div>

      {/* 3 Workflow Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {workflows.map((wid) => {
          const v = data ? data[wid] : null;
          const meta = WORKFLOW_METADATA[wid];
          if (!meta) return null;

          const chartData = v
            ? Object.entries(v.losses).map(([act, loss]) => ({
                action: act,
                loss: loss,
                isWinner: act === v.unconstrained_action,
              }))
            : [];

          return (
            <div
              key={wid}
              className="surface-card rounded-xl p-5 border border-[#EAE2D4] surface-card-hover flex flex-col justify-between"
            >
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-amber-800/80 tracking-wider block">
                      {meta.role}
                    </span>
                    <h3 className="font-bold text-base text-stone-900 mt-0.5">{meta.title}</h3>
                    <p className="text-xs text-stone-500 mt-0.5">{meta.subtitle}</p>
                  </div>
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-[#F4EFE6] text-stone-800 border border-[#E2D8C6]">
                    {meta.mode}
                  </span>
                </div>

                {/* Workflow Consequence Matrix */}
                <div className="grid grid-cols-2 gap-2 text-xs bg-[#FAF6EE] p-2.5 rounded-lg border border-[#EAE2D4]">
                  <div>
                    <span className="text-stone-500 block text-[10px]">Consequence C_w:</span>
                    <span className="font-bold text-stone-900 font-mono">{meta.consequence}</span>
                  </div>
                  <div>
                    <span className="text-stone-500 block text-[10px]">Irreversibility ι:</span>
                    <span className="font-bold text-stone-900 font-mono">{meta.irreversibility}</span>
                  </div>
                </div>

                {/* Decision Metrics */}
                {v && (
                  <div className="space-y-1.5 text-xs font-mono">
                    <div className="flex justify-between py-1 border-b border-stone-100">
                      <span className="text-stone-600 font-sans text-[11px]">P_def (Risk Probability):</span>
                      <span className="text-stone-900 font-semibold">{v.p_def.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-stone-100">
                      <span className="text-stone-600 font-sans text-[11px]">C_eff (Effective Consequence):</span>
                      <span className="text-stone-900 font-semibold">₹{v.c_eff.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-stone-100">
                      <span className="text-stone-600 font-sans text-[11px]">Severity Cap:</span>
                      <span className="text-stone-800 font-medium">{v.severity_cap}</span>
                    </div>
                    {v.unconstrained_action !== v.action && (
                      <div className="flex justify-between py-1 border-b border-stone-100">
                        <span className="text-stone-600 font-sans text-[11px]">Cap Applied:</span>
                        <span className="text-amber-800 font-semibold text-[11px]">
                          {v.unconstrained_action} → {v.action}
                          <span className="text-stone-500 font-normal ml-1">({v.cap_reason})</span>
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Expected Loss L(a) Bar Chart */}
                <div>
                  <div className="flex items-center justify-between text-[11px] text-stone-600 mb-2">
                    <span className="font-semibold text-stone-800">Expected Loss Spectrum L(a):</span>
                    <span className="text-[10px] text-stone-500 font-mono">argmin L(a)</span>
                  </div>
                  <div className="h-32 w-full bg-[#FAF6EE] rounded-lg p-2 border border-[#EAE2D4]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                        <XAxis dataKey="action" tick={{ fill: '#78716C', fontSize: 9 }} tickLine={false} axisLine={{ stroke: '#EAE2D4' }} />
                        <YAxis tick={{ fill: '#78716C', fontSize: 8 }} tickLine={false} axisLine={{ stroke: '#EAE2D4' }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#FFFDF9', borderColor: '#D9CEBA', borderRadius: '6px', fontSize: '11px', color: '#1C1917', boxShadow: '0 4px 6px -1px rgba(100,80,50,0.1)' }}
                          formatter={(value: any) => [`₹${Number(value).toFixed(2)}`, 'Loss']}
                        />
                        <Bar dataKey="loss" radius={[2, 2, 0, 0]}>
                          {chartData.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={entry.isWinner ? '#D97706' : '#D7CEBE'}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Reason Codes */}
                {v && (
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase font-bold tracking-wider block mb-1">Reason Codes</span>
                    <div className="flex flex-wrap gap-1">
                      {v.reason_codes.map((rc: string, i: number) => (
                        <span key={i} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4]">
                          {rc}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Action Pill Footer */}
              <div className="mt-5 pt-3 border-t border-stone-100">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-stone-600 font-medium">Adjudicated Verdict:</span>
                  <span className={`px-3 py-1 rounded-md text-xs font-bold font-mono uppercase tracking-wider shadow-sm ${ACTION_PILL_STYLES[v?.action || 'ALLOW']}`}>
                    {v?.action || 'EVALUATING'}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
