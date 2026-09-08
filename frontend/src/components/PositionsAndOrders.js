import React from "react";
import { C, fmt } from "./ui-kit";

export function PositionsAndOrders({ positions, orders }) {
  return (
    <div className="po-grid">
      <div className="panel" data-testid="positions-table">
        <div className="panel-head"><span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>ACTIVE POSITIONS</span></div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr>{["SYMBOL", "SIDE", "SIZE", "ENTRY", "MARK", "uPnL", "LIQ"].map((h) => (
              <th key={h} className="mono" style={th}>{h}</th>))}</tr></thead>
            <tbody>
              {(!positions || positions.length === 0) ? (
                <tr><td colSpan={7} className="mono" style={{ padding: 16, color: C.txt3, fontSize: 12 }}>No open positions.</td></tr>
              ) : positions.map((p, i) => (
                <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td className="mono" style={td}>{p.symbol}</td>
                  <td className="mono" style={{ ...td, color: p.side === "long" ? C.profit : C.danger }}>{p.side?.toUpperCase()}</td>
                  <td className="mono" style={td}>{p.size}</td>
                  <td className="mono" style={td}>{fmt(p.entry_price, 4)}</td>
                  <td className="mono" style={td}>{fmt(p.mark_price, 4)}</td>
                  <td className="mono" style={{ ...td, color: p.unrealized_pnl >= 0 ? C.profit : C.danger }}>{fmt(p.unrealized_pnl, 4)}</td>
                  <td className="mono" style={td}>{fmt(p.liquidation_price, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel" data-testid="orders-table">
        <div className="panel-head"><span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>WORKING ORDERS</span></div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr>{["SYMBOL", "SIDE", "SIZE", "UNFILLED", "PRICE", "TYPE", "STATE"].map((h) => (
              <th key={h} className="mono" style={th}>{h}</th>))}</tr></thead>
            <tbody>
              {(!orders || orders.length === 0) ? (
                <tr><td colSpan={7} className="mono" style={{ padding: 16, color: C.txt3, fontSize: 12 }}>No working orders.</td></tr>
              ) : orders.map((o, i) => (
                <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td className="mono" style={td}>{o.symbol}</td>
                  <td className="mono" style={{ ...td, color: o.side === "buy" ? C.profit : C.danger }}>{o.side?.toUpperCase()}</td>
                  <td className="mono" style={td}>{o.size}</td>
                  <td className="mono" style={td}>{o.unfilled_size}</td>
                  <td className="mono" style={td}>{o.limit_price || "MKT"}</td>
                  <td className="mono" style={td}>{o.order_type}</td>
                  <td className="mono" style={td}>{o.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const th = { textAlign: "left", padding: "8px 10px", fontSize: 9, color: C.txt3, letterSpacing: "0.12em", fontWeight: 700 };
const td = { padding: "8px 10px", fontSize: 12, color: C.txt };
