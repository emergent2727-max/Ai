import asyncio
from trading.delta import client, DeltaError

async def main():
    for fn, name in [(lambda: client.get_balances(), "balances")]:
        try:
            r = await fn()
            print(name, "OK", str(r)[:200])
        except DeltaError as e:
            print(name, "ERR", e.status, e.payload)
    await client.close()

asyncio.run(main())
