import React from "react";
import { Cpu, TrendingUp, TrendingDown } from "lucide-react";
import { C, Bar, Tag, fmt, decisionColor } from "./ui-kit";

const REGIME_COLOR = {
  TRENDING_UP: C.profit, BREAKOUT: C.profit, TRENDING_DOWN: C.danger, BREAKDOWN: C.danger,
  RANGING: C.txt2, HIGH_VOLATILITY: C.amber, LOW_VOLATILITY: C.txt3, UNCERTAIN: C.txt3,
};

function ScoreRow({ label, value }) {
  const col = value >= 58 ? C.profit : value <= 42 ? C.danger : C.cyan;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 10, color: C.txt2, letterSpacing: "0.1em", textTransform: "uppercase" }}>{label}</span>
        <span className="mono" style={{ fontSize: 11, fontWeight: 700, color: col }}>{fmt(value, 0)}</span>
      </div>
      <Bar value={value} color={col} />
    </div>
  );
}

export function BotBrainAnalysis({ analysis, symbol, setSymbol }) {
  const symbols = analysis.map((a) => a.symbol);
  const snap = analysis.find((a) => a.symbol === symbol) || analysis[0];

  return (
    <div className="panel" data-testid="bot-brain-panel" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="panel-head">
        <Cpu size={13} style={{ color: C.cyan }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>CURRENT MARKET ANALYSIS</span>
        <select data-testid="symbol-selector-dropdown" className="dk" value={snap?.symbol || ""}
          onChange={(e) => setSymbol(e.target.value)}
          style={{ marginLeft: "auto", width: 130, padding: "4px 8px", fontSize: 12 }}>
          {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {!snap ? (
        <div style={{ padding: 24, color: C.txt3 }} className="mono">Bot warming up — collecting live market data…</div>
      ) : (
        <div style={{ padding: 16, overflowY: "auto" }} className="fade-in">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div>
              <div className="font-display" style={{ fontSize: 26, fontWeight: 900 }}>{snap.symbol}</div>
              <div className="mono" style={{ fontSize: 14, color: C.txt }}>{fmt(snap.price, 4)}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.14em" }}>MARKET REGIME</div>
              <Tag color={REGIME_COLOR[snap.regime] || C.txt2}>{snap.regime}</Tag>
              <div style={{ marginTop: 6 }}>
                <Tag color={snap.direction === "bullish" ? C.profit : snap.direction === "bearish" ? C.danger : C.txt2}>
                  MTF {fmt(snap.alignment, 0)} · {snap.direction}
                </Tag>
              </div>
            </div>
          </div>

          <ScoreRow label="Technical" value={snap.decision?.components?.technical ?? 50} />
          <ScoreRow label="Structure" value={snap.decision?.components?.structure ?? 50} />
          <ScoreRow label="Volume / Momentum" value={snap.decision?.components?.volume ?? 50} />
          <ScoreRow label="Order Flow" value={snap.decision?.components?.orderflow ?? 50} />
          <ScoreRow label="Sentiment" value={snap.decision?.components?.sentiment ?? 50} />
          <ScoreRow label="News" value={snap.decision?.components?.news ?? 50} />
          <ScoreRow label="Regime" value={snap.decision?.components?.regime ?? 50} />

          <div style={{ display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" }}>
            <MiniStat label="RSI" value={fmt(snap.ta?.entry?.rsi, 1)} />
            <MiniStat label="ADX" value={fmt(snap.ta?.entry?.adx, 1)} />
            <MiniStat label="ATR" value={fmt(snap.ta?.entry?.atr, 2)} />
            <MiniStat label="VOL x" value={fmt(snap.ta?.entry?.volume_ratio, 2)} />
            <MiniStat label="SENT" value={fmt(snap.sentiment, 0)} color={snap.sentiment > 0 ? C.profit : C.danger} />
            <MiniStat label="NEWS" value={snap.news_score === null ? "N/A" : fmt(snap.news_score, 0)} />
          </div>

          {/* panic gauge */}
          <div data-testid="panic-level-gauge" style={{ padding: 10, background: "#0B0F14", borderRadius: 6, border: `1px solid ${C.border}`, marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span className="mono" style={{ fontSize: 10, color: C.txt2, letterSpacing: "0.12em" }}>PANIC DETECTION</span>
              <Tag color={snap.panic?.level === "NORMAL" ? C.profit : snap.panic?.level === "EXTREME" ? C.danger : C.amber}>{snap.panic?.level}</Tag>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div className="mono" style={{ fontSize: 9, color: C.danger }}>SELL {fmt(snap.panic?.panic_sell, 0)}</div>
                <Bar value={snap.panic?.panic_sell || 0} color={C.danger} height={5} />
              </div>
              <div style={{ flex: 1 }}>
                <div className="mono" style={{ fontSize: 9, color: C.profit }}>BUY {fmt(snap.panic?.panic_buy, 0)}</div>
                <Bar value={snap.panic?.panic_buy || 0} color={C.profit} height={5} />
              </div>
            </div>
          </div>

          {/* confidence + decision */}
          <div data-testid="bot-confidence-meter" style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span className="mono" style={{ fontSize: 10, color: C.txt2, letterSpacing: "0.12em" }}>CONFIDENCE</span>
              <span className="mono" style={{ fontSize: 13, fontWeight: 800, color: C.cyan }}>{fmt(snap.decision?.confidence, 0)}%</span>
            </div>
            <Bar value={snap.decision?.confidence || 0} color={C.cyan} height={8} />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", borderRadius: 8, background: `${decisionColor(snap.decision?.action)}14`, border: `1px solid ${decisionColor(snap.decision?.action)}55`, marginTop: 8 }}>
            {snap.decision?.direction === "bullish" ? <TrendingUp size={22} style={{ color: decisionColor(snap.decision?.action) }} /> : <TrendingDown size={22} style={{ color: decisionColor(snap.decision?.action) }} />}
            <div>
              <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.16em" }}>BOT DECISION</div>
              <div data-testid="bot-decision-badge" className="font-display" style={{ fontSize: 24, fontWeight: 900, color: decisionColor(snap.decision?.action) }}>
                {(snap.decision?.action || "NO_TRADE").replace(/_/g, " ")}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="mono" style={{ fontSize: 9, color: C.txt3, letterSpacing: "0.16em", marginBottom: 6 }}>REASONING FACTORS</div>
            {(snap.decision?.reasons || []).map((r, i) => (
              <div key={i} className="mono" style={{ fontSize: 11, color: C.txt2, padding: "3px 0", borderBottom: `1px solid ${C.border}` }}>
                <span style={{ color: C.cyan }}>{i + 1}.</span> {r}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ background: "#0B0F14", border: `1px solid ${C.border}`, borderRadius: 6, padding: "6px 10px", flex: "1 0 auto", minWidth: 72 }}>
      <div className="mono" style={{ fontSize: 8, color: C.txt3, letterSpacing: "0.14em" }}>{label}</div>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: color || C.txt }}>{value}</div>
    </div>
  );
}
