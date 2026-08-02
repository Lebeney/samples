"""
Pull REAL Step Index / Step Index 500 (and any Deriv synthetic) data straight from
Deriv's WebSocket API to CSV. Runs on any OS (Mac included) — no MT5, no Windows.

Setup (one time):
    pip install websocket-client

Find the exact symbol codes first:
    python3 deriv_pull.py --list          # prints all synthetic symbols + codes

Then pull ticks (finest data, best for the randomness test):
    python3 deriv_pull.py --symbol stpRNG --ticks 500000 --out step_ticks.csv

Or pull ready-made candles for a timeframe:
    python3 deriv_pull.py --symbol stpRNG --candles 1   --count 200000 --out step_1m.csv
    python3 deriv_pull.py --symbol stpRNG --candles 5   --count 200000 --out step_5m.csv
    python3 deriv_pull.py --symbol stpRNG --candles 15  --count 200000 --out step_15m.csv

Notes:
  * Public market data (ticks_history) needs NO login/token — just an app_id.
    1089 is Deriv's public test app_id; you can register your own in your Deriv
    account (Settings -> API token / Manage applications) and drop it in below.
  * Step Index code is usually "stpRNG". Step Index 500's exact code varies — run
    --list and copy whatever it shows (look for "Step" in the display name).
  * The API returns up to 5000 points per request; this script paginates backwards
    automatically until it reaches your target count.
"""
import json
import csv
import time
import argparse
from datetime import datetime, timezone

try:
    from websocket import create_connection
except ImportError:
    raise SystemExit("Missing dependency. Run:  pip install websocket-client")

APP_ID = 1089                                   # public test app_id; replace with your own if you like
URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
MAX_PER_REQ = 5000                              # Deriv cap per ticks_history call


def _connect():
    return create_connection(URL, timeout=30)


def _rpc(ws, payload, expect):
    """Send a request and return the first response whose msg_type == expect."""
    ws.send(json.dumps(payload))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("error"):
            raise RuntimeError(msg["error"].get("message", msg["error"]))
        if msg.get("msg_type") == expect:
            return msg


def list_symbols():
    ws = _connect()
    try:
        r = _rpc(ws, {"active_symbols": "brief", "product_type": "basic"}, "active_symbols")
    finally:
        ws.close()
    syn = [s for s in r["active_symbols"]
           if s.get("market") == "synthetic_index" or "synthetic" in s.get("market", "")]
    print(f"{'code':<14}{'display name'}")
    print("-" * 50)
    for s in sorted(syn, key=lambda x: x["display_name"]):
        print(f"{s['symbol']:<14}{s['display_name']}")
    print(f"\n{len(syn)} synthetic symbols. Copy the 'code' for the one you want (e.g. Step Index).")


def pull_ticks(symbol, target, out):
    ws = _connect()
    times, prices = [], []
    end = "latest"
    try:
        while len(times) < target:
            count = min(MAX_PER_REQ, target - len(times))
            r = _rpc(ws, {"ticks_history": symbol, "end": end,
                          "count": count, "style": "ticks"}, "history")
            h = r["history"]
            t, p = h["times"], h["prices"]
            if not t:
                break
            # prepend older data (API returns oldest..newest for this window)
            times = t + times
            prices = p + prices
            end = t[0] - 1                       # page further back in time
            print(f"  {symbol}: {len(times):,} ticks (back to "
                  f"{datetime.fromtimestamp(t[0], timezone.utc):%Y-%m-%d %H:%M})")
            time.sleep(0.6)                       # be polite to the API
    finally:
        ws.close()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "datetime_utc", "price"])
        for e, pr in zip(times, prices):
            w.writerow([e, datetime.fromtimestamp(e, timezone.utc).isoformat(), pr])
    print(f"[saved] {len(times):,} ticks -> {out}")


def pull_candles(symbol, granularity_min, target, out):
    ws = _connect()
    gran = granularity_min * 60
    rows = []
    end = "latest"
    try:
        while len(rows) < target:
            count = min(MAX_PER_REQ, target - len(rows))
            r = _rpc(ws, {"ticks_history": symbol, "end": end, "count": count,
                          "style": "candles", "granularity": gran}, "candles")
            cs = r["candles"]
            if not cs:
                break
            rows = cs + rows
            end = cs[0]["epoch"] - 1
            print(f"  {symbol} {granularity_min}m: {len(rows):,} candles (back to "
                  f"{datetime.fromtimestamp(cs[0]['epoch'], timezone.utc):%Y-%m-%d %H:%M})")
            time.sleep(0.6)
    finally:
        ws.close()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "datetime_utc", "open", "high", "low", "close"])
        for c in rows:
            w.writerow([c["epoch"], datetime.fromtimestamp(c["epoch"], timezone.utc).isoformat(),
                        c["open"], c["high"], c["low"], c["close"]])
    print(f"[saved] {len(rows):,} candles -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pull Deriv synthetic-index data to CSV.")
    ap.add_argument("--list", action="store_true", help="list synthetic symbols + codes")
    ap.add_argument("--symbol", default="stpRNG", help="symbol code (e.g. stpRNG for Step Index)")
    ap.add_argument("--ticks", type=int, default=0, help="pull this many ticks")
    ap.add_argument("--candles", type=int, default=0, help="candle timeframe in MINUTES (1/5/15)")
    ap.add_argument("--count", type=int, default=200000, help="number of candles (with --candles)")
    ap.add_argument("--out", default="deriv_data.csv", help="output CSV path")
    a = ap.parse_args()

    if a.list:
        list_symbols()
    elif a.ticks:
        pull_ticks(a.symbol, a.ticks, a.out)
    elif a.candles:
        pull_candles(a.symbol, a.candles, a.count, a.out)
    else:
        print("Nothing to do. Try --list, or --ticks N, or --candles 1 --count N. See -h.")
