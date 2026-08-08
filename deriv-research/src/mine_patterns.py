"""Exhaustive discovery of 3-candle patterns, with honest decay testing.

Each candle is classified into one of 5 anatomy types:
  SB strong bull (bull, body > 60% of range)     WB weak bull
  DJ doji        (body < 10% of range)
  WS weak bear                                    SS strong bear

Every 3-candle sequence (125 contexts) is a candidate "discovered pattern".
For each context we measure P(next bar up) on a DISCOVERY window
(2016-2018), keep the top and bottom 15 by apparent edge, then re-measure
the same contexts on a VALIDATION window (2019 - mid-2021, still inside the
training half; the final 5 years remain sealed). If the discovered edges are
real they persist; if they are mining noise they collapse to 50%.
"""

import argparse
import os

import numpy as np
import pandas as pd

from candlestick_features import add_anatomy


def classify(df):
    bf, d = df["body_frac"], df["dir"]
    t = np.full(len(df), 2, dtype=int)             # 2 = doji/neutral
    t[(d > 0) & (bf >= 0.6)] = 0                   # strong bull
    t[(d > 0) & (bf < 0.6) & (bf >= 0.1)] = 1      # weak bull
    t[(d < 0) & (bf < 0.6) & (bf >= 0.1)] = 3      # weak bear
    t[(d < 0) & (bf >= 0.6)] = 4                   # strong bear
    return t


NAMES = ["SB", "WB", "DJ", "WS", "SS"]


def context_stats(df):
    t = classify(df)
    ctx = t[:-3] * 25 + t[1:-2] * 5 + t[2:-1]
    up = (df["close"].to_numpy()[3:] > df["close"].to_numpy()[2:-1]).astype(int)
    stats = pd.DataFrame({"ctx": ctx, "up": up}).groupby("ctx")["up"].agg(["count", "mean"])
    return stats.rename(columns={"count": "n", "mean": "p_up"})


def label(ctx):
    return "-".join(NAMES[d] for d in [(ctx // 25) % 5, (ctx // 5) % 5, ctx % 5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--symbol", default="V75")
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--min-n", type=int, default=500)
    args = ap.parse_args()

    df = pd.read_parquet(
        os.path.join(args.datadir, f"{args.symbol}_train_{args.timeframe}.parquet"))
    df = add_anatomy(df)
    ts = pd.to_datetime(df["epoch"], unit="s")
    disc = df[ts < "2019-01-01"].reset_index(drop=True)
    val = df[ts >= "2019-01-01"].reset_index(drop=True)

    s_disc = context_stats(disc)
    s_val = context_stats(val)
    merged = s_disc.join(s_val, lsuffix="_disc", rsuffix="_val", how="inner")
    merged = merged[merged["n_disc"] >= args.min_n]
    merged["edge_disc"] = (merged["p_up_disc"] - 0.5).abs()
    merged["edge_val"] = (merged["p_up_val"] - 0.5).abs()
    # does the validation edge keep the discovery edge's direction?
    merged["same_side"] = (np.sign(merged["p_up_disc"] - 0.5)
                           == np.sign(merged["p_up_val"] - 0.5))
    merged["pattern"] = [label(c) for c in merged.index]

    top = merged.sort_values("edge_disc", ascending=False).head(30)
    cols = ["pattern", "n_disc", "p_up_disc", "n_val", "p_up_val", "same_side"]
    print("== Top 30 'discovered' 3-candle patterns by in-sample edge ==")
    print(top[cols].round(5).to_string(index=False))
    print(f"\ndiscovery mean |edge| of top 30: {top['edge_disc'].mean():.5f}")
    print(f"validation mean |edge| of top 30: {top['edge_val'].mean():.5f}")
    print(f"validation edge on same side as discovery: "
          f"{top['same_side'].mean() * 100:.0f}% (coin flip = 50%)")

    os.makedirs(args.outdir, exist_ok=True)
    out = os.path.join(args.outdir,
                       f"mined_patterns_{args.symbol}_{args.timeframe}.csv")
    merged.sort_values("edge_disc", ascending=False).to_csv(out)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
