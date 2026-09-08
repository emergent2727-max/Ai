import React from "react";

export const C = {
  bg: "#080B10", panel: "#0D1117", elev: "#151B23", border: "#21262D",
  txt: "#F0F6FC", txt2: "#8B949E", txt3: "#6E7681",
  danger: "#F85149", profit: "#2EA043", amber: "#D29922", cyan: "#388BFD", purple: "#A371F7",
};

export const stateColor = {
  ANALYZING: "#388BFD", WAITING: "#8B949E", SIGNAL: "#E3B341",
  EXECUTING: "#F0883E", MANAGING: "#2EA043", PAUSED: "#DA3633", ERROR: "#F85149",
};

export const decisionColor = (a) => {
  if (["OPEN_LONG", "BUY", "CLOSE_SHORT"].includes(a)) return C.profit;
  if (["OPEN_SHORT", "SELL", "CLOSE_LONG"].includes(a)) return C.danger;
  if (a === "HOLD") return C.cyan;
  return C.txt3;
};

export const fmt = (n, d = 2) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
};

export function Panel({ title, icon: Icon, right, children, testid, className = "" }) {
  return (
    <div className={`panel ${className}`} data-testid={testid}>
      {title && (
        <div className="panel-head">
          {Icon && <Icon size={13} style={{ color: C.txt2 }} />}
          <span className="font-display" style={{ letterSpacing: "0.1em", fontSize: 13 }}>{title}</span>
          <div style={{ marginLeft: "auto" }}>{right}</div>
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}

export function Bar({ value, max = 100, color, height = 6 }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div style={{ background: "#161B22", borderRadius: 4, height, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width 0.6s ease" }} />
    </div>
  );
}

export function Tag({ children, color = C.txt2, bg }) {
  return (
    <span className="tag" style={{ color, background: bg || `${color}22`, border: `1px solid ${color}44` }}>
      {children}
    </span>
  );
}
