"""
Strategy tuning + honest validation.

Goal: take the lesson from the gold run (win-often / lose-money, because targets
sit ~0.3R away while stops sit ~1R+ away) and see whether a fixed reward:risk
target ("rr" mode) can turn the pullback-continuation idea into something good --
on GOLD (a real market) and on the DERIV-STYLE SYNTHETICS (simulated RNG feeds).

The whole point is OUT-OF-SAMPLE validation:
  * Gold      -> time split: tune on the first ~8 months, test on the last ~4.
  * Synthetic -> seed split: tune on 12 independent months, test on 12 fresh ones.
  * Boom/Crash also re-run under a FAIR-GAME calibration (spike*freq == drift, so
    net drift = 0) to check whether any 'edge' is real structure or just my
    simulation's leftover drift.

Nothing here is live Deriv data or a promise of live profit.
"""
import numpy as np, pandas as pd
from dataclasses import replace
from backtest import (Params, load_dukascopy_5m, add_indicators,
                      detect_signals, simulate, summarize)

pd.set_option("display.width", 220, "display.max_columns", 30)

CANDLES_PER_MONTH = 30 * 24 * 12
TPC = 48


# --------------------------------------------------------------------------- #
#  Synthetic generators (documented processes; fair_game toggles Boom/Crash)
# --------------------------------------------------------------------------- #
def gen(instrument, seed, fair_game=False):
    rng = np.random.default_rng(seed)
    N = CANDLES_PER_MONTH * TPC
    if instrument.startswith("Vol"):
        sigma = float(instrument[3:]) / 100.0
        dt = 6.0 / (365 * 24 * 3600)
        r = (-0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(N)
        return 1000.0 * np.exp(np.cumsum(r))
    if instrument == "Step":
        return 9000.0 + np.cumsum(rng.choice([-0.1, 0.1], size=N))
    if instrument.startswith(("Boom", "Crash")):
        period = int(instrument.split()[-1])
        drift_sign = +1 if instrument.startswith("Crash") else -1
        spike_sign = -drift_sign
        delta = 0.05
        inc = drift_sign * delta + rng.normal(0, 0.08, N)
        spikes = rng.random(N) < 1.0 / period
        # fair game: E[mag]=period*delta -> net drift 0 ; else 1.28x (net drift)
        scale = 1.25 if fair_game else 1.6
        mag = rng.uniform(0.6, 1.0, N) * (period * delta * scale)
        inc = inc + spike_sign * spikes * mag
        return 10000.0 + np.cumsum(inc)
    raise ValueError(instrument)


def ticks_to_candles(price, tpc=TPC, start="2025-01-06"):
    n = len(price) // tpc * tpc
    p = price[:n].reshape(-1, tpc)
    df = pd.DataFrame({"open": p[:, 0], "high": p.max(1), "low": p.min(1),
                       "close": p[:, -1], "volume": float(tpc)})
    df.index = pd.date_range(start, periods=len(df), freq="5min")
    df.index.name = "datetime_utc"
    return df


def run_month(instrument, seed, p, fair_game=False):
    df = ticks_to_candles(gen(instrument, seed, fair_game))
    d = add_indicators(df, p)
    trades = simulate(d, detect_signals(d, p), p, apply_session=False)
    return summarize(trades, p), trades


# --------------------------------------------------------------------------- #
#  1) GOLD: RR sweep with a time-based train/test split
# --------------------------------------------------------------------------- #
def gold_experiment():
    print("=" * 78)
    print("GOLD (XAUUSD 5m, session ON) — reward:risk sweep, time split")
    print("=" * 78)
    base = Params(bar_minutes=5, session_filter=True)
    df = load_dukascopy_5m("data/XAUUSD_5M_dukascopy.csv")
    d = add_indicators(df, base)
    split = df.index.min() + (df.index.max() - df.index.min()) * 0.67  # ~2/3 in

    configs = [("SR (nearest)", replace(base, target_mode="sr"))]
    for rr in [1.0, 1.5, 2.0, 3.0]:
        configs.append((f"RR {rr}", replace(base, target_mode="rr", rr_multiple=rr)))

    rows = []
    for name, p in configs:
        trades = simulate(d, detect_signals(d, p), p, apply_session=True)
        tr_tr = [t for t in trades if t.entry_time < split]
        tr_te = [t for t in trades if t.entry_time >= split]
        s_all, s_tr, s_te = (summarize(trades, p), summarize(tr_tr, p),
                             summarize(tr_te, p))
        rows.append({
            "config": name, "n": s_all["n"],
            "train_win%": round(s_tr["win_rate"] * 100, 1),
            "train_avgR": round(s_tr["avg_r"], 3), "train_PF": round(s_tr["profit_factor"], 2),
            "test_win%": round(s_te["win_rate"] * 100, 1),
            "test_avgR": round(s_te["avg_r"], 3), "test_PF": round(s_te["profit_factor"], 2),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("(train = first ~2/3 by time, test = last ~1/3; positive test avgR/PF>1 = real)\n")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
#  2) SYNTHETICS: RR sweep with a seed-based train/test split
# --------------------------------------------------------------------------- #
def synth_experiment(instruments, fair_game=False, train_seeds=range(0, 12),
                     test_seeds=range(100, 112)):
    tag = " (FAIR-GAME calibration)" if fair_game else ""
    print("=" * 78)
    print(f"SYNTHETICS — RR sweep, seed train/test split{tag}")
    print("=" * 78)
    rr_grid = [1.0, 1.5, 2.0, 3.0]
    rows = []
    for inst in instruments:
        # pick best RR by TRAIN mean monthly return, then report TEST
        best = None
        for rr in rr_grid:
            p = replace(Params(), bar_minutes=5, session_filter=False,
                        spread_usd=(0.1 if inst == "Step" else 0.8),
                        slippage_usd=0.0, target_mode="rr", rr_multiple=rr)
            tr_ret = [run_month(inst, s, p, fair_game)[0].get("ret_pct", 0.0)
                      for s in train_seeds]
            tr_ret = [x for x in tr_ret if x == x]
            m = np.mean(tr_ret) if tr_ret else -999
            if best is None or m > best[1]:
                best = (rr, m, p)
        rr, train_mean, p = best
        te = [run_month(inst, s, p, fair_game)[0] for s in test_seeds]
        te = [s for s in te if s["n"] > 0]
        te_ret = np.array([s["ret_pct"] for s in te])
        rows.append({
            "instrument": inst, "best_RR_on_train": rr,
            "train_mean_ret%": round(train_mean, 2),
            "test_mean_ret%": round(te_ret.mean(), 2) if len(te_ret) else np.nan,
            "test_%green": round((te_ret > 0).mean() * 100, 0) if len(te_ret) else np.nan,
            "test_avg_trades": round(np.mean([s["n"] for s in te]), 0) if te else 0,
            "test_worst%": round(te_ret.min(), 1) if len(te_ret) else np.nan,
        })
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    print("(best RR chosen on TRAIN seeds; reported on unseen TEST seeds. "
          "Positive test_mean = holds up.)\n")
    return out


if __name__ == "__main__":
    g = gold_experiment()
    s1 = synth_experiment(["Vol75", "Vol100", "Step", "Boom 1000", "Crash 1000"])
    s2 = synth_experiment(["Boom 1000", "Crash 1000"], fair_game=True)

    g.to_csv("search_gold.csv", index=False)
    s1.to_csv("search_synth.csv", index=False)
    s2.to_csv("search_synth_fairgame.csv", index=False)
    print("[written] search_gold.csv, search_synth.csv, search_synth_fairgame.csv")
