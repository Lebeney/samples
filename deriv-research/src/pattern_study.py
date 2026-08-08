"""Pattern study: for every detected pattern, measure what actually happens next.

For each pattern occurrence we record, over horizons of 1, 5, and 15 bars:
  - forward log return (signed by the pattern's classic bias where it has one)
  - probability the next bar closes in the pattern's claimed direction
  - forward realized range vs. the unconditional average ("quick movement" test)

Statistics:
  - two-sided binomial test of P(direction) vs 0.5
  - Welch t-test of forward range vs unconditional forward range
  - Benjamini-Hochberg FDR correction across all pattern x horizon tests
"""

import argparse
import os

import numpy as np
import pandas as pd
from scipy import stats

from candlestick_features import add_anatomy, detect_patterns, PATTERN_BIAS

HORIZONS = [1, 5, 15]


def forward_metrics(df):
    c = df["close"]
    out = {}
    for hz in HORIZONS:
        out[f"fwd_ret_{hz}"] = np.log(c.shift(-hz) / c)
        out[f"fwd_up_{hz}"] = (c.shift(-hz) > c).astype(float)
        # realized range over the next hz bars, ATR-normalized
        fwd_hi = df["high"].shift(-1).rolling(hz).max().shift(-(hz - 1))
        fwd_lo = df["low"].shift(-1).rolling(hz).min().shift(-(hz - 1))
        out[f"fwd_range_{hz}"] = (fwd_hi - fwd_lo) / (df["atr"] + 1e-12)
    return pd.DataFrame(out, index=df.index)


def study(df, timeframe, symbol):
    df = add_anatomy(df)
    pats = detect_patterns(df)
    fwd = forward_metrics(df)
    valid = df["atr"].notna() & fwd.notna().all(axis=1)

    rows = []
    for name, mask in pats.items():
        m = (mask & valid).to_numpy()
        n = int(m.sum())
        if n < 100:
            continue
        bias = PATTERN_BIAS[name]
        for hz in HORIZONS:
            up = fwd[f"fwd_up_{hz}"].to_numpy()[m]
            ret = fwd[f"fwd_ret_{hz}"].to_numpy()[m]
            rng = fwd[f"fwd_range_{hz}"].to_numpy()[m]
            rng_all = fwd[f"fwd_range_{hz}"].to_numpy()[valid.to_numpy()]

            p_up = float(np.mean(up))
            # direction test vs fair coin
            k = int(up.sum())
            p_dir = stats.binomtest(k, n, 0.5).pvalue
            # quick-movement test: is forward range different after pattern?
            t_rng, p_rng = stats.ttest_ind(rng, rng_all, equal_var=False)

            if bias == +1:
                hit = p_up
            elif bias == -1:
                hit = 1.0 - p_up
            else:
                hit = np.nan
            rows.append({
                "symbol": symbol, "timeframe": timeframe, "pattern": name,
                "bias": bias, "horizon": hz, "n": n,
                "p_up": round(p_up, 5),
                "hit_rate": round(hit, 5) if hit == hit else None,
                "mean_fwd_ret_bps": round(float(np.mean(ret)) * 1e4, 4),
                "fwd_range_ratio": round(float(np.mean(rng) / np.mean(rng_all)), 4),
                "pval_direction": p_dir, "pval_range": p_rng,
            })
    res = pd.DataFrame(rows)
    # BH-FDR across all tests in this table
    for col, out in [("pval_direction", "fdr_direction"), ("pval_range", "fdr_range")]:
        pv = res[col].to_numpy()
        order = np.argsort(pv)
        ranked = np.empty_like(pv)
        n_tests = len(pv)
        prev = 1.0
        adj = np.empty_like(pv)
        for i in range(n_tests - 1, -1, -1):
            idx = order[i]
            prev = min(prev, pv[idx] * n_tests / (i + 1))
            adj[idx] = prev
        res[out] = adj
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--symbols", nargs="+", default=["V75", "V100"])
    ap.add_argument("--split", default="train", choices=["train", "holdout"])
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    all_res = []
    for sym in args.symbols:
        for tf in ["1m", "5m", "1h"]:
            path = os.path.join(args.datadir, f"{sym}_{args.split}_{tf}.parquet")
            if not os.path.exists(path):
                continue
            df = pd.read_parquet(path)
            res = study(df, tf, sym)
            all_res.append(res)
            print(f"{sym} {tf}: {len(res)} pattern-horizon tests, "
                  f"{(res['fdr_direction'] < 0.05).sum()} direction hits after FDR, "
                  f"{(res['fdr_range'] < 0.05).sum()} range hits after FDR")
    out = pd.concat(all_res, ignore_index=True)
    out_path = os.path.join(args.outdir, f"pattern_study_{args.split}.csv")
    out.to_csv(out_path, index=False)
    print(f"wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
