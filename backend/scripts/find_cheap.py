import asyncio
from trading.delta import client, DeltaError

async def main():
    try:
        bals = await client.get_balances()
        for w in bals:
            b = float(w.get("balance") or 0); a = float(w.get("available_balance") or 0)
            if b or a:
                print(f"BAL {w.get('asset_symbol')}: balance={b} available={a}")
    except DeltaError as e:
        print("bal err", e.payload)

    prods = await client.get_products(contract_types="perpetual_futures")
    tick = await client.get_tickers(contract_types="perpetual_futures")
    tmap = {t.get("symbol"): t for t in (tick or [])}
    rows = []
    for p in prods:
        sym = p["symbol"]
        cv = float(p.get("contract_value") or 0)
        t = tmap.get(sym) or {}
        mp = float(t.get("mark_price") or 0)
        turn = float(t.get("turnover_usd") or 0)
        lev = p.get("leverage") or p.get("default_leverage") or 1
        if cv and mp and turn > 500000:  # liquid only
            notional1 = cv * mp
            rows.append((notional1, sym, cv, mp, turn, lev, p.get("id")))
    rows.sort()
    print("\nSMALLEST 1-CONTRACT NOTIONAL (liquid perps):")
    for notional1, sym, cv, mp, turn, lev, pid in rows[:14]:
        print(f"  {sym:14s} 1ctr=${notional1:8.4f}  cv={cv}  price={mp}  maxLev={lev}  turnover=${turn/1e6:.1f}M id={pid}")
    await client.close()

asyncio.run(main())
