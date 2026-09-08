import React from "react";
import { Newspaper } from "lucide-react";
import { C, Tag } from "./ui-kit";

const SENT = (s) => (s === "BULLISH" ? C.profit : s === "BEARISH" ? C.danger : C.txt2);

export function NewsPanel({ news }) {
  const items = news?.items || [];
  return (
    <div className="panel" data-testid="news-panel" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="panel-head">
        <Newspaper size={13} style={{ color: C.cyan }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>NEWS & SENTIMENT</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {news?.sources && Object.entries(news.sources).map(([k, v]) => (
            <Tag key={k} color={v === "LIVE" ? C.profit : C.amber}>{k}:{v}</Tag>
          ))}
        </div>
      </div>
      <div style={{ overflowY: "auto", flex: 1 }}>
        {items.length === 0 ? (
          <div className="mono" style={{ padding: 16, color: C.txt3, fontSize: 12 }}>News feed UNAVAILABLE.</div>
        ) : items.map((n, i) => (
          <a key={i} href={n.url} target="_blank" rel="noreferrer"
            style={{ display: "block", padding: "10px 14px", borderBottom: `1px solid ${C.border}`, textDecoration: "none" }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 3, alignItems: "center" }}>
              <Tag color={SENT(n.sentiment)}>{n.sentiment}</Tag>
              <Tag color={n.importance === "CRITICAL" ? C.danger : n.importance === "HIGH" ? C.amber : C.txt3}>{n.importance}</Tag>
              <span className="mono" style={{ fontSize: 9, color: C.txt3, marginLeft: "auto" }}>{(n.assets || []).join(",")}</span>
            </div>
            <div style={{ fontSize: 12, color: C.txt, lineHeight: 1.4 }}>{n.headline}</div>
            <div className="mono" style={{ fontSize: 9, color: C.txt3, marginTop: 2 }}>{n.source}</div>
          </a>
        ))}
      </div>
    </div>
  );
}
