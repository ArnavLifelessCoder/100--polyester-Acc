import React, { useState, useEffect } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, Legend,
} from 'recharts';
import { ShieldCheck, ShieldAlert, TrendingDown, Lock, Unlock, RotateCw } from 'lucide-react';

interface Point {
  mean_predicted: number;
  observed_rate: number;
  count: number;
}

interface Rates {
  edr: number | null;
  uir: number | null;
  intervention_rate: number | null;
  escaped_defects?: number;
  unnecessary_interventions?: number;
}

interface Screen5Data {
  sufficient: boolean;
  labelled_count: number;
  minimum_required?: number;
  gate: number;
  active: boolean;
  fit: {
    n_train: number;
    n_test: number;
    ece_test_raw: number;
    ece_test_calibrated: number;
    brier_test_raw: number;
    brier_test_calibrated: number;
    base_rate: number;
    mean_raw: number;
    mean_calibrated: number;
    passes_gate_raw: boolean;
    passes_gate_calibrated: boolean;
  };
  reliability_raw: Point[];
  reliability_calibrated: Point[];
  rates_before: Rates;
  rates_after: Rates;
  per_workflow: Record<string, { n: number; before: Rates; after: Rates }>;
  stage_ladder: Array<{ stage: string; reached: boolean; note: string }>;
  caption: string;
  finding: string;
}

const fmt = (v: number | null | undefined) =>
  v === null || v === undefined ? 'n/a' : v.toLocaleString();

export const Screen5Calibration: React.FC = () => {
  const [data, setData] = useState<Screen5Data | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [applying, setApplying] = useState<boolean>(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch('/demo/screen5');
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error('failed to load calibration', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const applyFit = async (on: boolean) => {
    setApplying(true);
    try {
      await fetch(on ? '/admin/calibration/fit' : '/admin/calibration/clear', {
        method: 'POST',
      });
      await load();
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-stone-600">Measuring calibration…</div>;
  }
  if (!data) return <div className="text-sm text-red-700">Could not load calibration.</div>;

  if (!data.sufficient) {
    return (
      <div className="surface-card rounded-xl p-6 border border-[#EAE2D4] bg-[#FFFDF9]">
        <h2 className="text-lg font-bold text-stone-900">Not enough adjudicated decisions</h2>
        <p className="text-xs text-stone-600 mt-2 leading-relaxed">
          {data.labelled_count} of {data.minimum_required} labels. Calibration is not
          estimated below that, because a monotone map fitted to a handful of labels
          tracks their noise. Run <code>python -m sim.seed_data</code> or label
          decisions through the ledger.
        </p>
      </div>
    );
  }

  const f = data.fit;
  const raw = data.reliability_raw.map((p) => ({ x: p.mean_predicted, y: p.observed_rate, z: p.count }));
  const cal = data.reliability_calibrated.map((p) => ({ x: p.mean_predicted, y: p.observed_rate, z: p.count }));
  const uirDrop =
    data.rates_before.uir && data.rates_after.uir !== null
      ? Math.round((1 - (data.rates_after.uir as number) / (data.rates_before.uir as number)) * 100)
      : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="surface-card rounded-xl p-6 bg-gradient-to-b from-[#FFFDF9] to-[#FAF6EE] border border-[#EAE2D4]">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
            Screen 5
          </span>
          <span className="text-stone-300">/</span>
          <span className="text-xs font-semibold text-stone-700">Trust the number</span>
        </div>
        <h2 className="text-lg font-bold text-stone-900 tracking-tight mt-1.5">
          Is the probability the engine acts on actually true?
        </h2>
        <p className="text-xs text-stone-600 mt-1 max-w-3xl leading-relaxed">{data.caption}</p>
        <p className="text-xs text-stone-700 mt-2 max-w-3xl leading-relaxed bg-[#F7F2E8] border border-[#E8DFC9] rounded-lg p-3">
          {data.finding}
        </p>
        <p className="text-[11px] text-stone-500 mt-2 font-mono">
          {data.labelled_count} adjudicated · fitted on {f.n_train}, scored on {f.n_test} held out
        </p>
      </div>

      {/* The gate */}
      <div
        className={`surface-card rounded-xl p-6 border ${
          f.passes_gate_raw ? 'border-emerald-200 bg-emerald-50/40' : 'border-red-200 bg-red-50/40'
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            {f.passes_gate_raw ? (
              <ShieldCheck className="w-6 h-6 text-emerald-700" />
            ) : (
              <ShieldAlert className="w-6 h-6 text-red-700" />
            )}
            <div>
              <div className="text-sm font-bold text-stone-900">
                {f.passes_gate_raw
                  ? 'Calibration gate passed'
                  : 'Calibration gate failed. This policy may not enforce.'}
              </div>
              <div className="text-[11px] text-stone-600 mt-0.5">
                Held-out ECE {f.ece_test_raw} against a gate of {data.gate}
              </div>
            </div>
          </div>
          <div className="font-mono text-[11px] text-stone-700 flex flex-wrap gap-4">
            <span>
              base rate <b className="text-stone-900">{f.base_rate}</b>
            </span>
            <span>
              mean reported <b className="text-stone-900">{f.mean_raw}</b>
            </span>
            <span className="text-red-800">
              overconfident {(f.mean_raw / Math.max(f.base_rate, 1e-9)).toFixed(1)}x
            </span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {data.stage_ladder.map((s) => (
            <div
              key={s.stage}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg border text-xs ${
                s.reached
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-stone-100 border-stone-200 text-stone-500'
              }`}
              title={s.note}
            >
              {s.reached ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
              <span className="font-bold uppercase tracking-wider text-[10px]">{s.stage}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Reliability diagram */}
      <div className="surface-card rounded-xl p-6 border border-[#EAE2D4] bg-[#FFFDF9]">
        <h3 className="text-sm font-bold text-stone-900">Reliability diagram</h3>
        <p className="text-[11px] text-stone-600 mt-1 leading-relaxed max-w-3xl">
          Each point is a bucket of decisions: what the detector claimed, against what
          actually happened. Points on the diagonal are honest. Points above it mean the
          detector claimed more risk than the data contained, and that is what buys
          unnecessary interventions.
        </p>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8DFC9" />
              <XAxis
                type="number"
                dataKey="x"
                name="reported"
                domain={[0, 'auto']}
                tick={{ fontSize: 10 }}
                label={{ value: 'reported probability', position: 'insideBottom', offset: -10, fontSize: 10 }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="observed"
                domain={[0, 'auto']}
                tick={{ fontSize: 10 }}
                label={{ value: 'observed rate', angle: -90, position: 'insideLeft', fontSize: 10 }}
              />
              <ZAxis type="number" dataKey="z" range={[40, 320]} name="decisions" />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                formatter={(v: any, n: string) => [typeof v === 'number' ? v.toFixed(4) : v, n]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
                stroke="#A8A29E"
                strokeDasharray="4 4"
              />
              <Scatter name="as reported" data={raw} fill="#B45309" fillOpacity={0.75} />
              <Scatter name="after calibration" data={cal} fill="#047857" fillOpacity={0.75} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Before / after */}
      <div className="surface-card rounded-xl p-6 border border-[#EAE2D4] bg-[#FFFDF9]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-bold text-stone-900">
            What correcting the probability does
          </h3>
          <button
            onClick={() => applyFit(!data.active)}
            disabled={applying}
            className={`px-3 py-2 rounded-lg text-xs font-bold border transition disabled:opacity-50 flex items-center space-x-1.5 ${
              data.active
                ? 'bg-stone-900 text-white border-stone-900'
                : 'bg-amber-700 text-white border-amber-700 hover:bg-amber-800'
            }`}
          >
            {applying ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <TrendingDown className="w-3.5 h-3.5" />}
            <span>{data.active ? 'Calibration active, click to clear' : 'Apply calibration to the engine'}</span>
          </button>
        </div>

        <div className="grid md:grid-cols-3 gap-4 mt-4">
          {[
            { k: 'ECE (held out)', a: f.ece_test_raw, b: f.ece_test_calibrated, lower: true },
            { k: 'Unnecessary interventions / 10k', a: data.rates_before.uir, b: data.rates_after.uir, lower: true },
            { k: 'Escaped defects / 10k', a: data.rates_before.edr, b: data.rates_after.edr, lower: true },
          ].map((row) => (
            <div key={row.k} className="rounded-lg border border-[#E8DFC9] bg-[#F7F2E8] p-3">
              <div className="text-[10px] font-bold uppercase tracking-wider text-stone-500">{row.k}</div>
              <div className="flex items-baseline space-x-2 mt-1 font-mono">
                <span className="text-lg font-bold text-red-800">{fmt(row.a as number)}</span>
                <span className="text-stone-400">→</span>
                <span className="text-lg font-bold text-emerald-800">{fmt(row.b as number)}</span>
              </div>
            </div>
          ))}
        </div>

        {uirDrop !== null && (
          <p className="text-xs text-stone-700 mt-4 leading-relaxed">
            Correcting the probability removes <b>{uirDrop}%</b> of unnecessary
            interventions while escaped defects stay essentially flat. The thresholds did
            not move. Moving them would have broken the consequence model that derives
            them; the input was what was wrong.
          </p>
        )}

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-[#E8DFC9]">
                <th className="py-2">Workflow</th>
                <th className="py-2 text-right">n</th>
                <th className="py-2 text-right">UIR before</th>
                <th className="py-2 text-right">UIR after</th>
                <th className="py-2 text-right">EDR before</th>
                <th className="py-2 text-right">EDR after</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {Object.entries(data.per_workflow).map(([wid, v]) => (
                <tr key={wid} className="border-b border-[#F0EAE0]">
                  <td className="py-2 font-sans font-semibold text-stone-800">{wid}</td>
                  <td className="py-2 text-right text-stone-600">{v.n}</td>
                  <td className="py-2 text-right text-red-800">{fmt(v.before.uir)}</td>
                  <td className="py-2 text-right text-emerald-800">{fmt(v.after.uir)}</td>
                  <td className="py-2 text-right text-stone-700">{fmt(v.before.edr)}</td>
                  <td className="py-2 text-right text-stone-700">{fmt(v.after.edr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
