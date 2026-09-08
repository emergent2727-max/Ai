import React from "react";
import { BarChart3 } from "lucide-react";
import { C, fmt } from "./ui-kit";

function Cell({ label, value, color }) {
  return (
    <div style={{ padding: "10px 14px", borderRight: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}`, flex: "1 0 130px" }}>
      <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.14em", textTransform: "uppercase" }}>{label}</div>
      <div className="mono" style={{ fontSize: 18, fontWeight: 800, color: color || C.txt, marginTop: 3 }}>{value}</div>
    </div>
  );
}

export function StrategyPerformance({ perf }) {
  if (!perf) return null;
  return (
    <div className="panel" data-testid="performance-panel">
      <div className="panel-head">
        <BarChart3 size={13} style={{ color: C.cyan }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>STRATEGY PERFORMANCE (REAL FILLS)</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        <Cell label="Decisions" value={perf.total_decisions} />
        <Cell label="Executed" value={perf.executed} color={C.profit} />
        <Cell label="No-Trade" value={perf.no_trade} color={C.txt2} />
        <Cell label="Exec Failed" value={perf.exec_failed} color={perf.exec_failed ? C.danger : C.txt2} />
        <Cell label="Fills" value={perf.fills_count} />
        <Cell label="Realized P&L" value={fmt(perf.realized_pnl_from_fills, 4)} color={perf.realized_pnl_from_fills >= 0 ? C.profit : C.danger} />
        <Cell label="Total Fees" value={fmt(perf.total_fees, 4)} color={C.amber} />
        <Cell label="Win Rate" value={perf.win_rate === null ? "—" : `${perf.win_rate}%`} color={C.cyan} />
        <Cell label="Avg Conf (exec)" value={fmt(perf.avg_confidence_executed, 0)} />
      </div>
      <div className="mono" style={{ padding: "8px 14px", fontSize: 10, color: C.txt3 }}>{perf.note}</div>
    </div>
  );
}
