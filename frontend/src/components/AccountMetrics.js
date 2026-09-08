import React from "react";
import { C, fmt } from "./ui-kit";

function Stat({ label, value, color, testid, prefix = "", suffix = "" }) {
  return (
    <div style={{ padding: "12px 14px", borderRight: `1px solid ${C.border}`, minWidth: 130, flex: 1 }}>
      <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.16em", textTransform: "uppercase" }}>{label}</div>
      <div data-testid={testid} className="mono" style={{ fontSize: 20, fontWeight: 800, color: color || C.txt, marginTop: 4 }}>
        {prefix}{value}{suffix}
      </div>
    </div>
  );
}

export function AccountMetrics({ state, account }) {
  const eq = account?.account?.equity ?? 0;
  const avail = account?.account?.available ?? 0;
  const upnl = state?.unrealized_pnl ?? 0;
  const rpnl = state?.daily?.realized_pnl ?? 0;
  const today = rpnl + upnl;
  const pnlColor = (v) => (v > 0 ? C.profit : v < 0 ? C.danger : C.txt);
  const acct = account?.account;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", borderBottom: `1px solid ${C.border}`, background: C.panel }}>
      <Stat label="Account Equity" value={fmt(eq, 4)} suffix=" USD" testid="account-equity-val" />
      <Stat label="Available Margin" value={fmt(avail, 4)} suffix=" USD" />
      <Stat label="Realized P&L (today)" value={fmt(rpnl, 4)} color={pnlColor(rpnl)} />
      <Stat label="Unrealized P&L" value={fmt(upnl, 4)} color={pnlColor(upnl)} />
      <Stat label="Today Net P&L" value={fmt(today, 4)} color={pnlColor(today)} testid="account-pnl-today-val" />
      <Stat label="Daily Trades" value={state?.daily?.trades ?? 0} />
      <Stat label="Open Positions" value={state?.open_positions ?? 0} color={C.cyan} />
      <Stat label="Open Orders" value={state?.open_orders_count ?? 0} color={C.cyan} />
    </div>
  );
}
