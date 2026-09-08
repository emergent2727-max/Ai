import React from "react";
import { Activity, Power, Square, Cpu, Zap } from "lucide-react";
import { C, stateColor, Tag } from "./ui-kit";

const STATES = ["ANALYZING", "WAITING", "SIGNAL", "EXECUTING", "MANAGING", "PAUSED"];

export function AutonomousStatusBar({ state, onMode, onEnableLive, onStop, onResume }) {
  const status = state?.status || "PAUSED";
  const botState = state?.state || "PAUSED";
  const mode = state?.mode || "off";
  const live = state?.live_trading;
  const statusColor = status === "ACTIVE" ? C.profit : status === "ERROR" ? C.danger : C.amber;
  const modeColor = mode === "spot" ? C.cyan : mode === "futures" ? C.purple : C.txt3;

  return (
    <div data-testid="autonomous-master-bar"
      style={{ background: "#0A0E13", borderBottom: `1px solid ${C.border}`, position: "sticky", top: 0, zIndex: 40 }}>
      <div className="grad-scan" />
      <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "12px 18px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Cpu size={22} style={{ color: C.cyan }} />
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 900, letterSpacing: "0.02em", lineHeight: 1 }}>
              DACTE <span style={{ color: C.txt3, fontSize: 12, fontWeight: 700 }}>AUTONOMOUS ENGINE</span>
            </div>
            <div className="mono" style={{ fontSize: 10, color: C.txt3, letterSpacing: "0.14em" }}>DELTA EXCHANGE INDIA · LIVE</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="pulse-dot" style={{ color: statusColor, width: 9, height: 9, borderRadius: 9, background: statusColor, display: "inline-block" }} />
          <div data-testid="bot-status-badge">
            <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.15em" }}>AUTONOMOUS TRADING</div>
            <div className="font-display" style={{ fontSize: 16, fontWeight: 800, color: statusColor }}>{status}</div>
          </div>
        </div>

        {/* mode selector */}
        <div data-testid="bot-mode-selector" style={{ display: "flex", gap: 4, background: "#0B0F14", padding: 4, borderRadius: 8, border: `1px solid ${C.border}` }}>
          {["off", "spot", "futures"].map((m) => (
            <button key={m} data-testid={`mode-${m}-btn`} onClick={() => onMode(m)}
              style={{
                padding: "6px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.1em",
                textTransform: "uppercase",
                background: mode === m ? (m === "spot" ? C.cyan : m === "futures" ? C.purple : "#30363D") : "transparent",
                color: mode === m ? "#06090D" : C.txt2,
              }}>
              {m === "off" ? "TRADING OFF" : m}
            </button>
          ))}
        </div>

        {/* state machine */}
        <div data-testid="bot-state-indicator" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          {STATES.map((s) => {
            const active = botState === s;
            return (
              <span key={s} className={active ? "blink" : ""} style={{
                fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                padding: "3px 7px", borderRadius: 4,
                color: active ? "#06090D" : C.txt3,
                background: active ? stateColor[s] : "transparent",
                border: `1px solid ${active ? stateColor[s] : C.border}`,
              }}>{s}</span>
            );
          })}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <Tag color={live ? C.profit : C.txt3}>{live ? "LIVE CAPITAL ON" : "LIVE CAPITAL OFF"}</Tag>
          {status !== "ACTIVE" ? (
            live && mode !== "off" ? (
              <button data-testid="resume-btn" onClick={onResume}
                style={btn(C.profit)}><Power size={13} /> RESUME BOT</button>
            ) : (
              <button data-testid="enable-live-trading-btn" onClick={onEnableLive}
                style={btn(C.cyan)}><Zap size={13} /> ENABLE LIVE TRADING</button>
            )
          ) : (
            <button data-testid="emergency-kill-switch-btn" onClick={onStop}
              style={btn(C.danger)}><Square size={13} /> KILL SWITCH</button>
          )}
        </div>
      </div>
    </div>
  );
}

const btn = (color) => ({
  display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 7,
  border: `1px solid ${color}`, background: `${color}18`, color,
  fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em",
  cursor: "pointer", textTransform: "uppercase",
});
