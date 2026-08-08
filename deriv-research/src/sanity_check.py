"""Validate the generated data against the documented generator properties.

Checks:
  1. Path continuity: every candle opens exactly at the prior close.
  2. Per-minute log-return std matches sigma_annual * sqrt(60 / seconds_per_year).
  3. Lag-1..5 autocorrelation of 1m returns is ~0 (no fake structure).
  4. High >= max(open, close) >= min(open, close) >= low everywhere.
  5. Breakout frequency is in the random-walk ballpark (a canary for the
     chunking bug this suite originally caught).
"""

import argparse
import numpy as np
import pandas as pd

SECONDS_PER_YEAR = 365 * 24 * 3600
SIGMA = {"V75": 0.75, "V100": 1.00}


def check(datadir, sym):
    df = pd.read_parquet(f"{datadir}/{sym}_train_1m.parquet")
    ok = True

    cont = np.allclose(df["open"].to_numpy()[1:], df["close"].to_numpy()[:-1])
    print(f"[{sym}] continuity open[t]==close[t-1]: {cont}")
    ok &= cont

    ret = np.log(df["close"] / df["close"].shift(1)).dropna()
    theo = SIGMA[sym] * np.sqrt(60 / SECONDS_PER_YEAR)
    emp = ret.std()
    print(f"[{sym}] 1m return std: empirical={emp:.6e} theoretical={theo:.6e} "
          f"ratio={emp/theo:.4f}")
    ok &= abs(emp / theo - 1) < 0.01

    r = ret.to_numpy()
    for lag in [1, 2, 5]:
        ac = np.corrcoef(r[:-lag], r[lag:])[0, 1]
        print(f"[{sym}] 1m return autocorr lag {lag}: {ac:+.5f}")
        ok &= abs(ac) < 0.005

    sane = ((df["high"] >= df[["open", "close"]].max(axis=1)) &
            (df["low"] <= df[["open", "close"]].min(axis=1))).all()
    print(f"[{sym}] OHLC ordering sane: {sane}")
    ok &= bool(sane)

    hh20 = df["high"].shift(1).rolling(20).max()
    freq = (df["close"] > hh20).mean()
    print(f"[{sym}] 20-bar breakout frequency: {freq:.4f} (random-walk ballpark ~0.02-0.05)")
    ok &= 0.01 < freq < 0.10

    print(f"[{sym}] ALL CHECKS {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    args = ap.parse_args()
    results = [check(args.datadir, s) for s in ["V75", "V100"]]
    raise SystemExit(0 if all(results) else 1)
