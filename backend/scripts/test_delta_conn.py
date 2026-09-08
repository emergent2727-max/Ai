import hashlib, hmac, time, os, json, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')
BASE = os.environ['DELTA_BASE_URL']
KEY = os.environ['DELTA_API_KEY']
SECRET = os.environ['DELTA_API_SECRET']


def sign(secret, msg):
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


def signed_get(path, query=''):
    ts = str(int(time.time()))
    data = 'GET' + ts + path + query
    sig = sign(SECRET, data)
    h = {'api-key': KEY, 'timestamp': ts, 'signature': sig, 'User-Agent': 'dacte-test', 'Content-Type': 'application/json'}
    return requests.get(BASE + path + query, headers=h, timeout=20)


print('== public products ==')
r = requests.get(BASE + '/v2/products?contract_types=spot&states=live', headers={'User-Agent': 'dacte-test'}, timeout=20)
print(r.status_code, str(r.text)[:300])

print('== server time-ish (tickers) ==')
r = requests.get(BASE + '/v2/tickers?contract_types=perpetual_futures', headers={'User-Agent': 'dacte-test'}, timeout=20)
print(r.status_code, str(r.text)[:200])

print('== private wallet balances ==')
r = signed_get('/v2/wallet/balances')
print(r.status_code, str(r.text)[:500])

print('== private positions/margined ==')
r = signed_get('/v2/positions/margined')
print(r.status_code, str(r.text)[:400])
