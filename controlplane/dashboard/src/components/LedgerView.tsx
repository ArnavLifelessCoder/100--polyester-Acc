import React, { useState, useEffect } from 'react';
import { Database, Search, ChevronRight, X, Lock, CheckCircle2, RotateCw } from 'lucide-react';

interface DecisionRow {
  decision_id: string;
  request_id: string;
  session_id: string | null;
  workflow_id: string;
  policy_version: string;
  action: string;
  p_def: number;
  p_def_effective: number;
  c_eff: number;
  losses: Record<string, number>;
  unconstrained_action: string;
  severity_cap: string;
  cap_reason: string | null;
  reason_codes: string[];
  risk_vector: any;
  session_risk_before: number;
  session_risk_after: number;
  tiers_run: number[];
  total_latency_ms: number;
  estimated_cost_units: number;
  shadow: boolean;
  timestamp: string;
  prev_hash: string;
  row_hash: string;
}

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

export const LedgerView: React.FC = () => {
  const [decisions, setDecisions] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [workflowFilter, setWorkflowFilter] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDecision, setSelectedDecision] = useState<DecisionRow | null>(null);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [chainCount, setChainCount] = useState<number>(0);

  const fetchDecisions = async () => {
    setLoading(true);
    try {
      let url = '/v1/decisions?limit=150';
      if (workflowFilter) url += `&workflow_id=${workflowFilter}`;
      if (actionFilter) url += `&action=${actionFilter}`;
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setDecisions(json);
      }
    } catch (e) {
      console.error('Failed to fetch ledger decisions', e);
    } finally {
      setLoading(false);
    }
  };

  const verifyChain = async () => {
    try {
      const res = await fetch('/v1/chain/verify');
      if (res.ok) {
        const json = await res.json();
        setChainValid(json.valid);
        setChainCount(json.rows_checked);
      }
    } catch (e) {
      console.error('Failed to verify hash chain', e);
    }
  };

  useEffect(() => {
    fetchDecisions();
    verifyChain();
  }, [workflowFilter, actionFilter]);

  const filteredDecisions = decisions.filter((d) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      d.decision_id.toLowerCase().includes(q) ||
      d.workflow_id.toLowerCase().includes(q) ||
      d.action.toLowerCase().includes(q) ||
      d.reason_codes.some((r) => r.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
              Audit Substrate
            </span>
            <span className="text-stone-300">/</span>
            <span className="text-xs font-semibold text-stone-700">Immutable Ledger</span>
          </div>
          <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">SHA-256 Hash-Chained Decision Store</h2>
          <p className="text-xs text-stone-600 mt-1 max-w-2xl leading-relaxed">
            Every candidate response (including <span className="font-mono text-stone-900 font-semibold">ALLOW</span>) is recorded with append-only cryptographic hashes.
            Decisions are re-playable against the exact policy version that produced them.
          </p>
        </div>

        {/* Verification Pill */}
        <div className="flex items-center space-x-3 bg-white px-3.5 py-2.5 rounded-lg border border-[#D9CEBA] self-start md:self-auto shadow-sm">
          <div className="text-xs">
            <div className="flex items-center space-x-1.5 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span className="font-bold text-stone-900">Hash Chain Valid</span>
            </div>
            <span className="text-[10px] text-stone-500 font-mono">{chainCount.toLocaleString()} blocks verified to genesis</span>
          </div>
          <button
            onClick={verifyChain}
            className="p-1.5 text-stone-500 hover:text-stone-900 hover:bg-[#F5EFE4] rounded transition"
            title="Re-verify"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="surface-card rounded-xl p-4 border border-[#EAE2D4] flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Filter by ID, tag, or reason..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg pl-8 pr-3 py-1.5 text-stone-900 focus:outline-none focus:border-amber-600 w-56 font-mono text-xs"
            />
          </div>

          {/* Workflow Filter */}
          <select
            value={workflowFilter}
            onChange={(e) => setWorkflowFilter(e.target.value)}
            className="bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg px-2.5 py-1.5 text-stone-800 focus:outline-none focus:border-amber-600 text-xs font-semibold"
          >
            <option value="">All Workflows</option>
            <option value="decision_support">Decision Support</option>
            <option value="support_chatbot">Support Chatbot</option>
            <option value="internal_copilot">Internal Copilot</option>
          </select>

          {/* Action Filter */}
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-[#FAF6EE] border border-[#E2D8C6] rounded-lg px-2.5 py-1.5 text-stone-800 focus:outline-none focus:border-amber-600 text-xs font-semibold"
          >
            <option value="">All Actions</option>
            <option value="ALLOW">ALLOW</option>
            <option value="HOLD">HOLD</option>
            <option value="CONSTRAIN">CONSTRAIN</option>
            <option value="ESCALATE">ESCALATE</option>
            <option value="BLOCK">BLOCK</option>
          </select>
        </div>

        <span className="text-[11px] text-stone-500 font-mono">
          Showing <b className="text-stone-900">{filteredDecisions.length}</b> rows
        </span>
      </div>

      {/* Ledger Table */}
      <div className="surface-card rounded-xl overflow-hidden border border-[#EAE2D4]">
        <div className="overflow-x-auto max-h-[480px]">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F6F1E7] text-stone-700 font-semibold sticky top-0 border-b border-[#EAE2D4] text-[10px] tracking-wider uppercase">
              <tr>
                <th className="py-3 px-4 font-mono">Decision ID</th>
                <th className="py-3 px-4">Workflow</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4 font-mono">P_def</th>
                <th className="py-3 px-4 font-mono">C_eff</th>
                <th className="py-3 px-4">Severity Cap</th>
                <th className="py-3 px-4">Reason Codes</th>
                <th className="py-3 px-4 font-mono">Latency</th>
                <th className="py-3 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 font-mono text-[11px]">
              {filteredDecisions.map((d) => (
                <tr
                  key={d.decision_id}
                  onClick={() => setSelectedDecision(d)}
                  className="hover:bg-[#FAF6EE] cursor-pointer transition-colors"
                >
                  <td className="py-2.5 px-4 font-semibold text-amber-900">
                    {d.decision_id.slice(0, 8)}...
                  </td>
                  <td className="py-2.5 px-4 font-sans text-stone-800 font-medium">
                    {d.workflow_id}
                  </td>
                  <td className="py-2.5 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold shadow-sm ${ACTION_PILL_STYLES[d.action]}`}>
                      {d.action}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-stone-800">
                    {d.p_def.toFixed(4)}
                  </td>
                  <td className="py-2.5 px-4 text-stone-800">
                    ₹{d.c_eff.toLocaleString()}
                  </td>
                  <td className="py-2.5 px-4 text-stone-600">
                    {d.severity_cap}
                  </td>
                  <td className="py-2.5 px-4">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {d.reason_codes.slice(0, 2).map((rc, i) => (
                        <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4]">
                          {rc}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2.5 px-4 text-stone-600">
                    {d.total_latency_ms.toFixed(1)}ms
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <ChevronRight className="w-3.5 h-3.5 text-stone-400 inline-block" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Inspect Modal */}
      {selectedDecision && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/40 backdrop-blur-sm">
          <div className="surface-card rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 border border-[#D9CEBA] shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-stone-200 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900 font-mono">
                  Decision Record: {selectedDecision.decision_id}
                </h3>
                <span className="text-[11px] text-stone-500 font-mono">Workflow: {selectedDecision.workflow_id} · {selectedDecision.policy_version}</span>
              </div>
              <button
                onClick={() => setSelectedDecision(null)}
                className="p-1 rounded hover:bg-stone-100 text-stone-500 hover:text-stone-900"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Arithmetic Grid */}
            <div className="grid grid-cols-4 gap-2 text-xs bg-[#FAF6EE] p-3 rounded-lg border border-[#EAE2D4] font-mono">
              <div>
                <span className="text-stone-500 block text-[10px]">Action</span>
                <span className={`font-bold ${selectedDecision.action === 'ALLOW' ? 'text-emerald-700' : 'text-stone-900'}`}>
                  {selectedDecision.action}
                </span>
              </div>
              <div>
                <span className="text-stone-500 block text-[10px]">Unconstrained</span>
                <span className="text-stone-900 font-semibold">{selectedDecision.unconstrained_action}</span>
              </div>
              <div>
                <span className="text-stone-500 block text-[10px]">Severity Cap</span>
                <span className="text-stone-900 font-semibold">{selectedDecision.severity_cap}</span>
              </div>
              <div>
                <span className="text-stone-500 block text-[10px]">C_eff</span>
                <span className="text-stone-900 font-semibold">₹{selectedDecision.c_eff.toLocaleString()}</span>
              </div>
            </div>

            {/* Expected Loss Spectrum */}
            <div className="text-xs space-y-1.5">
              <span className="text-stone-700 text-[11px] font-semibold block">Expected Losses L(a):</span>
              <div className="grid grid-cols-5 gap-1.5 font-mono text-center text-[10px]">
                {Object.entries(selectedDecision.losses).map(([act, loss]) => (
                  <div
                    key={act}
                    className={`p-2 rounded border ${
                      act === selectedDecision.unconstrained_action
                        ? 'bg-amber-50 border-amber-300 text-amber-900 font-bold'
                        : 'bg-white border-stone-200 text-stone-600'
                    }`}
                  >
                    <span className="block font-bold">{act}</span>
                    <span>₹{loss}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Hashes */}
            <div className="surface-inset p-3 rounded-lg border border-[#E6DEC4] text-[10px] font-mono space-y-1">
              <span className="text-stone-700 font-bold block font-sans">Cryptographic Chain Hashes:</span>
              <div className="break-all text-stone-500">
                <span>Prev: </span>{selectedDecision.prev_hash}
              </div>
              <div className="break-all text-stone-800">
                <span className="text-emerald-700 font-semibold">Row:  </span>{selectedDecision.row_hash}
              </div>
            </div>

            {/* Detector evidence. The ledger is only an audit trail if it
                records why, not just what. */}
            {selectedDecision.risk_vector?.per_tag && (
              <div>
                <span className="text-[11px] font-semibold text-stone-700 block mb-1">
                  Detector Evidence
                </span>
                <div className="space-y-2">
                  {Object.entries(selectedDecision.risk_vector.per_tag).map(
                    ([tag, det]: [string, any]) => {
                      const ev = det.evidence ?? {};
                      const claims: any[] = ev.per_sentence ?? [];
                      const biasFindings: any[] = ev.findings ?? [];
                      return (
                        <div
                          key={tag}
                          className="rounded border border-[#EAE2D4] bg-[#FAF6EE] p-2"
                        >
                          <div className="flex items-center justify-between text-[10px] font-mono">
                            <span className="font-bold text-stone-800 uppercase tracking-wider">
                              {tag}
                            </span>
                            <span className="text-stone-600">
                              p_hat {det.p_hat} · precision {det.measured_precision} ·{' '}
                              {det.detector_id}
                              {det.verifiable === false && (
                                <span className="text-amber-800 font-bold"> · ABSTAINED</span>
                              )}
                            </span>
                          </div>

                          {ev.method && (
                            <div className="text-[10px] text-stone-500 font-mono mt-1">
                              method: {ev.method}
                              {ev.supported !== undefined &&
                                ` · ${ev.supported}/${ev.sentences} claims supported`}
                            </div>
                          )}

                          {/* Per-claim entailment from the grounding detector */}
                          {claims.length > 0 && (
                            <div className="mt-1.5 space-y-1">
                              {claims.map((c: any, i: number) => (
                                <div
                                  key={i}
                                  className={`text-[10px] rounded px-1.5 py-1 border ${
                                    c.verdict === 'entailed'
                                      ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                                      : c.verdict === 'contradicted'
                                      ? 'bg-red-50 border-red-200 text-red-900'
                                      : 'bg-amber-50 border-amber-200 text-amber-900'
                                  }`}
                                >
                                  <span className="font-bold uppercase tracking-wider mr-1.5">
                                    {c.verdict}
                                  </span>
                                  <span className="font-mono opacity-70">
                                    ent {Number(c.entailment).toFixed(3)}
                                  </span>
                                  <div className="mt-0.5 leading-snug">{c.sentence}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Protected attribute findings */}
                          {biasFindings.length > 0 && biasFindings[0]?.attribute_term && (
                            <div className="mt-1.5 space-y-0.5">
                              {biasFindings.map((f: any, i: number) => (
                                <div key={i} className="text-[10px] font-mono text-red-800">
                                  {f.category}: "{f.attribute_term}" beside "{f.decision_term}"
                                </div>
                              ))}
                            </div>
                          )}

                          {/* PII and deny-list matches */}
                          {Array.isArray(ev.matches) && ev.matches.length > 0 && (
                            <div className="mt-1.5 text-[10px] font-mono text-stone-700">
                              matches:{' '}
                              {ev.matches
                                .map((m: any) => (typeof m === 'string' ? m : m.type))
                                .join(', ')}
                            </div>
                          )}

                          {ev.abstained && (
                            <div className="mt-1.5 text-[10px] font-mono text-amber-800">
                              abstained: {ev.reason}
                            </div>
                          )}
                        </div>
                      );
                    }
                  )}
                </div>
              </div>
            )}

            {/* Reason Codes */}
            <div>
              <span className="text-[11px] font-semibold text-stone-700 block mb-1">Reason Codes</span>
              <div className="flex flex-wrap gap-1">
                {selectedDecision.reason_codes.map((rc, i) => (
                  <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#FAF6EE] text-stone-700 border border-[#EAE2D4] font-medium">
                    {rc}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
