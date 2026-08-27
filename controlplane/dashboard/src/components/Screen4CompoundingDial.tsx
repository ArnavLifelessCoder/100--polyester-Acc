import React, { useState, useEffect, useCallback } from 'react';
import { Sliders, MessageSquare } from 'lucide-react';
import { ResponsiveContainer, ReferenceLine, CartesianGrid, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

interface DetectorQuality {
  tpr: number;
  fpr: number;
  samples: number;
  measured_precision: number;
  detector_precisions: Record<string, number>;
  severity_cap: string;
  action_distribution: Record<string, number>;
  edr: number;
  uir: number;
}

interface CompoundingTurn {
  turn: number;
  request: string;
  action: string;
  p_def: number;
  p_def_effective: number;
  session_risk_before: number;
  session_risk_after: number;
}

const ACTION_PILL_STYLES: Record<string, string> = {
  ALLOW: 'pill-allow',
  HOLD: 'pill-hold',
  CONSTRAIN: 'pill-constrain',
  ESCALATE: 'pill-escalate',
  BLOCK: 'pill-block',
};

export const Screen4CompoundingDial: React.FC = () => {
  const [turns, setTurns] = useState<CompoundingTurn[]>([]);
  // The band where this workflow stops choosing ALLOW, read from the engine's
  // own switching points. The old hardcoded 16.67% came from the annex closed
  // form p*_esc = H/(a_h*C), which omits iota and the utility-loss term and so
  // does not predict what the engine does.
  const [trackLabel, setTrackLabel] = useState<string>('');
  const [threshold, setThreshold] = useState<number>(0);
  const [tpr, setTpr] = useState<number>(0.80);
  const [fpr, setFpr] = useState<number>(0.05);
  const baseRate = 0.025;

  const fetchCompoundingData = async () => {
    try {
      const res = await fetch('/demo/screen4');
      if (res.ok) {
        const json = await res.json();
        // The endpoint now returns several tracks; render the primary one.
        const track = json.tracks[json.primary];
        setTurns(track.turns);
        setTrackLabel(json.primary);
        const firstIntervention = (track.thresholds || []).find(
          (t: any) => t.action !== 'ALLOW'
        );
        setThreshold(firstIntervention ? firstIntervention.p : 0);
      }
    } catch (e) {
      console.error('Failed to fetch compounding data', e);
    }
  };

  useEffect(() => {
    fetchCompoundingData();
  }, []);

  // Moving the dial re-scores the labelled set through the real engine and
  // returns what it did. The previous version POSTed the dial and computed
  // precision in the browser, so the slider moved and nothing on screen
  // changed: a control that does nothing is worse than no control.
  const [quality, setQuality] = useState<DetectorQuality | null>(null);
  const [scoring, setScoring] = useState<boolean>(false);

  const rescore = useCallback(async (newTpr: number, newFpr: number) => {
    setScoring(true);
    try {
      const res = await fetch(
        `/demo/detector_quality?tpr=${newTpr.toFixed(3)}&fpr=${newFpr.toFixed(3)}`
      );
      if (res.ok) setQuality(await res.json());
    } catch (e) {
      console.error('re-scoring failed', e);
    } finally {
      setScoring(false);
    }
  }, []);

  // Debounced so dragging does not queue a run per pixel.
  useEffect(() => {
    const t = setTimeout(() => rescore(tpr, fpr), 250);
    return () => clearTimeout(t);
  }, [tpr, fpr, rescore]);

  const handleTprChange = (val: number) => setTpr(val);
  const handleFprChange = (val: number) => setFpr(val);

  // Measured on the labelled set, not derived in the browser.
  const analyticalPrecision = quality?.measured_precision ?? 0.0;

  // Severity cap logic
  let severityCap = 'HOLD';
  let capStyle = 'pill-hold';
  if (analyticalPrecision >= 0.95) {
    severityCap = 'BLOCK';
    capStyle = 'pill-block';
  } else if (analyticalPrecision >= 0.70) {
    severityCap = 'ESCALATE';
    capStyle = 'pill-escalate';
  } else if (analyticalPrecision >= 0.40) {
    severityCap = 'CONSTRAIN';
    capStyle = 'pill-constrain';
  }

  const chartData = [
    { turn: 'T0 (Init)', effective_p: 0.0, threshold },
    ...turns.map((t) => ({
      turn: `T${t.turn}`,
      effective_p: t.p_def_effective,
      threshold,
    })),
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
            Screen 4
          </span>
          <span className="text-stone-300">/</span>
          <span className="text-xs font-semibold text-stone-700">Session Risk & Precision Limits</span>
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 ml-auto">
            SIMULATED DETECTORS
          </span>
        </div>
        <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">Multi-Turn Compounding & The Detector Quality Dial</h2>
        <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
          <b>Part 1:</b> Allowed risk in Turn 1 & 2 carries into context. Turn 3 crosses the escalation threshold purely from carry accumulation (<span className="font-mono text-stone-900 font-semibold">s_t</span>).
          <br />
          <b>Part 2:</b> When detector quality is low, the engine caps severity and degrades to <b>HOLD/LOG</b> instead of producing false blocks.
        </p>
      </div>

      {/* Part 1: Compounding Timeline & Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Turns List */}
        <div className="lg:col-span-6 surface-card rounded-xl p-5 border border-[#EAE2D4] space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-stone-100">
            <h3 className="font-bold text-sm text-stone-900">Compounding sequence: {trackLabel}</h3>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-mono font-semibold text-stone-600">intervenes above {(threshold * 100).toFixed(2)}%</span>
              <button
                onClick={fetchCompoundingData}
                className="px-2 py-1 text-[10px] font-semibold bg-white border border-stone-200 rounded hover:bg-stone-50 transition text-stone-700"
              >
                Re-run
              </button>
            </div>
          </div>

          <div className="space-y-2.5">
            {turns.map((t) => {
              const isEscalated = t.action === 'ESCALATE';
              return (
                <div
                  key={t.turn}
                  className={`p-3 rounded-lg border transition-colors ${
                    isEscalated
                      ? 'bg-purple-50 border-purple-200'
                      : 'surface-inset border-[#E6DEC4]'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-stone-900">Turn {t.turn}: "{t.request}"</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono shadow-sm ${ACTION_PILL_STYLES[t.action]}`}>
                      {t.action}
                    </span>
                  </div>

                  <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] font-mono text-stone-600 bg-white p-2 rounded border border-[#EAE2D4]">
                    <div>
                      <span className="text-stone-400 block font-sans">Single-Turn p</span>
                      <span className="text-stone-900 font-semibold">{(t.p_def * 100).toFixed(1)}%</span>
                    </div>
                    <div>
                      <span className="text-stone-400 block font-sans">Carried Risk s_t</span>
                      <span className="text-stone-900 font-semibold">{t.session_risk_after.toFixed(3)}</span>
                    </div>
                    <div>
                      <span className="text-stone-400 block font-sans">Effective P_eff</span>
                      <span className={`font-bold ${t.p_def_effective > threshold ? 'text-purple-700' : 'text-stone-900'}`}>
                        {(t.p_def_effective * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Compounding Chart */}
        <div className="lg:col-span-6 surface-card rounded-xl p-5 border border-[#EAE2D4] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-bold text-sm text-stone-900">Carried Risk Progression (P_eff)</h3>
              <span className="text-[11px] font-mono font-medium text-stone-500">γ = 0.85 · β = 0.50</span>
            </div>
            <p className="text-xs text-stone-500 mb-3">
              Per-turn risk never changes. Turns 1 and 2 sit below the {(threshold * 100).toFixed(2)}% band;
              turn 3 crosses it on carried risk alone.
            </p>

            <div className="h-56 w-full bg-[#FAF6EE] rounded-lg p-2 border border-[#EAE2D4]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="areaGradWarm" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#D97706" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#D97706" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EAE2D4" />
                  <XAxis dataKey="turn" tick={{ fill: '#78716C', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#D9CEBA' }} />
                  <YAxis tick={{ fill: '#78716C', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#D9CEBA' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#FFFDF9', borderColor: '#D9CEBA', borderRadius: '6px', fontSize: '11px', color: '#1C1917', boxShadow: '0 4px 6px -1px rgba(100,80,50,0.1)' }}
                    formatter={(v: any) => [`${(Number(v) * 100).toFixed(1)}%`, 'Effective Probability']}
                  />
                  <ReferenceLine y={threshold} stroke="#DC2626" strokeDasharray="3 3" label={{ value: `intervention band (${(threshold * 100).toFixed(2)}%)`, fill: "#B91C1C", fontSize: 9, position: "top" }} />
                  <Area type="monotone" dataKey="effective_p" stroke="#D97706" strokeWidth={2} fillOpacity={1} fill="url(#areaGradWarm)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-3 p-2.5 bg-[#FAF6EE] border border-[#EAE2D4] rounded-lg text-[11px] text-stone-600">
            Escalation triggers naturally from state compounding without hardcoded turn count limits.
          </div>
        </div>
      </div>

      {/* Part 2: The Detector Quality Dial */}
      <div className="surface-card rounded-xl p-6 border border-[#EAE2D4]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-stone-100">
          <div>
            <h3 className="text-sm font-bold text-stone-900">The Detector Quality Dial & Severity Cap</h3>
            <p className="text-xs text-stone-500 mt-0.5">
              Action severity is bounded by measured precision. Weak detectors degrade toward HOLD/LOG rather than dangerous false blocks.
            </p>
          </div>

          {/* Severity Cap Indicator */}
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-stone-600 font-medium">Maximum Permitted Action:</span>
            <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold uppercase shadow-sm ${capStyle}`}>
              {severityCap}
            </span>
          </div>
        </div>

        {/* Sliders Grid */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* TPR */}
          <div className="surface-inset p-3.5 rounded-lg border border-[#E6DEC4] space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="text-stone-700 font-semibold">True Positive Rate (TPR):</span>
              <span className="font-mono font-bold text-stone-900">{(tpr * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.10"
              max="0.99"
              step="0.01"
              value={tpr}
              onChange={(e) => handleTprChange(parseFloat(e.target.value))}
              className="w-full accent-amber-600 h-1.5 bg-stone-200 rounded-lg cursor-pointer"
            />
            <span className="text-[10px] text-stone-500 block">Detector Recall / Sensitivity</span>
          </div>

          {/* FPR */}
          <div className="surface-inset p-3.5 rounded-lg border border-[#E6DEC4] space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="text-stone-700 font-semibold">False Positive Rate (FPR):</span>
              <span className="font-mono font-bold text-stone-900">{(fpr * 100).toFixed(1)}%</span>
            </div>
            <input
              type="range"
              min="0.001"
              max="0.30"
              step="0.005"
              value={fpr}
              onChange={(e) => handleFprChange(parseFloat(e.target.value))}
              className="w-full accent-amber-600 h-1.5 bg-stone-200 rounded-lg cursor-pointer"
            />
            <span className="text-[10px] text-stone-500 block">False alarm probability</span>
          </div>

          {/* Precision Readout */}
          <div className="surface-inset p-3.5 rounded-lg border border-[#E6DEC4] flex flex-col justify-between">
            <div>
              <span className="text-stone-500 block text-[10px] font-bold uppercase">
                Measured Precision {scoring && <span className="text-amber-700">· re-scoring</span>}
              </span>
              <div className="text-2xl font-bold text-stone-900 font-mono mt-0.5">
                {(analyticalPrecision * 100).toFixed(1)}%
              </div>
            </div>
            <span className="text-[10px] text-stone-500 font-mono">
              Measured over {quality?.samples ?? 0} labelled decisions, best detector at this operating point
            </span>
          </div>
        </div>

        {/* Action mix, measured. This is the beat: as quality falls the system
            slides toward HOLD, meaning it degrades into logging rather than
            into wrong blocks. */}
        {quality && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-stone-500">
              <span>Action mix at this operating point</span>
              <span className="font-mono normal-case text-stone-700">
                UIR {quality.uir.toLocaleString()} / 10k · EDR {quality.edr.toLocaleString()} / 10k
              </span>
            </div>
            <div className="flex h-6 rounded overflow-hidden border border-[#E8DFC9] mt-1.5">
              {(['ALLOW', 'HOLD', 'CONSTRAIN', 'ESCALATE', 'BLOCK'] as const).map((a) => {
                const total = Object.values(quality.action_distribution).reduce((x, y) => x + y, 0) || 1;
                const pct = ((quality.action_distribution[a] ?? 0) / total) * 100;
                if (pct <= 0) return null;
                const bg: Record<string, string> = {
                  ALLOW: 'bg-emerald-500',
                  HOLD: 'bg-amber-400',
                  CONSTRAIN: 'bg-blue-500',
                  ESCALATE: 'bg-purple-500',
                  BLOCK: 'bg-red-600',
                };
                return (
                  <div
                    key={a}
                    className={`${bg[a]} flex items-center justify-center transition-all duration-300`}
                    style={{ width: `${pct}%` }}
                    title={`${a}: ${pct.toFixed(1)}%`}
                  >
                    {pct > 9 && (
                      <span className="text-[9px] font-bold text-white tracking-wider">
                        {a} {pct.toFixed(0)}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[10px] text-stone-600 mt-1.5 leading-relaxed">
              Drop detector quality and the mix slides toward HOLD. The system degrades
              into logging, not into wrong blocks.
            </p>
          </div>
        )}

        {/* Clean Precision Ladder Bar */}
        <div className="mt-4 grid grid-cols-4 gap-2 text-center text-[11px] font-mono">
          <div className={`p-2 rounded border transition-colors ${analyticalPrecision >= 0.95 ? 'bg-red-50 border-red-300 text-red-700 font-bold shadow-sm' : 'bg-[#FAF6EE] border-[#EAE2D4] text-stone-400'}`}>
            &gt;95% → BLOCK
          </div>
          <div className={`p-2 rounded border transition-colors ${analyticalPrecision >= 0.70 && analyticalPrecision < 0.95 ? 'bg-purple-50 border-purple-300 text-purple-700 font-bold shadow-sm' : 'bg-[#FAF6EE] border-[#EAE2D4] text-stone-400'}`}>
            70-95% → ESCALATE
          </div>
          <div className={`p-2 rounded border transition-colors ${analyticalPrecision >= 0.40 && analyticalPrecision < 0.70 ? 'bg-blue-50 border-blue-300 text-blue-700 font-bold shadow-sm' : 'bg-[#FAF6EE] border-[#EAE2D4] text-stone-400'}`}>
            40-70% → CONSTRAIN
          </div>
          <div className={`p-2 rounded border transition-colors ${analyticalPrecision < 0.40 ? 'bg-amber-50 border-amber-300 text-amber-800 font-bold shadow-sm' : 'bg-[#FAF6EE] border-[#EAE2D4] text-stone-400'}`}>
            &lt;40% → HOLD / LOG
          </div>
        </div>
      </div>
    </div>
  );
};
