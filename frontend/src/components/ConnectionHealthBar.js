import React from "react";
import { Radio, AlertTriangle } from "lucide-react";
import { C } from "./ui-kit";

const LABELS = {
  rest: "DELTA REST", ws_public: "PUBLIC WS", ws_private: "PRIVATE WS",
  market_data: "MARKET DATA", news: "NEWS", account: "ACCOUNT",
};
const good = ["CONNECTED", "LIVE"];
const warn = ["STALE", "INIT", "UNAVAILABLE"];

function colorFor(v) {
  if (good.includes(v)) return C.profit;
  if (warn.includes(v)) return C.amber;
  return C.danger;
}

export function ConnectionHealthBar({ conn }) {
  if (!conn) return null;
  return (
    <div data-testid="connection-health-bar" style={{ borderBottom: `1px solid ${C.border}`, background: "#0A0E13" }}>
      <div data-testid="connection-health-grid" style={{ display: "flex", gap: 16, padding: "8px 18px", flexWrap: "wrap", alignItems: "center" }}>
        <Radio size={13} style={{ color: C.txt3 }} />
        {Object.keys(LABELS).map((k) => {
          const v = conn[k] || "INIT";
          const col = colorFor(v);
          return (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 6 }} data-testid={`health-${k}`}>
              <span style={{ width: 7, height: 7, borderRadius: 7, background: col, display: "inline-block" }} />
              <span className="mono" style={{ fontSize: 10, color: C.txt3, letterSpacing: "0.1em" }}>{LABELS[k]}</span>
              <span className="mono" style={{ fontSize: 10, fontWeight: 700, color: col, letterSpacing: "0.08em" }}>{v}</span>
            </div>
          );
        })}
        <div className="mono" style={{ fontSize: 10, color: C.txt3, marginLeft: "auto" }}>
          drift {conn.server_time_drift ?? 0}s · clock {conn.time_synced ? "SYNCED" : "DRIFT"}
        </div>
      </div>
      {conn.required_ip && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 18px", background: "rgba(210,153,34,0.10)", borderTop: `1px solid ${C.amber}44` }}>
          <AlertTriangle size={14} style={{ color: C.amber }} />
          <span className="mono" style={{ fontSize: 12, color: C.amber }}>
            ACCOUNT DATA BLOCKED — whitelist this server IP on your Delta API key:&nbsp;
            <b style={{ color: C.txt }}>{conn.required_ip}</b>
            &nbsp;(delta.exchange → API Management → edit key → add IP)
          </span>
        </div>
      )}
    </div>
  );
}
