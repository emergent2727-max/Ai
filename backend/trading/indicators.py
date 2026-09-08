"""Deterministic technical analysis, market structure & regime engines (numpy)."""
import numpy as np


def _ema(arr, period):
    if len(arr) < period:
        return np.full(len(arr), np.nan)
    alpha = 2 / (period + 1)
    out = np.empty(len(arr))
    out[:] = np.nan
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = arr[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def _rsi(close, period=14):
    if len(close) <= period:
        return np.nan
    d = np.diff(close)
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ag = up[:period].mean()
    al = dn[:period].mean()
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + up[i]) / period
        al = (al * (period - 1) + dn[i]) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return float(100 - 100 / (1 + rs))


def _atr(high, low, close, period=14):
    if len(close) <= period:
        return np.nan
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    atr = tr[:period].mean()
    for i in range(period, len(tr)):
        atr = (atr * (period - 1) + tr[i]) / period
    return float(atr)


def _adx(high, low, close, period=14):
    if len(close) <= period * 2:
        return np.nan
    up = high[1:] - high[:-1]
    dn = low[:-1] - low[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    tr = np.where(tr == 0, 1e-9, tr)
    atr = np.convolve(tr, np.ones(period) / period, mode="valid")
    pdi = 100 * np.convolve(plus_dm, np.ones(period) / period, mode="valid") / atr
    mdi = 100 * np.convolve(minus_dm, np.ones(period) / period, mode="valid") / atr
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, 1e-9, (pdi + mdi))
    if len(dx) < period:
        return float(dx.mean()) if len(dx) else np.nan
    return float(dx[-period:].mean())


def _macd(close):
    e12 = _ema(close, 12)
    e26 = _ema(close, 26)
    macd = e12 - e26
    valid = macd[~np.isnan(macd)]
    if len(valid) < 9:
        return 0.0, 0.0, 0.0
    signal = _ema(valid, 9)
    return float(valid[-1]), float(signal[-1]), float(valid[-1] - signal[-1])


def _vwap(high, low, close, vol):
    tp = (high + low + close) / 3
    cv = np.cumsum(vol)
    if cv[-1] == 0:
        return float(close[-1])
    return float(np.cumsum(tp * vol)[-1] / cv[-1])


def _swings(high, low, lb=3):
    highs, lows = [], []
    for i in range(lb, len(high) - lb):
        if high[i] == max(high[i - lb:i + lb + 1]):
            highs.append((i, high[i]))
        if low[i] == min(low[i - lb:i + lb + 1]):
            lows.append((i, low[i]))
    return highs, lows


def compute_ta(candles):
    """candles: ascending list of dicts with open/high/low/close/volume."""
    if not candles or len(candles) < 30:
        return None
    o = np.array([float(c["open"]) for c in candles])
    h = np.array([float(c["high"]) for c in candles])
    l = np.array([float(c["low"]) for c in candles])
    c = np.array([float(c["close"]) for c in candles])
    v = np.array([float(c["volume"]) for c in candles])
    price = float(c[-1])

    ema9 = _ema(c, 9)[-1]
    ema21 = _ema(c, 21)[-1]
    ema50 = _ema(c, 50)[-1] if len(c) >= 50 else np.nan
    ema200 = _ema(c, 200)[-1] if len(c) >= 200 else np.nan
    rsi = _rsi(c)
    macd, macd_sig, macd_hist = _macd(c)
    atr = _atr(h, l, c)
    adx = _adx(h, l, c)
    vwap = _vwap(h, l, c, v)
    mean = c[-20:].mean()
    std = c[-20:].std()
    bb_up, bb_lo, bb_mid = mean + 2 * std, mean - 2 * std, mean
    vol_ma = v[-20:].mean()
    momentum = float((c[-1] - c[-10]) / c[-10] * 100) if len(c) >= 10 else 0.0
    price_change = float((c[-1] - c[-2]) / c[-2] * 100)

    highs, lows = _swings(h, l)
    resistance = float(np.mean([p for _, p in highs[-3:]])) if highs else float(h[-20:].max())
    support = float(np.mean([p for _, p in lows[-3:]])) if lows else float(l[-20:].min())
    swing_high = float(highs[-1][1]) if highs else float(h.max())
    swing_low = float(lows[-1][1]) if lows else float(l.min())

    # bullish/bearish scoring 0..100
    score = 50.0
    if not np.isnan(ema9) and not np.isnan(ema21):
        score += 12 if ema9 > ema21 else -12
    if not np.isnan(ema50) and price > ema50:
        score += 8
    elif not np.isnan(ema50):
        score -= 8
    if not np.isnan(ema200):
        score += 6 if price > ema200 else -6
    if not np.isnan(rsi):
        if rsi > 70:
            score -= 6
        elif rsi < 30:
            score += 6
        else:
            score += (rsi - 50) * 0.2
    score += 8 if macd_hist > 0 else -8
    if not np.isnan(vwap):
        score += 5 if price > vwap else -5
    score = float(max(0, min(100, score)))

    def nn(x):
        return None if (x is None or (isinstance(x, float) and np.isnan(x))) else round(float(x), 4)

    return {
        "price": round(price, 4),
        "ema9": nn(ema9), "ema21": nn(ema21), "ema50": nn(ema50), "ema200": nn(ema200),
        "rsi": nn(rsi), "macd": nn(macd), "macd_signal": nn(macd_sig), "macd_hist": nn(macd_hist),
        "atr": nn(atr), "adx": nn(adx), "vwap": nn(vwap),
        "bb_upper": nn(bb_up), "bb_lower": nn(bb_lo), "bb_mid": nn(bb_mid),
        "volume": round(float(v[-1]), 2), "volume_ma": round(float(vol_ma), 2),
        "volume_ratio": round(float(v[-1] / vol_ma), 2) if vol_ma else 0.0,
        "momentum": round(momentum, 3), "price_change_pct": round(price_change, 3),
        "support": round(support, 4), "resistance": round(resistance, 4),
        "swing_high": round(swing_high, 4), "swing_low": round(swing_low, 4),
        "technical_score": round(score, 1),
        "bias": "bullish" if score >= 58 else ("bearish" if score <= 42 else "neutral"),
    }


def compute_structure(candles):
    if not candles or len(candles) < 30:
        return {"label": "UNCERTAIN", "structure_score": 50.0, "events": []}
    h = np.array([float(c["high"]) for c in candles])
    l = np.array([float(c["low"]) for c in candles])
    c = np.array([float(c["close"]) for c in candles])
    highs, lows = _swings(h, l)
    events = []
    score = 50.0
    label = "RANGING"
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1][1] > highs[-2][1]
        hl = lows[-1][1] > lows[-2][1]
        lh = highs[-1][1] < highs[-2][1]
        ll = lows[-1][1] < lows[-2][1]
        if hh and hl:
            label, score = "UPTREND_HH_HL", 74
            events.append("higher_high"); events.append("higher_low")
        elif lh and ll:
            label, score = "DOWNTREND_LH_LL", 26
            events.append("lower_high"); events.append("lower_low")
        elif hh and ll:
            label, score = "EXPANSION", 50
        else:
            label, score = "RANGING", 50
    res = float(np.mean([p for _, p in highs[-3:]])) if highs else float(h.max())
    sup = float(np.mean([p for _, p in lows[-3:]])) if lows else float(l.min())
    last = float(c[-1])
    if last > res:
        events.append("breakout"); score = min(100, score + 12)
    elif last < sup:
        events.append("breakdown"); score = max(0, score - 12)
    return {"label": label, "structure_score": round(float(score), 1),
            "support": round(sup, 4), "resistance": round(res, 4), "events": events}


def compute_regime(ta, structure):
    if not ta:
        return "UNCERTAIN"
    adx = ta.get("adx") or 0
    price = ta["price"]
    bb_w = 0
    if ta.get("bb_upper") and ta.get("bb_lower") and ta.get("bb_mid"):
        bb_w = (ta["bb_upper"] - ta["bb_lower"]) / ta["bb_mid"] * 100
    atr_pct = (ta.get("atr") or 0) / price * 100 if price else 0
    lbl = structure.get("label", "")
    if "breakout" in structure.get("events", []):
        return "BREAKOUT"
    if "breakdown" in structure.get("events", []):
        return "BREAKDOWN"
    if atr_pct > 2.5 or bb_w > 8:
        return "HIGH_VOLATILITY"
    if adx and adx > 25:
        if ta["bias"] == "bullish":
            return "TRENDING_UP"
        if ta["bias"] == "bearish":
            return "TRENDING_DOWN"
    if adx and adx < 15 and atr_pct < 0.8:
        return "LOW_VOLATILITY"
    if "UPTREND" in lbl:
        return "TRENDING_UP"
    if "DOWNTREND" in lbl:
        return "TRENDING_DOWN"
    return "RANGING"


def multi_timeframe_alignment(ta_trend, ta_setup, ta_entry):
    """Returns alignment score 0..100 and direction."""
    biases = [t["bias"] for t in (ta_trend, ta_setup, ta_entry) if t]
    if not biases:
        return 50.0, "neutral"
    bull = biases.count("bullish")
    bear = biases.count("bearish")
    if bull > bear:
        return round(50 + 50 * bull / len(biases), 1), "bullish"
    if bear > bull:
        return round(50 - 50 * bear / len(biases), 1), "bearish"
    return 50.0, "neutral"
