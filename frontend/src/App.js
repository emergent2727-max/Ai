import React, { useEffect, useState, useCallback } from "react";
import "./App.css";
import { Toaster, toast } from "sonner";
import { LayoutGrid, Sliders, ShieldAlert } from "lucide-react";
import { api } from "./lib/api";
import { C } from "./components/ui-kit";
import { AutonomousStatusBar } from "./components/AutonomousStatusBar";
import { ConnectionHealthBar } from "./components/ConnectionHealthBar";
import { AccountMetrics } from "./components/AccountMetrics";
import { BotBrainAnalysis } from "./components/BotBrainAnalysis";
import { LiveMarketEvents } from "./components/LiveMarketEvents";
import { DecisionTimelineFeed } from "./components/DecisionTimelineFeed";
import { PositionsAndOrders } from "./components/PositionsAndOrders";
import { RiskAndStrategyConfig } from "./components/RiskAndStrategyConfig";
import { LiveTradingModal } from "./components/LiveTradingModal";
import { EmergencyControls } from "./components/EmergencyControls";
import { NewsPanel } from "./components/NewsPanel";
import { StrategyPerformance } from "./components/StrategyPerformance";

export default function App() {
  const [state, setState] = useState(null);
  const [config, setConfig] = useState(null);
  const [analysis, setAnalysis] = useState([]);
  const [events, setEvents] = useState([]);
  const [feed, setFeed] = useState([]);
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [account, setAccount] = useState(null);
  const [news, setNews] = useState(null);
  const [perf, setPerf] = useState(null);
  const [symbol, setSymbol] = useState("BTCUSD");
  const [tab, setTab] = useState("intel");
  const [liveModal, setLiveModal] = useState(false);

  const poll = useCallback(async () => {
    try {
      const [s, a, e, f, p, o, ac, n] = await Promise.all([
        api.state(), api.analysis(), api.events(), api.feed(),
        api.positions(), api.orders(), api.account(), api.news(),
      ]);
      setState(s); setAnalysis(a); setEvents(e); setFeed(f);
      setPositions(p); setOrders(o); setAccount(ac); setNews(n);
      api.performance().then(setPerf).catch(() => {});
    } catch (err) { /* transient */ }
  }, []);

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
    poll();
    const id = setInterval(poll, 2500);
    return () => clearInterval(id);
  }, [poll]);

  const changeMode = async (mode) => {
    try {
      await api.setMode(mode);
      toast.success(`Mode → ${mode.toUpperCase()}`);
      poll();
      api.config().then(setConfig);
    } catch { toast.error("Mode change failed"); }
  };

  const enableLive = () => {
    if (state?.mode === "off") { toast.error("Select SPOT or FUTURES first"); return; }
    setLiveModal(true);
  };
  const confirmLive = async (text) => {
    await api.setLive(true, text);
    api.config().then(setConfig);
    poll();
  };
  const resume = async () => {
    try { await api.resume(); toast.success("Autonomous trading RESUMED"); poll(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Cannot resume"); }
  };
  const stop = async () => { await api.stop(); toast("Kill switch engaged — new entries stopped", { icon: "■" }); poll(); };

  const saveConfig = async (body) => { await api.updateConfig(body); api.config().then(setConfig); };

  return (
    <div className="App">
      <Toaster theme="dark" position="top-right" richColors />
      <AutonomousStatusBar state={state} onMode={changeMode} onEnableLive={enableLive} onStop={stop} onResume={resume} />
      <ConnectionHealthBar conn={state?.connection} />
      <AccountMetrics state={state} account={account} />

      {/* tabs */}
      <div style={{ display: "flex", gap: 4, padding: "10px 18px 0", background: C.bg }}>
        {[["intel", "INTELLIGENCE", LayoutGrid], ["work", "POSITIONS & CONFIG", Sliders], ["safety", "EMERGENCY", ShieldAlert]].map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`tab-${k}`}
            style={{ display: "flex", alignItems: "center", gap: 7, padding: "9px 16px", border: "none", cursor: "pointer",
              borderBottom: `2px solid ${tab === k ? C.cyan : "transparent"}`, background: "transparent",
              color: tab === k ? C.txt : C.txt3, fontFamily: "'Barlow Condensed',sans-serif", fontSize: 15, fontWeight: 700, letterSpacing: "0.08em" }}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      <div style={{ padding: 18, background: C.bg, minHeight: "70vh" }}>
        {tab === "intel" && (
          <div data-testid="core-intelligence-section" className="intel-grid">
            <BotBrainAnalysis analysis={analysis} symbol={symbol} setSymbol={setSymbol} />
            <div className="intel-col">
              <LiveMarketEvents events={events} />
              <NewsPanel news={news} />
            </div>
            <DecisionTimelineFeed feed={feed} />
          </div>
        )}
        {tab === "work" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <PositionsAndOrders positions={positions} orders={orders} onProtect={api.protect} />
            <StrategyPerformance perf={perf} />
            <RiskAndStrategyConfig config={config} onSave={saveConfig} />
          </div>
        )}
        {tab === "safety" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 900 }}>
            <EmergencyControls onCancelOrders={api.cancelOrders} onClosePositions={api.closePositions} />
            {state?.paused_reason && (
              <div className="panel" style={{ padding: 16 }}>
                <div className="mono" style={{ fontSize: 11, color: C.amber, letterSpacing: "0.1em" }}>CURRENT PAUSE REASON</div>
                <div className="mono" style={{ fontSize: 13, color: C.txt, marginTop: 6 }}>{state.paused_reason}</div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ padding: "14px 18px", background: C.bg, borderTop: `1px solid ${C.border}`, textAlign: "center" }}>
        <span className="mono" style={{ fontSize: 10, color: C.txt3, letterSpacing: "0.1em" }}>
          DACTE · REAL MONEY · CAPITAL PROTECTION &gt; TRADE FREQUENCY · NO PAPER TRADING · NO TESTNET · IF UNCERTAIN → NO TRADE
        </span>
      </div>

      <LiveTradingModal open={liveModal} onClose={() => setLiveModal(false)} onConfirm={confirmLive} mode={state?.mode} />
    </div>
  );
}
