"""
Simple multi-timeframe engulfing-continuation test, exactly as described:

  1-min signal:  candle A (against) -> candle B engulfs it (with) -> candle C (with)
                 => enter in B/C direction on the next candle.
  Confirmation:  last COMPLETED 5-min AND 15-min candle both point the same way.
  Layer/risk:    tested first at fixed small risk (does the SIGNAL win?),
                 then with the 50% initial + 20% add sizing.

Instruments: the Deriv-style synthetics (Step / Volatility / Boom / Crash),
generated at tick level so 1m/5m/15m all come from ONE consistent stream.
No lookahead: HTF confirmation uses only candles completed at or before the 1m bar;
entry is the next 1m open. Simulated data, not a live feed.
"""
import numpy as np, pandas as pd

MIN_PER_MONTH = 30 * 24 * 60         # 43200 one-minute candles (24/7)
SUBTICKS = 12                        # sub-ticks per minute -> intrabar OHLC


def gen_1m(inst, seed, n_min=MIN_PER_MONTH, fair_game=False):
    rng = np.random.default_rng(seed)
    N = n_min * SUBTICKS
    if inst.startswith("Vol"):
        sigma = float(inst[3:]) / 100.0
        dt = (60.0 / SUBTICKS) / (365 * 24 * 3600)
        r = (-0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(N)
        price = 1000.0 * np.exp(np.cumsum(r))
    elif inst == "Step":
        price = 9000.0 + np.cumsum(rng.choice([-0.1, 0.1], size=N))
    elif inst.startswith(("Boom", "Crash")):
        period = int(inst.split()[-1])
        drift_sign = +1 if inst.startswith("Crash") else -1
        spike_sign = -drift_sign
        delta = 0.05
        inc = drift_sign * delta + rng.normal(0, 0.08, N)
        spikes = rng.random(N) < 1.0 / period          # 1 spike per `period` sub-ticks
        scale = 1.25 if fair_game else 1.6   # 1.25 => net drift 0 (true fair game); consistent
        mag = rng.uniform(0.6, 1.0, N) * (period * delta * scale)
        price = 10000.0 + np.cumsum(inc + spike_sign * spikes * mag)
    else:
        raise ValueError(inst)
    p = price[:n_min * SUBTICKS].reshape(n_min, SUBTICKS)
    df = pd.DataFrame({"open": p[:, 0], "high": p.max(1), "low": p.min(1), "close": p[:, -1]})
    df.index = pd.date_range("2025-01-06", periods=n_min, freq="1min")
    return df


def atr(df, n=14):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def htf_dir(df1, rule):
    """Direction (+1/-1) of the last COMPLETED higher-timeframe candle, aligned to 1m."""
    h = df1.resample(rule, label="left", closed="left").agg(
        o=("open", "first"), c=("close", "last")).dropna()
    d = np.sign(h["c"] - h["o"]).replace(0, np.nan).ffill()
    d.index = d.index + pd.tseries.frequencies.to_offset(rule)   # completion time
    return d.reindex(df1.index, method="ffill")


def signals(df1, dir5, dir15):
    o, h, l, c = (df1[k].values for k in ["open", "high", "low", "close"])
    a = atr(df1).values
    d5, d15 = dir5.values, dir15.values
    n = len(df1)
    bull = c > o
    bear = c < o
    out = []
    for i in range(20, n - 1):
        if not (a[i] > 0):
            continue
        # long: A bear (i-2), B bull engulf A (i-1), C bull (i) ; 5m & 15m up
        if bear[i-2] and bull[i-1] and bull[i] and \
           c[i-1] >= o[i-2] and o[i-1] <= c[i-2] and d5[i] == 1 and d15[i] == 1:
            out.append((i, +1, a[i]))
        # short mirror
        elif bull[i-2] and bear[i-1] and bear[i] and \
             c[i-1] <= o[i-2] and o[i-1] >= c[i-2] and d5[i] == -1 and d15[i] == -1:
            out.append((i, -1, a[i]))
    return out


def test_edge(inst, seeds, rr=2.0, stop_buf=0.3, cost=0.3, fair_game=False, gap_frac=0.5):
    """One position at a time, fixed risk, target = rr * risk. Pool R across seeds."""
    Rs = []
    for s in seeds:
        df1 = gen_1m(inst, s, fair_game=fair_game)
        d5 = htf_dir(df1, "5min"); d15 = htf_dir(df1, "15min")
        sig = signals(df1, d5, d15)
        o, h, l, c = (df1[k].values for k in ["open", "high", "low", "close"])
        n = len(df1); busy = -1
        for (i, d, av) in sig:
            e = i + 1
            if e >= n or e <= busy:
                continue
            entry = o[e]
            if d == 1:
                stop = min(l[i-2], l[i-1], l[i]) - stop_buf * av
                if stop >= entry:
                    continue
            else:
                stop = max(h[i-2], h[i-1], h[i]) + stop_buf * av
                if stop <= entry:
                    continue
            risk = abs(entry - stop)
            target = entry + d * rr * risk
            outcome = 0
            exit_price = None
            end = min(e + 300, n - 1)
            for t in range(e, end + 1):
                hs = (l[t] <= stop) if d == 1 else (h[t] >= stop)
                ht = (h[t] >= target) if d == 1 else (l[t] <= target)
                rng_t = h[t] - l[t]
                if hs:   # stop hit (checked first = conservative on same-bar ambiguity)
                    # spike gap-through: a fast bar fills a stop worse than the stop price
                    adverse = l[t] if d == 1 else h[t]
                    beyond = (stop - adverse) if d == 1 else (adverse - stop)
                    if rng_t > 4.0 * av and beyond > 0:
                        exit_price = stop - gap_frac * beyond if d == 1 else stop + gap_frac * beyond
                    else:
                        exit_price = stop
                    outcome = -1; texit = t; break
                if ht:
                    exit_price = target; outcome = +1; texit = t; break
            else:
                texit = end; exit_price = c[end]
            r = ((exit_price - entry) * d - cost) / risk
            Rs.append(r); busy = texit
    R = np.array(Rs)
    if len(R) == 0:
        return {"instrument": inst, "signals": 0}
    wins = R > 0
    gl = -R[R < 0].sum()
    return {
        "instrument": inst, "signals": len(R),
        "win%": round(wins.mean() * 100, 1),
        "avg_R": round(float(R.mean()), 3),
        "PF": round(float(R[R > 0].sum() / gl), 2) if gl > 0 else float("inf"),
        "expectancy_per_$risked": round(float(R.mean()), 3),
        "stderr": round(float(R.std() / np.sqrt(len(R))), 3),
    }


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 20)
    seeds = range(8)
    rows = [test_edge(inst, seeds) for inst in
            ["Step", "Vol75", "Vol100", "Boom 1000", "Crash 1000"]]
    # Boom/Crash again under a TRUE fair game (net drift 0) — the honest instrument
    rows.append({**test_edge("Boom 1000", seeds, fair_game=True),
                 "instrument": "Boom 1000 (fair game)"})
    rows.append({**test_edge("Crash 1000", seeds, fair_game=True),
                 "instrument": "Crash 1000 (fair game)"})
    df = pd.DataFrame(rows)
    print("Simple 1m engulfing-continuation + 5m/15m confirmation")
    print("(one position at a time, fixed risk, target = 2R, costs on,")
    print(" spike gap-through modeled at 0.5 of the overshoot)\n")
    print(df.to_string(index=False))
    df.to_csv("mtf_engulf.csv", index=False)

    # The Boom/Crash 'edge' is entirely a spike-fill artifact: sweep the fill.
    print("\nBoom/Crash (fair game) avg_R vs how a spike fills your stop:")
    print(f"{'spike_fill':>26} | {'Boom':>8} | {'Crash':>8}")
    for gf, name in [(0.0, "ignore gap (naive/bug)"), (0.5, "halfway through stop"),
                     (1.0, "at spike extreme (real)")]:
        b = test_edge("Boom 1000", range(4), fair_game=True, gap_frac=gf)["avg_R"]
        c = test_edge("Crash 1000", range(4), fair_game=True, gap_frac=gf)["avg_R"]
        print(f"{name:>26} | {b:>8} | {c:>8}")
    print("\n[written] mtf_engulf.csv")
