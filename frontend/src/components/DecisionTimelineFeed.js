import React from "react";
import { Terminal } from "lucide-react";
import { C } from "./ui-kit";

const TAG_COLOR = {
  analyze: C.cyan, exec: "#F0883E", risk: C.amber, manage: C.profit,
  error: C.danger, system: C.purple, info: C.txt2,
};

export function DecisionTimelineFeed({ feed }) {
  return (
    <div className="panel" data-testid="decision-feed-container" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="panel-head">
        <Terminal size={13} style={{ color: C.profit }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>LIVE DECISION FEED</span>
        <span className="blink" style={{ marginLeft: "auto", width: 7, height: 7, borderRadius: 7, background: C.profit }} />
      </div>
      <div style={{ overflowY: "auto", flex: 1, padding: "6px 0", background: "#070A0E" }}>
        {(!feed || feed.length === 0) ? (
          <div className="mono" style={{ padding: 16, color: C.txt3, fontSize: 12 }}>Awaiting bot activity…</div>
        ) : feed.map((f, i) => (
          <div key={i} className="mono fade-in" style={{ display: "flex", gap: 8, padding: "3px 14px", fontSize: 11, lineHeight: 1.5 }}>
            <span style={{ color: C.txt3, minWidth: 66 }}>{new Date(f.ts).toLocaleTimeString("en-US", { hour12: false })}</span>
            <span style={{ color: TAG_COLOR[f.tag] || C.txt2, minWidth: 62, fontWeight: 700 }}>[{(f.tag || "info").toUpperCase()}]</span>
            <span style={{ color: C.txt }}>{f.line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
