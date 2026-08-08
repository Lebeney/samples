"""Fetch real historical candles from the Deriv API into pipeline-ready parquet.

The research sandbox this project was built in could not reach Deriv's API
(egress policy), so the study ran on a calibrated simulation of the
documented generators. Run THIS script from an unrestricted machine to pull
the real history, then point pattern_study.py / ml_model.py / mine_patterns.py
at its output directory -- the file naming matches exactly.

Usage:
  pip install websocket-client pandas pyarrow
  python fetch_deriv_data.py --outdir ./data --symbol R_75 --granularity 60 \
      --start 2016-08-08 --end 2026-08-08

Common symbols: R_10 R_25 R_50 R_75 R_100 (Volatility indices),
1HZ75V etc. ((1s) variants), stpRNG (Step Index), BOOM1000, CRASH1000.
Granularity in seconds: 60, 300, 3600 (Deriv supports 60..86400).

The script splits the range at the 5-year midpoint into *_train_* and
*_holdout_* files so the blind protocol carries over to real data.
"""

import argparse
import json
import time

import pandas as pd
import websocket

APP_ID = 1089  # public demo app id; replace with your own for heavy use
WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
BATCH = 5000  # max candles per ticks_history request


def fetch_range(ws, symbol, granularity, start_epoch, end_epoch):
    frames = []
    cursor = start_epoch
    while cursor < end_epoch:
        req = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "start": cursor,
            "end": min(cursor + BATCH * granularity, end_epoch),
            "count": BATCH,
        }
        ws.send(json.dumps(req))
        resp = json.loads(ws.recv())
        if "error" in resp:
            raise RuntimeError(f"{symbol}: {resp['error']['message']}")
        candles = resp.get("candles", [])
        if not candles:
            cursor += BATCH * granularity
            continue
        frames.append(pd.DataFrame(candles))
        cursor = candles[-1]["epoch"] + granularity
        time.sleep(0.3)  # stay well under the API rate limit
    df = pd.concat(frames, ignore_index=True).drop_duplicates("epoch")
    df = df[["epoch", "open", "high", "low", "close"]].astype(
        {"epoch": "int64", "open": "float64", "high": "float64",
         "low": "float64", "close": "float64"})
    return df.sort_values("epoch").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--symbol", default="R_75")
    ap.add_argument("--granularity", type=int, default=60)
    ap.add_argument("--start", default="2016-08-08")
    ap.add_argument("--end", default="2026-08-08")
    args = ap.parse_args()

    start = int(pd.Timestamp(args.start, tz="UTC").timestamp())
    end = int(pd.Timestamp(args.end, tz="UTC").timestamp())
    mid = start + (end - start) // 2
    tag = {60: "1m", 300: "5m", 3600: "1h"}.get(args.granularity,
                                                f"{args.granularity}s")

    ws = websocket.create_connection(WS_URL, timeout=60)
    try:
        for name, s, e in [("train", start, mid), ("holdout", mid, end)]:
            print(f"fetching {args.symbol} {tag} {name} "
                  f"({pd.Timestamp(s, unit='s')} -> {pd.Timestamp(e, unit='s')})")
            df = fetch_range(ws, args.symbol, args.granularity, s, e)
            path = f"{args.outdir}/{args.symbol}_{name}_{tag}.parquet"
            df.to_parquet(path, index=False)
            print(f"  wrote {path}: {len(df)} candles")
    finally:
        ws.close()


if __name__ == "__main__":
    main()
