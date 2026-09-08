import asyncio, json
from trading.delta import client, DeltaError

async def main():
    print("EGRESS/whitelist test:")
    try:
        bals = await client.get_balances()
        print("  balances OK, required_ip:", client.required_ip)
        for w in bals:
            b = float(w.get("balance") or 0)
            a = float(w.get("available_balance") or 0)
            if b or a:
                print(f"  {w.get('asset_symbol')}: balance={b} available={a}")
    except DeltaError as e:
        print("  balances ERR", e.payload)
    try:
        pos = await client.get_positions_margined()
        print("positions:", pos)
    except DeltaError as e:
        print("positions ERR", e.payload)
    await client.close()

asyncio.run(main())
