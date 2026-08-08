"""Candlestick anatomy features and pattern detectors.

Anatomy of a candle (all sizes normalized by a rolling ATR so that patterns
mean the same thing at any price level):

      high  ---   <- extreme of buying reach within the period
       |
      body top    <- max(open, close)
      #####
      #####       <- body: |close - open|, the net directional move
      #####
      body bottom <- min(open, close)
       |
      low   ---   <- extreme of selling reach within the period

  upper wick = high - max(open, close)   (rejected upside)
  lower wick = min(open, close) - low    (rejected downside)
  range      = high - low                (total contested ground)

In a real order-driven market a candle is the residue of order flow:
initiative buyers/sellers move price, resting liquidity absorbs it, and
wicks record excursions that got rejected. In a Deriv synthetic index the
"order flow" is a certified RNG driving a fixed-volatility process, so the
same anatomy exists mechanically but has no participants behind it. Part of
the purpose of this study is to measure which classic pattern claims
survive when the order-flow explanation is removed.
"""

import numpy as np
import pandas as pd

EPS = 1e-12


def add_anatomy(df, atr_window=100):
    """Add normalized anatomy columns to an OHLC frame (epoch,open,high,low,close)."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    df = df.copy()
    df["range"] = h - l
    df["body"] = (c - o).abs()
    df["dir"] = np.sign(c - o).astype(int)          # +1 bull, -1 bear, 0 flat
    df["upper_wick"] = h - np.maximum(o, c)
    df["lower_wick"] = np.minimum(o, c) - l
    df["ret"] = np.log(c / c.shift(1))
    # True range / ATR for scale normalization
    prev_c = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev_c).abs(), (l - prev_c).abs()))
    df["atr"] = tr.rolling(atr_window, min_periods=atr_window).mean()
    r = df["range"] + EPS
    df["body_frac"] = df["body"] / r                 # 0 = doji, 1 = marubozu
    df["uw_frac"] = df["upper_wick"] / r
    df["lw_frac"] = df["lower_wick"] / r
    df["range_atr"] = df["range"] / (df["atr"] + EPS)
    df["close_pos"] = (c - l) / r                    # where close sits in range
    return df


def detect_patterns(df):
    """Return a dict of boolean Series, one per pattern, aligned to df.

    Thresholds follow common technical-analysis definitions (Nison/Bulkowski
    style), applied mechanically and identically across the whole sample.
    """
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bf, uw, lw = df["body_frac"], df["uw_frac"], df["lw_frac"]
    rng_atr, d = df["range_atr"], df["dir"]
    body = df["body"]

    p = {}
    p["doji"] = bf < 0.1
    p["spinning_top"] = (bf < 0.35) & (uw > 0.25) & (lw > 0.25)
    p["marubozu_bull"] = (bf > 0.9) & (d > 0)
    p["marubozu_bear"] = (bf > 0.9) & (d < 0)
    p["hammer"] = (lw > 0.6) & (uw < 0.15) & (bf > 0.05)
    p["shooting_star"] = (uw > 0.6) & (lw < 0.15) & (bf > 0.05)
    p["big_range"] = rng_atr > 2.0                    # volatility burst candle
    p["tiny_range"] = rng_atr < 0.5

    o1, c1, h1, l1 = o.shift(1), c.shift(1), h.shift(1), l.shift(1)
    body1, d1 = body.shift(1), d.shift(1)
    p["engulf_bull"] = (d > 0) & (d1 < 0) & (o <= c1) & (c >= o1) & (body > body1)
    p["engulf_bear"] = (d < 0) & (d1 > 0) & (o >= c1) & (c <= o1) & (body > body1)
    p["harami_bull"] = (d > 0) & (d1 < 0) & (np.maximum(o, c) <= np.maximum(o1, c1)) \
        & (np.minimum(o, c) >= np.minimum(o1, c1))
    p["harami_bear"] = (d < 0) & (d1 > 0) & (np.maximum(o, c) <= np.maximum(o1, c1)) \
        & (np.minimum(o, c) >= np.minimum(o1, c1))
    p["inside_bar"] = (h <= h1) & (l >= l1)
    p["outside_bar"] = (h > h1) & (l < l1)

    d2 = d.shift(2)
    p["three_white_soldiers"] = (d > 0) & (d1 > 0) & (d2 > 0) & (c > c1) & (c1 > c.shift(2))
    p["three_black_crows"] = (d < 0) & (d1 < 0) & (d2 < 0) & (c < c1) & (c1 < c.shift(2))

    # Simple structure: N-bar momentum runs (continuation vs mean-reversion test)
    up3 = (df["ret"] > 0).rolling(3).sum() == 3
    dn3 = (df["ret"] < 0).rolling(3).sum() == 3
    p["run_up_3"] = up3
    p["run_dn_3"] = dn3
    up5 = (df["ret"] > 0).rolling(5).sum() == 5
    dn5 = (df["ret"] < 0).rolling(5).sum() == 5
    p["run_up_5"] = up5
    p["run_dn_5"] = dn5

    # Swing breakout: close above rolling 20-bar high (prior), below 20-bar low
    hh20 = h.shift(1).rolling(20).max()
    ll20 = l.shift(1).rolling(20).min()
    p["breakout_up_20"] = c > hh20
    p["breakout_dn_20"] = c < ll20

    return {k: v.fillna(False) for k, v in p.items()}


# Directional expectation each pattern carries in classic TA lore:
#   +1 = bullish signal, -1 = bearish, 0 = "volatility / no direction" claim
PATTERN_BIAS = {
    "doji": 0, "spinning_top": 0, "marubozu_bull": +1, "marubozu_bear": -1,
    "hammer": +1, "shooting_star": -1, "big_range": 0, "tiny_range": 0,
    "engulf_bull": +1, "engulf_bear": -1, "harami_bull": +1, "harami_bear": -1,
    "inside_bar": 0, "outside_bar": 0,
    "three_white_soldiers": +1, "three_black_crows": -1,
    "run_up_3": +1, "run_dn_3": -1, "run_up_5": +1, "run_dn_5": -1,
    "breakout_up_20": +1, "breakout_dn_20": -1,
}
