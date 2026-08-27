import React, { useState, useEffect } from 'react';
import { GitBranch, ArrowRight, Wrench, AlertTriangle } from 'lucide-react';

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

interface ReachableTool {
  tool: string;
  label: string;
  consequence: number;
  p_reach: number;
  iota: number;
  effective: number;
}

interface Variant {
  label: string;
  description: string;
  action: string;
  unconstrained_action: string;
  severity_cap: string;
  cap_binds: boolean;
  p_def: number;
  c_eff: number;
  reachable_tools: ReachableTool[];
  reason_codes: string[];
}

interface Screen6Data {
  request: string;
  response: string;
  workflow_id: string;
  policy_consequence: Record<string, number>;
  variants: Record<string, Variant>;
  distinct_actions: string[];
  caption: string;
}

const ORDER = ['text_only', 'plan_note', 'plan_refund'];

export const Screen6Agentic: React.FC = () => {
  const [data, setData] = useState<Screen6Data | null>(null);

  useEffect(() => {
    fetch('/demo/screen6')
      .then((r) => r.json())
      .then(setData)
      .catch((e) => console.error('failed to load agentic demo', e));
  }, []);

  if (!data) return <div className="text-sm text-stone-600">Loading…</div>;

  const maxCeff = Math.max(...Object.values(data.variants).map((v) => v.c_eff));

  return (
    <div className="space-y-6">
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
            Screen 6
          </span>
          <span className="text-stone-300">/</span>
          <span className="text-xs font-semibold text-stone-700">Agentic consequence</span>
        </div>
        <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">
          A step is worth what it can cause, not what it says.
        </h2>
        <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">{data.caption}</p>

        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">
              Request
            </div>
            <div className="text-xs text-stone-700 bg-[#F7F2E8] border border-[#E8DFC9] rounded-lg p-3">
              {data.request}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">
              Model output, identical in all three columns
            </div>
            <div className="text-xs text-stone-800 bg-white border border-[#E8DFC9] rounded-lg p-3 leading-relaxed">
              {data.response}
            </div>
          </div>
        </div>

        <div className="mt-3 text-[11px] font-mono text-stone-600">
          workflow <b className="text-stone-900">{data.workflow_id}</b> · policy consequence{' '}
          <b className="text-stone-900">₹{data.policy_consequence.performance?.toLocaleString()}</b> ·
          verdicts produced: <b className="text-stone-900">{data.distinct_actions.join(', ')}</b>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {ORDER.filter((k) => data.variants[k]).map((key) => {
          const v = data.variants[key];
          const barPct = Math.max(2, (v.c_eff / maxCeff) * 100);
          const escalated = v.c_eff > (data.policy_consequence.performance ?? 0);
          return (
            <div
              key={key}
              className={`surface-card rounded-xl p-5 border bg-[#FFFDF9] ${
                escalated ? 'border-amber-300' : 'border-[#EAE2D4]'
              }`}
            >
              <div className="flex items-start space-x-2">
                {key === 'text_only' ? (
                  <Wrench className="w-4 h-4 text-stone-400 mt-0.5" />
                ) : (
                  <GitBranch className="w-4 h-4 text-amber-700 mt-0.5" />
                )}
                <div>
                  <div className="text-xs font-bold text-stone-900 leading-snug">{v.label}</div>
                  <div className="text-[11px] text-stone-600 mt-0.5 leading-relaxed">
                    {v.description}
                  </div>
                </div>
              </div>

              {/* Reachable tools */}
              <div className="mt-4">
                <div className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                  Reachable actions
                </div>
                {v.reachable_tools.length === 0 ? (
                  <div className="text-[11px] text-stone-500 italic">
                    None. Nothing this step says can execute.
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {v.reachable_tools.map((t) => (
                      <div
                        key={t.tool}
                        className="text-[11px] rounded border border-[#E8DFC9] bg-[#F7F2E8] px-2 py-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-stone-800">{t.label}</span>
                          <span className="font-mono text-stone-900">
                            ₹{t.effective.toLocaleString()}
                          </span>
                        </div>
                        <div className="font-mono text-[10px] text-stone-500 mt-0.5">
                          ₹{t.consequence.toLocaleString()} × p{t.p_reach} × ι{t.iota}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* C_eff bar */}
              <div className="mt-4">
                <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-stone-500">
                  <span>Effective consequence</span>
                  <span className="font-mono text-stone-900 normal-case">
                    ₹{v.c_eff.toLocaleString()}
                  </span>
                </div>
                <div className="h-2 bg-[#F0EAE0] rounded mt-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded ${escalated ? 'bg-amber-600' : 'bg-stone-400'}`}
                    style={{ width: `${barPct}%` }}
                  />
                </div>
              </div>

              {/* Verdict */}
              <div className="mt-4 pt-3 border-t border-[#EAE2D4]">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500">
                    Verdict
                  </span>
                  <span className={ACTION_PILL_STYLES[v.action]}>{v.action}</span>
                </div>
                <div className="font-mono text-[10px] text-stone-600 mt-2">
                  P_def {v.p_def.toFixed(4)} · argmin {v.unconstrained_action}
                  {v.cap_binds && (
                    <span className="text-amber-800"> · capped at {v.severity_cap}</span>
                  )}
                </div>
                {v.reason_codes.some((r) => r.startsWith('REACHAB')) && (
                  <div className="mt-2 text-[10px] text-amber-800 inline-flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>consequence taken from the reachable tool, not the policy</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="surface-card rounded-xl p-5 border border-[#EAE2D4] bg-[#F7F2E8]">
        <div className="flex items-center space-x-2 text-xs text-stone-700">
          <ArrowRight className="w-4 h-4 text-amber-700" />
          <span>
            The risk vector is identical in all three columns. P_def never moves. Only what
            the step can reach changes, and that alone takes the same sentence from ALLOW
            to a human review.
          </span>
        </div>
      </div>
    </div>
  );
};
