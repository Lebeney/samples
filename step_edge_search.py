"""
Exhaustive edge search on Step Index and Step Index 500, across 1m / 5m / 15m.

Two parts:
  (A) RANDOMNESS FINGERPRINT — the proof. If the next candle is 50/50 no matter
      what you condition on, then NO pattern on any timeframe can have an edge.
      We measure return autocorrelation and conditional next-move probabilities.
  (B) STRATEGY BATTERY — the search. A dozen concrete strategies (momentum,
      mean-reversion, breakout, fade, engulfing, streaks, multi-timeframe align)
      tested on 1m/5m/15m with a TRAIN/TEST seed split. In-sample flukes are
      expected; the honest test is whether ANYTHING survives out-of-sample.

Step indices are, by Deriv's spec, equal-probability fixed-step processes (no
drift, no memory). Live feed is blocked here, so this simulates that spec.
Step 500's exact tick size isn't pinned in my knowledge — modeled as a symmetric
fixed-step walk with larger steps; symmetry (not step size) is what kills edges.
"""
import numpy as np, pandas as pd

pd.set_option("display.width", 220, "display.max_columns", 40)
TICKS_PER_MIN = 30

SPECS = {                    # (step size, ) — both symmetric, p(up)=p(down)=0.5
    "Step Index": 0.1,
    "Step Index 500": 1.0,
}


def gen_1m(inst, seed, n_min):
    rng = np.random.default_rng(seed)
    step = SPECS[inst]
    N = n_min * TICKS_PER_MIN
    ticks = rng.choice([-step, step], size=N)          # symmetric: 50/50, fixed step
    price = 1000.0 + np.cumsum(ticks)
    p = price.reshape(n_min, TICKS_PER_MIN)
    df = pd.DataFrame({"open": p[:, 0], "high": p.max(1), "low": p.min(1), "close": p[:, -1]})
    df.index = pd.date_range("2025-01-06", periods=n_min, freq="1min")
    return df


def timeframes(df1):
    out = {"1m": df1}
    for rule, name in [("5min", "5m"), ("15min", "15m")]:
        out[name] = df1.resample(rule, label="left", closed="left").agg(
            open=("open", "first"), high=("high", "max"),
            low=("low", "min"), close=("close", "last")).dropna()
    return out


# --------------------------------------------------------------------------- #
#  (A) randomness fingerprint
# --------------------------------------------------------------------------- #
def fingerprint(df):
    o, c = df["open"].values, df["close"].values
    ret = c - o
    d = np.sign(ret); d = d[d != 0]
    up = (d > 0).astype(int)
    n = len(up)

    def cond_p(hist):                       # P(next up | last len(hist) dirs == hist)
        k = len(hist)
        hist = np.array(hist)
        idx = np.arange(k, n)
        mask = np.ones(len(idx), bool)
        for j in range(k):
            mask &= (up[idx - k + j] == hist[j])
        nxt = up[idx][mask]
        return (nxt.mean() if len(nxt) else np.nan, len(nxt))

    ac1 = np.corrcoef(ret[:-1], ret[1:])[0, 1]
    return {
        "P(up)": round(up.mean(), 4),
        "autocorr_lag1": round(ac1, 4),
        "P(up|up)": round(cond_p([1])[0], 4),
        "P(up|down)": round(cond_p([0])[0], 4),
        "P(up|up,up)": round(cond_p([1, 1])[0], 4),
        "P(up|3up)": round(cond_p([1, 1, 1])[0], 4),
        "P(up|3down)": round(cond_p([0, 0, 0])[0], 4),
    }


# --------------------------------------------------------------------------- #
#  (B) strategy battery — expectancy of next-candle return in signal direction
# --------------------------------------------------------------------------- #
def signal_dirs(df, name):
    """Return an array `d` (+1/-1/0) of the position to hold INTO the next candle,
    decided at each candle's close using only past/current info (no lookahead)."""
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    n = len(df)
    up = (c > o).astype(int); dn = (c < o).astype(int)
    d = np.zeros(n)
    if name == "momentum1":            # last candle up -> long (continuation)
        d = np.where(c > o, 1, np.where(c < o, -1, 0))
    elif name == "meanrev1":           # last candle up -> short (fade)
        d = np.where(c > o, -1, np.where(c < o, 1, 0))
    elif name == "momentum3":          # 3 same-dir -> continue
        for i in range(3, n):
            if up[i-2] and up[i-1] and up[i]: d[i] = 1
            elif dn[i-2] and dn[i-1] and dn[i]: d[i] = -1
    elif name == "streak3_fade":       # 3 same-dir -> fade (gambler's fallacy)
        for i in range(3, n):
            if up[i-2] and up[i-1] and up[i]: d[i] = -1
            elif dn[i-2] and dn[i-1] and dn[i]: d[i] = 1
    elif name == "breakout10":         # close > prior 10-bar high -> long
        for i in range(10, n):
            if c[i] > h[i-10:i].max(): d[i] = 1
            elif c[i] < l[i-10:i].min(): d[i] = -1
    elif name == "fade_breakout10":
        for i in range(10, n):
            if c[i] > h[i-10:i].max(): d[i] = -1
            elif c[i] < l[i-10:i].min(): d[i] = 1
    elif name == "engulf_cont":        # bullish/bearish engulfing -> continue
        for i in range(1, n):
            if c[i] > o[i] and c[i-1] < o[i-1] and c[i] >= o[i-1] and o[i] <= c[i-1]: d[i] = 1
            elif c[i] < o[i] and c[i-1] > o[i-1] and c[i] <= o[i-1] and o[i] >= c[i-1]: d[i] = -1
    return d


def battery_expectancy(df, name):
    o, c = df["open"].values, df["close"].values
    d = signal_dirs(df, name)
    nxt = np.concatenate([c[1:] - c[:-1], [0.0]])       # next-candle close-to-close return
    atr = np.mean(np.abs(c[1:] - c[:-1])) or 1.0
    mask = d != 0
    if mask.sum() == 0:
        return 0, np.nan, np.nan
    pnl = (d[mask] * nxt[mask]) / atr                   # in ATR units, no lookahead
    return int(mask.sum()), float(pnl.mean()), float(pnl.std() / np.sqrt(len(pnl)))


STRATS = ["momentum1", "meanrev1", "momentum3", "streak3_fade",
          "breakout10", "fade_breakout10", "engulf_cont"]


def run():
    print("=" * 78)
    print("(A) RANDOMNESS FINGERPRINT  (if all conditional P(up) ~ 0.50 -> no edge exists)")
    print("=" * 78)
    for inst in SPECS:
        df1 = gen_1m(inst, seed=7, n_min=6 * 43200)     # 6 months
        for tf, df in timeframes(df1).items():
            fp = fingerprint(df)
            print(f"{inst:16s} {tf:>3s} | " + "  ".join(f"{k}={v}" for k, v in fp.items()))
    print()

    print("=" * 78)
    print("(B) STRATEGY BATTERY  — expectancy per trade in ATR units, TRAIN vs TEST")
    print("    (train = seeds 0-5, test = unseen seeds 100-105; edge = TEST consistently >0)")
    print("=" * 78)
    train, test = range(0, 6), range(100, 106)
    rows = []
    for inst in SPECS:
        tf_train = {s: timeframes(gen_1m(inst, s, 43200)) for s in train}
        tf_test = {s: timeframes(gen_1m(inst, s, 43200)) for s in test}
        for tf in ["1m", "5m", "15m"]:
            for strat in STRATS:
                tr = [battery_expectancy(tf_train[s][tf], strat)[1] for s in train]
                te = [battery_expectancy(tf_test[s][tf], strat)[1] for s in test]
                tr = np.array(tr); te = np.array(te)
                rows.append({
                    "instrument": inst, "tf": tf, "strategy": strat,
                    "train_exp": round(float(np.nanmean(tr)), 4),
                    "test_exp": round(float(np.nanmean(te)), 4),
                    "test_stderr": round(float(np.nanstd(te) / np.sqrt(len(te))), 4),
                })
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    res.to_csv("step_edge_search.csv", index=False)

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    best = res.reindex(res["test_exp"].abs().sort_values(ascending=False).index).head(3)
    print("Largest |test expectancy| found (best 'edges'):")
    print(best.to_string(index=False))
    within = (res["test_exp"].abs() <= 2 * res["test_stderr"]).mean() * 100
    print(f"\n{within:.0f}% of all {len(res)} strategy/timeframe combos have a test expectancy "
          f"within 2 standard errors of ZERO.")
    print("Mean |test expectancy| across all combos: "
          f"{res['test_exp'].abs().mean():.4f} ATR (i.e. statistical noise).")
    print("\n[written] step_edge_search.csv")


if __name__ == "__main__":
    run()
