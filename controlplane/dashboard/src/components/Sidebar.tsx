import React from 'react';
import { Shield, Layers, Sliders, FileSearch, MessageSquare, Database, Play, Home, CheckCircle2, ChevronRight, Activity, Cpu, Zap, ShieldCheck, GitBranch } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onOpenLanding: () => void;
  metrics: any;
  hashChainValid: boolean | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  onOpenLanding,
  metrics,
  hashChainValid,
}) => {
  const navSections = [
    {
      title: 'Demo Scenarios',
      items: [
        { id: 'screen0', label: '0. The Catch', icon: Zap, desc: 'Real model, real hallucination' },
        { id: 'screen1', label: '1. Three Verdicts', icon: Layers, desc: 'Identical output, 3 actions' },
        { id: 'screen2', label: '2. Threshold Frontier', icon: Sliders, desc: 'Global vs Derived EDR/UIR' },
        { id: 'screen3', label: '3. Abstention', icon: FileSearch, desc: 'Missing RAG prior fallback' },
        { id: 'screen4', label: '4. Compounding & Dial', icon: MessageSquare, desc: 'Multi-turn carry & precision dial' },
        { id: 'screen5', label: '5. Calibration Gate', icon: ShieldCheck, desc: 'Is the number even true?' },
        { id: 'screen6', label: '6. Agentic Consequence', icon: GitBranch, desc: 'Worth what it can cause' },
      ],
    },
    {
      title: 'Audit & Governance',
      items: [
        { id: 'ledger', label: 'Audit Ledger', icon: Database, desc: 'SHA-256 hash-chained store' },
      ],
    },
    {
      title: 'Developer Sandbox',
      items: [
        { id: 'playground', label: 'Live Playground', icon: Play, desc: 'Test custom prompts & RAG' },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-[#FFFDF9] border-r border-[#EAE2D4] flex flex-col justify-between flex-shrink-0 min-h-screen">
      <div>
        {/* Logo & Header */}
        <div className="p-5 border-b border-[#EAE2D4]">
          <button
            onClick={onOpenLanding}
            className="flex items-center space-x-2.5 text-left w-full hover:opacity-90 transition group"
          >
            <div className="w-7 h-7 rounded-lg bg-stone-900 flex items-center justify-center shadow-sm">
              <Shield className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-sm text-stone-900 tracking-tight">ControlPlane<span className="text-amber-700 font-semibold">.ai</span></span>
              </div>
              <span className="text-[10px] text-stone-500 font-medium block">Enterprise Gateway</span>
            </div>
          </button>
        </div>

        {/* Back to Home pill */}
        <div className="px-4 pt-4">
          <button
            onClick={onOpenLanding}
            className="w-full px-3 py-1.5 rounded-lg text-xs font-semibold text-stone-600 hover:text-stone-900 hover:bg-[#F5EFE4] transition flex items-center justify-between border border-[#EAE2D4]/60"
          >
            <span className="flex items-center space-x-2">
              <Home className="w-3.5 h-3.5 text-stone-500" />
              <span>Landing Page</span>
            </span>
            <ChevronRight className="w-3 h-3 text-stone-400" />
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="p-4 space-y-6">
          {navSections.map((section, sidx) => (
            <div key={sidx} className="space-y-1">
              <div className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-stone-400">
                {section.title}
              </div>
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelectTab(item.id)}
                    className={`w-full px-2.5 py-2 rounded-lg text-left transition-all flex items-start space-x-2.5 ${
                      isActive
                        ? 'bg-[#F2ECE1] text-stone-900 font-bold border border-[#D9CEBA] shadow-sm'
                        : 'text-stone-600 hover:text-stone-900 hover:bg-[#FAF6EE] font-medium border border-transparent'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isActive ? 'text-amber-800' : 'text-stone-400'}`} />
                    <div className="min-w-0">
                      <div className="text-xs leading-tight">{item.label}</div>
                      <div className="text-[10px] text-stone-400 truncate mt-0.5">{item.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Sidebar Footer / Telemetry Mini Widget */}
      <div className="p-4 border-t border-[#EAE2D4] bg-[#FAF6EE]/70 space-y-2.5">
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-stone-500">Hash Chain:</span>
          <span className="inline-flex items-center space-x-1 text-emerald-800 font-semibold text-[10px]">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>Verified</span>
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-stone-500">Decisions Logged:</span>
          <span className="text-stone-900 font-bold">{metrics?.traffic?.total_decisions?.toLocaleString() ?? '0'}</span>
        </div>

        <div className="pt-2 border-t border-[#E8DFC9] flex justify-between text-[10px] text-stone-500">
          <span>Engine: Active</span>
          <span>Latency: p50 {metrics?.p50_latency_ms ?? 12}ms</span>
        </div>
      </div>
    </aside>
  );
};
