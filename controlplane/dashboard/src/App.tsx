import React, { useState, useEffect } from 'react';
import { Shield, Home, LayoutDashboard, ChevronRight } from 'lucide-react';
import { LandingPage } from './components/LandingPage';
import { Sidebar } from './components/Sidebar';
import { TelemetryStrip } from './components/TelemetryStrip';
import { Screen0LiveCatch } from './components/Screen0LiveCatch';
import { Screen1Verdicts } from './components/Screen1Verdicts';
import { Screen2ThresholdSlider } from './components/Screen2ThresholdSlider';
import { Screen3Abstention } from './components/Screen3Abstention';
import { Screen4CompoundingDial } from './components/Screen4CompoundingDial';
import { Screen5Calibration } from './components/Screen5Calibration';
import { Screen6Agentic } from './components/Screen6Agentic';
import { LedgerView } from './components/LedgerView';
import { LivePlayground } from './components/LivePlayground';

type ViewMode = 'landing' | 'console';
type Tab = 'screen0' | 'screen1' | 'screen2' | 'screen3' | 'screen4' | 'screen5' | 'screen6' | 'ledger' | 'playground';

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('landing');
  const [activeTab, setActiveTab] = useState<Tab>('screen0');
  const [metrics, setMetrics] = useState<any | null>(null);
  const [hashChainValid, setHashChainValid] = useState<boolean | null>(null);

  const fetchGlobalMetrics = async () => {
    try {
      const [mRes, cRes] = await Promise.all([
        fetch('/v1/metrics'),
        fetch('/v1/chain/verify'),
      ]);
      if (mRes.ok) setMetrics(await mRes.json());
      if (cRes.ok) {
        const cJson = await cRes.json();
        setHashChainValid(cJson.valid);
      }
    } catch (e) {
      console.error('Failed to load global metrics', e);
    }
  };

  useEffect(() => {
    fetchGlobalMetrics();
    const interval = setInterval(fetchGlobalMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleLaunchConsole = (tab?: string) => {
    if (tab) setActiveTab(tab as Tab);
    setViewMode('console');
  };

  // If in Landing Page mode, render the full landing page
  if (viewMode === 'landing') {
    return <LandingPage onLaunchConsole={handleLaunchConsole} />;
  }

  // Console Mode with Sidebar
  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 flex font-sans antialiased">
      {/* Enterprise Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab as Tab)}
        onOpenLanding={() => setViewMode('landing')}
        metrics={metrics}
        hashChainValid={hashChainValid}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Telemetry Strip */}
        <TelemetryStrip metrics={metrics} hashChainValid={hashChainValid} />

        {/* Console Header Bar */}
        <header className="bg-[#FFFDF9] border-b border-[#EAE2D4] px-6 py-3 flex items-center justify-between shadow-[0_1px_2px_rgba(100,80,50,0.02)]">
          <div className="flex items-center space-x-3">
            <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">ControlPlane Console</span>
            <span className="text-stone-300">/</span>
            <span className="text-xs font-bold text-stone-900">
              {activeTab === 'screen0' && '0. The Catch'}
              {activeTab === 'screen1' && '1. Three Verdicts Demo'}
              {activeTab === 'screen2' && '2. Threshold Frontier Demo'}
              {activeTab === 'screen3' && '3. Abstention Demo'}
              {activeTab === 'screen4' && '4. Compounding & Quality Dial'}
              {activeTab === 'screen5' && '5. Calibration & the Enforcing Gate'}
              {activeTab === 'screen6' && '6. Agentic Consequence'}
              {activeTab === 'ledger' && 'Audit Ledger'}
              {activeTab === 'playground' && 'Live Adjudication Playground'}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode('landing')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-stone-700 bg-stone-100 hover:bg-[#F0EAE0] border border-stone-200 transition flex items-center space-x-1.5"
            >
              <Home className="w-3.5 h-3.5 text-stone-500" />
              <span>Landing Page</span>
            </button>
          </div>
        </header>

        {/* Tab View Container */}
        <main className="flex-1 p-6 overflow-y-auto max-w-6xl w-full mx-auto">
          {activeTab === 'screen0' && <Screen0LiveCatch />}
          {activeTab === 'screen1' && <Screen1Verdicts />}
          {activeTab === 'screen2' && <Screen2ThresholdSlider />}
          {activeTab === 'screen3' && <Screen3Abstention />}
          {activeTab === 'screen4' && <Screen4CompoundingDial />}
          {activeTab === 'screen5' && <Screen5Calibration />}
          {activeTab === 'screen6' && <Screen6Agentic />}
          {activeTab === 'ledger' && <LedgerView />}
          {activeTab === 'playground' && <LivePlayground />}
        </main>

        {/* Footer */}
        <footer className="border-t border-[#EAE2D4] bg-[#F7F2E8] py-3 text-center text-[11px] text-stone-500 font-mono">
          ControlPlane.ai · Consequence-Aware AI Intervention Layer · Round 2 Prototype
        </footer>
      </div>
    </div>
  );
}
