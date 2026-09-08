import React, { useState } from "react";
import { ShieldAlert, X } from "lucide-react";
import { C } from "./ui-kit";
import { toast } from "sonner";

export function LiveTradingModal({ open, onClose, onConfirm, mode }) {
  const [text, setText] = useState("");
  if (!open) return null;
  const ready = text.trim().toUpperCase() === "ENABLE REAL CAPITAL";

  const submit = async () => {
    try {
      await onConfirm(text);
      toast.success("Live capital ENABLED. Press RESUME BOT to start autonomous trading.");
      setText("");
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to enable");
    }
  };

  return (
    <div style={overlay}>
      <div data-testid="live-trading-confirm-modal" className="fade-in" style={{ ...modal, borderColor: C.danger }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <ShieldAlert size={26} style={{ color: C.danger }} />
          <div className="font-display" style={{ fontSize: 22, fontWeight: 900, color: C.danger }}>ENABLE LIVE AUTONOMOUS TRADING</div>
          <button onClick={onClose} style={{ marginLeft: "auto", background: "none", border: "none", color: C.txt2, cursor: "pointer" }}><X size={20} /></button>
        </div>
        <div style={{ background: "rgba(248,81,73,0.10)", border: `1px solid ${C.danger}55`, borderRadius: 8, padding: 14, marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 13, color: C.txt, lineHeight: 1.6 }}>
            <b style={{ color: C.danger }}>WARNING:</b> This application can place <b>real orders</b> using your Delta Exchange India account in <b>{(mode || "off").toUpperCase()}</b> mode.
            <br />Real money can be gained or lost. The autonomous engine will observe, decide, and execute on its own within your risk limits.
          </div>
        </div>
        <div className="mono" style={{ fontSize: 11, color: C.txt2, marginBottom: 6 }}>
          Type <b style={{ color: C.amber }}>ENABLE REAL CAPITAL</b> to confirm:
        </div>
        <input data-testid="confirm-live-input" className="dk" value={text} onChange={(e) => setText(e.target.value)}
          placeholder="ENABLE REAL CAPITAL" style={{ marginBottom: 16 }} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={ghostBtn}>CANCEL</button>
          <button data-testid="confirm-live-submit-btn" disabled={!ready} onClick={submit}
            style={{ ...solidBtn(C.danger), opacity: ready ? 1 : 0.4, cursor: ready ? "pointer" : "not-allowed" }}>
            ENABLE REAL CAPITAL
          </button>
        </div>
      </div>
    </div>
  );
}

export const overlay = { position: "fixed", inset: 0, background: "rgba(3,5,8,0.8)", backdropFilter: "blur(6px)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 };
export const modal = { background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, padding: 24, width: 520, maxWidth: "100%" };
export const ghostBtn = { padding: "9px 16px", borderRadius: 7, border: `1px solid ${C.border}`, background: "transparent", color: C.txt2, cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 700 };
export const solidBtn = (c) => ({ padding: "9px 16px", borderRadius: 7, border: `1px solid ${c}`, background: `${c}22`, color: c, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 800, letterSpacing: "0.06em" });
