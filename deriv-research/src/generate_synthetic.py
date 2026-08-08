"""Generate statistically faithful Deriv-style synthetic index data.

Deriv's Volatility indices are simulated markets driven by a certified
cryptographic RNG at a fixed annualized volatility (V75 = 75%, V100 = 100%),
ticking every 2 seconds, trading 24/7, with no drift edge (martingale in
price, which implies -sigma^2/2 drift in log space -- the well-known
long-term downward drift visible on real V75 charts is exactly this
volatility drag).

This script reproduces that process tick-by-tick and aggregates to
1-minute OHLC candles (30 ticks per candle), then derives 5m and 1h.

Data layout (written to --outdir):
  <SYMBOL>_train_1m.parquet    first 5 years  (analysis allowed)
  <SYMBOL>_holdout_1m.parquet  last 5 years   (BLIND -- do not open)
  <SYMBOL>_holdout_1m.sha256   integrity hash of the sealed holdout

Everything is seeded, so the dataset is exactly reproducible.
"""

import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd

TICK_SECONDS = 2
TICKS_PER_MIN = 60 // TICK_SECONDS
SECONDS_PER_YEAR = 365 * 24 * 3600

SYMBOLS = {
    "V75": {"sigma_annual": 0.75, "start_price": 100_000.0},
    "V100": {"sigma_annual": 1.00, "start_price": 100_000.0},
}


def simulate_1m_candles(sigma_annual, start_price, start_ts, n_minutes, seed,
                        chunk_minutes=100_000):
    """Simulate GBM ticks and aggregate to 1m OHLC without storing ticks."""
    sigma_tick = sigma_annual * np.sqrt(TICK_SECONDS / SECONDS_PER_YEAR)
    drift_tick = -0.5 * sigma_tick**2  # price-martingale
    rng = np.random.default_rng(seed)

    frames = []
    log_price = np.log(start_price)
    done = 0
    while done < n_minutes:
        m = min(chunk_minutes, n_minutes - done)
        z = rng.standard_normal(m * TICKS_PER_MIN)
        # cumulative sum across the WHOLE chunk so the path is continuous,
        # then reshape into per-minute rows
        log_paths = (log_price + np.cumsum(drift_tick + sigma_tick * z)
                     ).reshape(m, TICKS_PER_MIN)
        prices = np.exp(log_paths)
        opens = np.empty(m)
        opens[0] = np.exp(log_price)
        opens[1:] = prices[:-1, -1]
        df = pd.DataFrame({
            "epoch": start_ts + (done + np.arange(m)) * 60,
            "open": opens,
            "high": np.maximum(prices.max(axis=1), opens),
            "low": np.minimum(prices.min(axis=1), opens),
            "close": prices[:, -1],
        })
        frames.append(df)
        log_price = log_paths[-1, -1]
        done += m
    return pd.concat(frames, ignore_index=True)


def resample(df_1m, minutes):
    g = df_1m.assign(bucket=(df_1m["epoch"] // (minutes * 60)) * (minutes * 60))
    out = g.groupby("bucket").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last")).reset_index()
    return out.rename(columns={"bucket": "epoch"})


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--symbols", nargs="+", default=["V75", "V100"])
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    # 10 years ending 2026-08-08 00:00 UTC, split at the 5-year midpoint.
    end_ts = int(pd.Timestamp("2026-08-08", tz="UTC").timestamp())
    mid_ts = int(pd.Timestamp("2021-08-08", tz="UTC").timestamp())
    start_ts = int(pd.Timestamp("2016-08-08", tz="UTC").timestamp())
    train_minutes = (mid_ts - start_ts) // 60
    holdout_minutes = (end_ts - mid_ts) // 60

    manifest = {}
    for sym in args.symbols:
        spec = SYMBOLS[sym]
        # per-symbol seed offset so symbols are independent draws
        sym_off = int.from_bytes(hashlib.sha256(sym.encode()).digest()[:4], "big")
        train = simulate_1m_candles(spec["sigma_annual"], spec["start_price"],
                                    start_ts, train_minutes, seed=20160808 + sym_off)
        train_path = os.path.join(args.outdir, f"{sym}_train_1m.parquet")
        train.to_parquet(train_path, index=False)
        for mins, tag in [(5, "5m"), (60, "1h")]:
            resample(train, mins).to_parquet(
                os.path.join(args.outdir, f"{sym}_train_{tag}.parquet"), index=False)

        # Holdout continues from the train endpoint with an independent seed.
        holdout = simulate_1m_candles(spec["sigma_annual"],
                                      float(train["close"].iloc[-1]),
                                      mid_ts, holdout_minutes,
                                      seed=20210808 + sym_off)
        holdout_path = os.path.join(args.outdir, f"{sym}_holdout_1m.parquet")
        holdout.to_parquet(holdout_path, index=False)
        digest = sha256_file(holdout_path)
        manifest[sym] = {
            "train_rows": len(train), "holdout_rows": len(holdout),
            "train_span": [start_ts, mid_ts], "holdout_span": [mid_ts, end_ts],
            "holdout_sha256": digest,
        }
        print(f"{sym}: train={len(train)} rows, holdout={len(holdout)} rows "
              f"(sealed, sha256={digest[:16]}...)")

    with open(os.path.join(args.outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
