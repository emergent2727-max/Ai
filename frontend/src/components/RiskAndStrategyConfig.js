import React, { useState, useEffect } from "react";
import { Sliders, Save } from "lucide-react";
import { C } from "./ui-kit";
import { toast } from "sonner";

const RISK_FIELDS = [
  ["max_risk_per_trade_pct", "Max Risk / Trade %"],
  ["max_position_size_usd", "Max Position Size (USD)"],
  ["max_daily_loss_usd", "Max Daily Loss (USD)"],
  ["max_daily_trades", "Max Daily Trades"],
  ["max_open_positions", "Max Open Positions"],
  ["max_leverage", "Max Leverage"],
  ["max_slippage_pct", "Max Slippage %"],
  ["min_expected_net_profit_pct", "Min Net Profit % (after fees)"],
  ["min_confidence", "Min Confidence"],
  ["min_risk_reward", "Min Risk : Reward"],
  ["max_consecutive_losses", "Max Consecutive Losses"],
];
const WEIGHTS = ["technical", "structure", "volume", "sentiment", "news", "regime", "orderflow"];

export function RiskAndStrategyConfig({ config, onSave }) {
  const [risk, setRisk] = useState({});
  const [weights, setWeights] = useState({});

  useEffect(() => {
    if (config) { setRisk(config.risk || {}); setWeights(config.weights || {}); }
  }, [config]);

  const save = async () => {
    try {
      await onSave({ risk, weights });
      toast.success("Configuration saved — server-side limits updated");
    } catch (e) { toast.error("Save failed"); }
  };

  return (
    <div className="panel" data-testid="risk-config-form">
      <div className="panel-head">
        <Sliders size={13} style={{ color: C.cyan }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>RISK LIMITS & STRATEGY WEIGHTS</span>
        <button onClick={save} data-testid="save-config-btn" style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center", padding: "6px 12px", borderRadius: 6, border: `1px solid ${C.cyan}`, background: `${C.cyan}18`, color: C.cyan, cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 700 }}>
          <Save size={12} /> SAVE
        </button>
      </div>
      <div className="rc-grid" style={{ padding: 16 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.txt3, letterSpacing: "0.14em", marginBottom: 10 }}>HARD RISK LIMITS (SERVER-ENFORCED)</div>
          {RISK_FIELDS.map(([k, label]) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span className="mono" style={{ fontSize: 11, color: C.txt2, flex: 1 }}>{label}</span>
              <input className="dk" data-testid={`risk-${k}`} type="number" step="any" style={{ width: 100 }}
                value={risk[k] ?? ""} onChange={(e) => setRisk({ ...risk, [k]: parseFloat(e.target.value) })} />
            </div>
          ))}
        </div>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.txt3, letterSpacing: "0.14em", marginBottom: 10 }}>DECISION WEIGHTS (%)</div>
          {WEIGHTS.map((k) => (
            <div key={k} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span className="mono" style={{ fontSize: 11, color: C.txt2, textTransform: "capitalize" }}>{k}</span>
                <span className="mono" style={{ fontSize: 11, color: C.cyan }}>{weights[k] ?? 0}%</span>
              </div>
              <input type="range" min="0" max="40" data-testid={`weight-${k}`} value={weights[k] ?? 0}
                onChange={(e) => setWeights({ ...weights, [k]: parseInt(e.target.value) })}
                style={{ width: "100%", accentColor: C.cyan }} />
            </div>
          ))}
          <div className="mono" style={{ fontSize: 10, color: C.txt3, marginTop: 8 }}>
            Total: {Object.values(weights).reduce((a, b) => a + (b || 0), 0)}% (normalized automatically)
          </div>
        </div>
      </div>
    </div>
  );
}
