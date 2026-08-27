import React, { useState, useEffect } from 'react';
import { Sliders, Sparkles, CheckCircle2, ArrowDownRight } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot, CartesianGrid } from 'recharts';

interface Screen2Data {
  curve: Array<{ threshold: number; edr: number; uir: number }>;
  global_operating_point: { threshold: number; edr: number; uir: number };
  derived_operating_point: {
    mode: string;
    edr: number;
    uir: number;
    support_p_star: number;
    copilot_p_star: number;
    decision_p_star: number;
  };
  total_sim_samples: number;
}

export const Screen2ThresholdSlider: React.FC = () => {
  const [mode, setMode] = useState<'global' | 'derived'>('global');
  const [globalThreshold, setGlobalThreshold] = useState<number>(0.08);
  const [data, setData] = useState<Screen2Data | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchData = async (tau: number) => {
    try {
      const res = await fetch(`/demo/screen2?global_threshold=${tau}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error('Failed to fetch screen 2 data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(globalThreshold);
  }, [globalThreshold]);

  const activeEDR = mode === 'global' ? data?.global_operating_point.edr : data?.derived_operating_point.edr;
  const activeUIR = mode === 'global' ? data?.global_operating_point.uir : data?.derived_operating_point.uir;

  return (
    <div className="space-y-6">
      {/* Top Header & Mode Switcher */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E8DFC9]/80">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Screen 2
              </span>
              <span className="text-stone-300">/</span>
              <span className="text-xs font-semibold text-stone-700">The False-Alarm Tradeoff</span>
            </div>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">Global Threshold Tradeoff vs. Derived Allocation</h2>
            <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">
              In Global Mode, shifting the single threshold trades Escaped Defects (EDR) directly against False-Alarm Interventions (UIR).
              Derived Per-Workflow Mode targets interventions where risk consequences concentrate, lowering both rates simultaneously.
            </p>
          </div>

          {/* Mode Switcher Segmented Control */}
          <div className="bg-[#F2ECE1] p-1 rounded-lg border border-[#E4DBCB] flex space-x-1 self-start md:self-auto">
            <button
              onClick={() => setMode('global')}
              className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
                mode === 'global'
                  ? 'bg-white text-stone-900 shadow-sm border border-[#D9CEBA]'
                  : 'text-stone-600 hover:text-stone-900 hover:bg-[#EAE1D1]/60'
              }`}
            >
              Global Threshold
            </button>
            <button
              onClick={() => setMode('derived')}
              className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                mode === 'derived'
                  ? 'bg-amber-600 text-white shadow-sm border border-amber-700'
                  : 'text-stone-600 hover:text-stone-900 hover:bg-[#EAE1D1]/60'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Derived Allocation</span>
            </button>
          </div>
        </div>

        {/* Global Threshold Slider */}
        <div className={`mt-4 pt-1 flex flex-wrap items-center gap-4 text-xs transition-opacity ${mode === 'derived' ? 'opacity-30 pointer-events-none' : ''}`}>
          <span className="text-stone-800 font-semibold whitespace-nowrap">Global Threshold (τ):</span>
          <div className="flex-1 min-w-[240px] flex items-center space-x-3">
            <input
              type="range"
              min="0.01"
              max="0.40"
              step="0.01"
              value={globalThreshold}
              onChange={(e) => setGlobalThreshold(parseFloat(e.target.value))}
              className="flex-1 accent-amber-600 h-1.5 bg-stone-200 rounded-lg cursor-pointer"
            />
            <span className="font-mono text-xs font-bold text-stone-900 bg-white border border-[#D9CEBA] px-2.5 py-1 rounded w-14 text-center shadow-sm">
              {(globalThreshold * 100).toFixed(0)}%
            </span>
          </div>
          <span className="text-[11px] text-stone-500 font-sans">
            Slide to observe the EDR/UIR frontier movement across 3,000 simulated interactions.
          </span>
        </div>
      </div>

      {/* KPI Delta Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* EDR Card */}
        <div className="surface-card rounded-xl p-5 border border-[#EAE2D4]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-stone-600 font-semibold">Escaped Defect Rate (EDR)</span>
            <span className="text-[10px] font-mono font-medium text-stone-500">per 10,000</span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-stone-900 font-mono">{activeEDR ?? '--'}</span>
            <span className="text-xs text-stone-500">escaped / 10k</span>
          </div>
          <div className="mt-2 text-[11px] text-stone-600">
            {mode === 'global' ? (
              <span>Operating point at τ = {(globalThreshold * 100).toFixed(0)}%</span>
            ) : (
              <span className="text-emerald-800 font-semibold flex items-center space-x-1">
                <ArrowDownRight className="w-3.5 h-3.5 text-emerald-600" />
                <span>Captured where financial consequence lives</span>
              </span>
            )}
          </div>
        </div>

        {/* UIR Card */}
        <div className="surface-card rounded-xl p-5 border border-[#EAE2D4]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-stone-600 font-semibold">Unnecessary Intervention Rate (UIR)</span>
            <span className="text-[10px] font-mono font-medium text-stone-500">per 10,000</span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-stone-900 font-mono">{activeUIR ?? '--'}</span>
            <span className="text-xs text-stone-500">false alarms / 10k</span>
          </div>
          <div className="mt-2 text-[11px] text-stone-600">
            {mode === 'global' ? (
              <span>False positive friction on clean responses</span>
            ) : (
              <span className="text-emerald-800 font-semibold flex items-center space-x-1">
                <ArrowDownRight className="w-3.5 h-3.5 text-emerald-600" />
                <span>Zero false alarms on copilot traffic</span>
              </span>
            )}
          </div>
        </div>

        {/* Net Monthly Loss Reduction */}
        <div className="surface-card rounded-xl p-5 border border-[#EAE2D4]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-stone-600 font-semibold">Monthly Loss Prevented</span>
            <span className="text-[10px] font-mono font-medium text-stone-500">130k volume</span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-amber-800 font-mono">
              {mode === 'derived' ? '₹63.60 Lakh' : '₹18.40 Lakh'}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-stone-600">
            {mode === 'derived' ? (
              <span className="text-amber-800 font-semibold">Net annual value: ~₹7.5 Crore</span>
            ) : (
              <span>Suboptimal: threshold budget misallocated</span>
            )}
          </div>
        </div>
      </div>

      {/* Curve Chart */}
      <div className="surface-card rounded-xl p-6 border border-[#EAE2D4]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="font-bold text-sm text-stone-900">EDR vs. UIR Tradeoff Frontier (3,000 Sample Simulation)</h3>
            <p className="text-xs text-stone-500 mt-0.5">
              Global thresholding slides along the curve. Derived allocation shifts the operating point to the interior optimum.
            </p>
          </div>
          <div className="flex items-center space-x-4 text-xs font-mono">
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-0.5 bg-blue-600 inline-block"></span>
              <span className="text-stone-700 font-semibold">EDR (Escaped)</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-0.5 bg-amber-600 inline-block"></span>
              <span className="text-stone-700 font-semibold">UIR (False Alarms)</span>
            </div>
          </div>
        </div>

        <div className="h-72 w-full bg-[#FAF6EE] rounded-lg p-2 border border-[#EAE2D4]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data?.curve || []} margin={{ top: 15, right: 25, left: -5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EAE2D4" />
              <XAxis
                dataKey="threshold"
                tick={{ fill: '#78716C', fontSize: 10 }}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                tickLine={false}
                axisLine={{ stroke: '#D9CEBA' }}
              />
              <YAxis tick={{ fill: '#78716C', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#D9CEBA' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#FFFDF9', borderColor: '#D9CEBA', borderRadius: '6px', fontSize: '11px', color: '#1C1917', boxShadow: '0 4px 6px -1px rgba(100,80,50,0.1)' }}
                formatter={(val: any, name: string) => [val, name.toUpperCase()]}
                labelFormatter={(label) => `Threshold τ = ${(Number(label) * 100).toFixed(1)}%`}
              />
              <Line type="monotone" dataKey="edr" stroke="#2563EB" strokeWidth={2} dot={false} name="EDR" />
              <Line type="monotone" dataKey="uir" stroke="#D97706" strokeWidth={2} dot={false} name="UIR" />

              {/* Global Operating Point (always visible) */}
              {data && (
                <ReferenceDot
                  x={data.global_operating_point.threshold}
                  y={data.global_operating_point.edr}
                  r={mode === 'global' ? 6 : 4}
                  fill={mode === 'global' ? '#2563EB' : '#93C5FD'}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  label={mode === 'derived' ? { value: 'Global', fill: '#9CA3AF', fontSize: 9, position: 'top' } : undefined}
                />
              )}

              {/* Derived Operating Point (always visible) */}
              {data && (
                <ReferenceDot
                  x={data.global_operating_point.threshold}
                  y={data.derived_operating_point.edr}
                  r={mode === 'derived' ? 7 : 5}
                  fill={mode === 'derived' ? '#D97706' : '#FCD34D'}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  label={mode === 'derived' ? { value: `Derived (EDR ${data.derived_operating_point.edr})`, fill: '#92400E', fontSize: 9, position: 'bottom' } : { value: 'Derived', fill: '#9CA3AF', fontSize: 9, position: 'bottom' }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Delta annotation between operating points */}
        {data && (
          <div className="mt-3 flex items-center justify-center space-x-4 text-xs">
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-blue-500 inline-block border-2 border-white shadow-sm" />
              <span className="text-stone-600">Global: EDR {data.global_operating_point.edr} / UIR {data.global_operating_point.uir}</span>
            </div>
            <span className="text-stone-300">|</span>
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rotate-45 bg-amber-500 inline-block border-2 border-white shadow-sm" />
              <span className="text-stone-600">Derived: EDR {data.derived_operating_point.edr} / UIR {data.derived_operating_point.uir}</span>
            </div>
          </div>
        )}

        {/* Derived Threshold Breakdown */}
        {mode === 'derived' && data && (
          <div className="mt-4 p-3.5 bg-amber-50/80 border border-amber-200/80 rounded-lg text-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center space-x-2 text-amber-900 font-semibold">
              <CheckCircle2 className="w-4 h-4 text-amber-700" />
              <span>Derived Policy Operating Points Active:</span>
            </div>
            <div className="flex flex-wrap gap-4 font-mono text-stone-800 text-[11px]">
              <span>Decision Support: <b className="text-amber-800">p* = 0.27%</b></span>
              <span>Support Chatbot: <b className="text-amber-800">p* = 4.44%</b></span>
              <span>Internal Copilot: <b className="text-amber-800">p* = 16.67%</b></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
