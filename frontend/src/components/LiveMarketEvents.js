import React from "react";
import { Zap, AlertTriangle } from "lucide-react";
import { C, Bar, Tag, fmt } from "./ui-kit";

const SEV = (s) => (s === "CRITICAL" ? C.danger : s === "HIGH" ? C.amber : C.cyan);

export function LiveMarketEvents({ events }) {
  return (
    <div className="panel" data-testid="live-events-panel" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="panel-head">
        <Zap size={13} style={{ color: C.amber }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>LIVE MARKET EVENTS</span>
      </div>
      <div data-testid="market-events-list" style={{ overflowY: "auto", flex: 1 }}>
        {(!events || events.length === 0) ? (
          <div className="mono" style={{ padding: 20, color: C.txt3, fontSize: 12 }}>No abnormal events detected. Markets nominal.</div>
        ) : events.map((e, i) => {
          const sev = e.data?.severity ?? (e.severity === "CRITICAL" ? 90 : e.severity === "HIGH" ? 65 : 40);
          return (
            <div key={i} className="fade-in" style={{ padding: "10px 14px", borderBottom: `1px solid ${C.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <AlertTriangle size={13} style={{ color: SEV(e.severity) }} />
                <span className="font-display" style={{ fontSize: 14, fontWeight: 800, color: SEV(e.severity) }}>{e.kind?.replace(/_/g, " ")}</span>
                <span className="mono" style={{ fontSize: 11, color: C.txt }}>{e.symbol}</span>
                <Tag color={SEV(e.severity)}>{e.severity}</Tag>
                <span className="mono" style={{ fontSize: 9, color: C.txt3, marginLeft: "auto" }}>{new Date(e.ts).toLocaleTimeString()}</span>
              </div>
              <div className="mono" style={{ fontSize: 11, color: C.txt2, marginBottom: 6 }}>{e.message}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="mono" style={{ fontSize: 9, color: C.txt3 }}>SEVERITY</span>
                <div style={{ flex: 1 }}><Bar value={sev} color={SEV(e.severity)} height={5} /></div>
                <span className="mono" style={{ fontSize: 10, color: SEV(e.severity) }}>{fmt(sev, 0)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
