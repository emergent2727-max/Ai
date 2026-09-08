import React, { useState } from "react";
import { AlertTriangle, XCircle, ShieldAlert } from "lucide-react";
import { C } from "./ui-kit";
import { overlay, modal, ghostBtn, solidBtn } from "./LiveTradingModal";
import { toast } from "sonner";

export function EmergencyControls({ onCancelOrders, onClosePositions }) {
  const [confirmClose, setConfirmClose] = useState(false);
  const [text, setText] = useState("");

  const cancel = async () => {
    try { await onCancelOrders(); toast.success("Cancel-all-orders request sent to Delta"); }
    catch { toast.error("Failed"); }
  };
  const close = async () => {
    try { await onClosePositions(text); toast.success("Emergency close executed & bot paused"); setConfirmClose(false); setText(""); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <ShieldAlert size={13} style={{ color: C.danger }} />
        <span className="font-display" style={{ fontSize: 13, letterSpacing: "0.1em" }}>EMERGENCY ACTION CENTER</span>
      </div>
      <div style={{ padding: 16, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div className="mono" style={{ fontSize: 11, color: C.txt3, width: "100%", marginBottom: 4 }}>
          Safety controls only — not the normal trading workflow. The kill switch is in the top bar.
        </div>
        <button data-testid="emergency-cancel-orders-btn" onClick={cancel} style={{ ...actionBtn(C.amber) }}>
          <XCircle size={15} /> CANCEL ALL OPEN ORDERS
        </button>
        <button data-testid="emergency-close-positions-btn" onClick={() => setConfirmClose(true)} style={{ ...actionBtn(C.danger) }}>
          <AlertTriangle size={15} /> EMERGENCY CLOSE ALL POSITIONS
        </button>
      </div>

      {confirmClose && (
        <div style={overlay}>
          <div className="fade-in" style={{ ...modal, borderColor: C.danger, width: 440 }}>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 900, color: C.danger, marginBottom: 12 }}>CONFIRM EMERGENCY CLOSE</div>
            <div className="mono" style={{ fontSize: 12, color: C.txt2, marginBottom: 12 }}>
              This market-closes ALL open positions immediately and pauses the bot. Type <b style={{ color: C.amber }}>CLOSE ALL</b> to confirm.
            </div>
            <input className="dk" value={text} onChange={(e) => setText(e.target.value)} placeholder="CLOSE ALL" style={{ marginBottom: 16 }} />
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button onClick={() => setConfirmClose(false)} style={ghostBtn}>CANCEL</button>
              <button disabled={text.trim().toUpperCase() !== "CLOSE ALL"} onClick={close}
                style={{ ...solidBtn(C.danger), opacity: text.trim().toUpperCase() === "CLOSE ALL" ? 1 : 0.4 }}>CLOSE ALL</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const actionBtn = (c) => ({ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 8, border: `1px solid ${c}55`, background: `${c}14`, color: c, cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 700, letterSpacing: "0.06em", flex: 1, minWidth: 240, justifyContent: "center" });
