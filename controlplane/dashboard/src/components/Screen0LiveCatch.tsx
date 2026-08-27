import React, { useState, useEffect } from 'react';
import { Zap, AlertTriangle, CheckCircle2, XCircle, Scale, RotateCw, Radio } from 'lucide-react';

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

interface Claim {
  sentence: string;
  verdict: string;
  entailment: number;
  contradiction: number;
}

interface LiveResult {
  action: string;
  unconstrained_action: string;
  severity_cap: string;
  cap_reason: string | null;
  cap_binds: boolean;
  p_def: number;
  c_eff: number;
  workflow_id: string;
  request: string;
  retrieval_context: string;
  generated_response: string;
  total_latency_ms: number;
  tiers_run: number[];
  generation: { source: string; model: string | null };
  grounding: {
    method: string | null;
    supported: number | null;
    sentences: number | null;
    failed_claims: Claim[];
  };
  bias: {
    categories: string[];
    findings: Array<{ attribute_term: string; decision_term: string; category: string }>;
  };
}

interface Scenarios {
  provider: { configured: boolean; model: string };
  nli: { loaded: boolean; model: string };
  scenarios: Record<string, { label: string; workflow_id: string; request: string }>;
}

const VERDICT_STYLE: Record<string, string> = {
  entailed: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  contradicted: 'text-red-700 bg-red-50 border-red-200',
  unsupported: 'text-amber-700 bg-amber-50 border-amber-200',
};

export const Screen0LiveCatch: React.FC = () => {
  const [meta, setMeta] = useState<Scenarios | null>(null);
  const [scenario, setScenario] = useState<string>('refund_policy');
  const [result, setResult] = useState<LiveResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    fetch('/demo/live/scenarios')
      .then((r) => r.json())
      .then(setMeta)
      .catch((e) => console.error('failed to load scenarios', e));
  }, []);

  const run = async (key: string) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('/demo/live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: key }),
      });
      if (res.ok) setResult(await res.json());
    } catch (e) {
      console.error('live run failed', e);
    } finally {
      setLoading(false);
    }
  };

  const isLive = meta?.provider.configured;

  return (
    <div className="space-y-6">
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
            Screen 0
          </span>
          <span className="text-stone-300">/</span>
          <span className="text-xs font-semibold text-stone-700">The Catch</span>
        </div>
        <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">
          A model gets it wrong. The layer says which sentence.
        </h2>
        <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
          The answer below is checked claim by claim against the source document by a natural
          language inference model, and screened for decisions conditioned on protected attributes.
          Nothing here is a keyword list.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {meta &&
            Object.entries(meta.scenarios).map(([key, s]) => (
              <button
                key={key}
                onClick={() => {
                  setScenario(key);
                  run(key);
                }}
                className={`px-3 py-2 rounded-lg text-xs font-semibold border transition ${
                  scenario === key
                    ? 'bg-stone-900 text-white border-stone-900'
                    : 'bg-[#F2ECE1] text-stone-800 border-[#E4DBCB] hover:bg-[#EDE5D8]'
                }`}
              >
                {s.label}
              </button>
            ))}
          <button
            onClick={() => run(scenario)}
            disabled={loading}
            className="px-3 py-2 rounded-lg text-xs font-bold bg-amber-700 text-white hover:bg-amber-800 disabled:opacity-50 flex items-center space-x-1.5"
          >
            {loading ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            <span>{loading ? 'Adjudicating' : 'Run'}</span>
          </button>
        </div>

        {/* Provenance. A recording must never be presented as a live call. */}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px]">
          <span
            className={`inline-flex items-center space-x-1.5 px-2 py-1 rounded border font-semibold ${
              isLive
                ? 'text-emerald-800 bg-emerald-50 border-emerald-200'
                : 'text-stone-700 bg-stone-100 border-stone-200'
            }`}
          >
            <Radio className="w-3 h-3" />
            <span>
              {isLive ? `LIVE MODEL · ${meta?.provider.model}` : 'RECORDED RESPONSE · no model key configured'}
            </span>
          </span>
          <span className="text-stone-500 font-mono">
            grounding: {meta?.nli.loaded ? `real NLI · ${meta.nli.model}` : 'lexical fallback'}
          </span>
        </div>
      </div>

      {result && (
        <>
          {/* Verdict */}
          <div className="surface-card rounded-xl p-6 border border-[#EAE2D4] bg-[#FFFDF9]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                <span className={`${ACTION_PILL_STYLES[result.action]} text-sm px-3 py-1`}>
                  {result.action}
                </span>
                {result.cap_binds && (
                  <span className="text-[11px] text-stone-600 inline-flex items-center space-x-1">
                    <Scale className="w-3.5 h-3.5 text-amber-700" />
                    <span>
                      engine wanted <b className="text-stone-900">{result.unconstrained_action}</b>, capped at{' '}
                      <b className="text-stone-900">{result.severity_cap}</b> ({result.cap_reason})
                    </span>
                  </span>
                )}
              </div>
              <div className="font-mono text-[11px] text-stone-600 flex flex-wrap gap-3">
                <span>P_def <b className="text-stone-900">{result.p_def.toFixed(4)}</b></span>
                <span>C_eff <b className="text-stone-900">₹{result.c_eff.toLocaleString()}</b></span>
                <span>tiers <b className="text-stone-900">{result.tiers_run.join('·')}</b></span>
                <span>{result.total_latency_ms.toFixed(0)}ms</span>
              </div>
            </div>

            <div className="mt-4 grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                  Source document
                </div>
                <div className="text-xs text-stone-700 bg-[#F7F2E8] border border-[#E8DFC9] rounded-lg p-3 leading-relaxed">
                  {result.retrieval_context}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                  Model answer
                </div>
                <div className="text-xs text-stone-800 bg-white border border-[#E8DFC9] rounded-lg p-3 leading-relaxed">
                  {result.generated_response}
                </div>
              </div>
            </div>
          </div>

          {/* Per-claim grounding */}
          <div className="surface-card rounded-xl p-6 border border-[#EAE2D4] bg-[#FFFDF9]">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-stone-900">Claim-level verification</h3>
              <span className="text-[11px] font-mono text-stone-600">
                {result.grounding.supported}/{result.grounding.sentences} claims supported · method{' '}
                {result.grounding.method}
              </span>
            </div>

            {result.grounding.failed_claims.length === 0 ? (
              <div className="mt-3 text-xs text-emerald-800 inline-flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4" />
                <span>Every claim is entailed by the source.</span>
              </div>
            ) : (
              <div className="mt-3 space-y-2">
                {result.grounding.failed_claims.map((c, i) => (
                  <div
                    key={i}
                    className={`rounded-lg border p-3 text-xs ${VERDICT_STYLE[c.verdict] ?? VERDICT_STYLE.unsupported}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold uppercase tracking-wider text-[10px]">
                        {c.verdict === 'contradicted' ? 'refuted by source' : 'not supported by source'}
                      </span>
                      <span className="font-mono text-[10px] opacity-80">
                        entail {c.entailment.toFixed(3)} · contra {c.contradiction.toFixed(3)}
                      </span>
                    </div>
                    <div className="leading-relaxed">{c.sentence}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Bias */}
          {result.bias.categories.length > 0 && (
            <div className="surface-card rounded-xl p-6 border border-red-200 bg-red-50/40">
              <h3 className="text-sm font-bold text-stone-900 inline-flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-red-700" />
                <span>Decision conditioned on a protected attribute</span>
              </h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {result.bias.categories.map((cat) => (
                  <span
                    key={cat}
                    className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200"
                  >
                    {cat}
                  </span>
                ))}
              </div>
              <div className="mt-3 space-y-1.5">
                {result.bias.findings.map((f, i) => (
                  <div key={i} className="text-xs text-stone-700 font-mono">
                    <XCircle className="w-3 h-3 inline text-red-600 mr-1.5" />
                    <b className="text-red-800">{f.attribute_term}</b> appears beside decision term{' '}
                    <b className="text-stone-900">{f.decision_term}</b>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-stone-600 leading-relaxed">
                Co-occurrence is suggestive, not proof, so this evidence caps severity at escalation.
                The system asks for a human rather than silencing the model on its own.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
};
