"""
Experiment: double-top/bottom + 50%/20% layering across the synthetics (and gold).

Answers two independent questions and keeps them separate:
  (A) EDGE  — pool per-campaign R over many seeds at TINY risk (no ruin truncation).
              Mean R > 0 means the pattern+management actually has an edge.
  (B) RUIN  — apply the literal 50% initial + 20% add sizing per seed-month and
              measure how often the account is blown (equity < 20% of start).

Outputs a table, a CSV, and a plot (sample equity paths + final-equity histogram).
NOT live Deriv data; NOT financial advice.
"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from dataclasses import replace
from pattern_layering import LayerParams, run_instrument, ticks_to_candles, gen
from backtest import load_dukascopy_5m, add_indicators, Params

SYNTH = ["Vol75", "Vol100", "Step", "Boom 1000", "Crash 1000"]
COST = {"Vol75": 0.6, "Vol100": 0.7, "Step": 0.1, "Boom 1000": 1.0,
        "Crash 1000": 1.0, "Gold": 0.4}


def long_series(inst, seed, months):
    """Concatenate `months` independent monthly tick-blocks into one price path."""
    parts = [gen(inst, seed * 97 + m) for m in range(months)]
    # stitch so there is no artificial jump: rebase each part to the previous close
    price = parts[0]
    for nxt in parts[1:]:
        price = np.concatenate([price, nxt - nxt[0] + price[-1]])
    return ticks_to_candles(price)


# --------------------------------------------------------------------------- #
#  (A) EDGE — tiny risk, no ruin stop, pool campaign R across seeds
# --------------------------------------------------------------------------- #
def edge_table(n_seeds=12, months=3):
    # constant $ risk so per-campaign R is clean and never truncated by ruin
    tiny = LayerParams(fixed_risk_dollars=100.0, ruin_level=-1.0)
    rows = []
    for inst in SYNTH:
        Rs = []
        for s in range(n_seeds):
            df = long_series(inst, s, months)
            res, _, _ = run_instrument(inst, df, tiny, COST[inst])
            Rs.append(res["rs"])
        R = np.concatenate(Rs) if Rs else np.array([])
        rows.append(_edge_row(inst, R))
    # gold (real, single path)
    gdf = load_dukascopy_5m("data/XAUUSD_5M_dukascopy.csv")
    res, _, _ = run_instrument("Gold", gdf, tiny, COST["Gold"])
    rows.append(_edge_row("Gold (real)", res["rs"]))
    return pd.DataFrame(rows)


def _edge_row(inst, R):
    if len(R) == 0:
        return {"instrument": inst, "campaigns": 0, "win%": np.nan,
                "mean_R": np.nan, "expectancy_note": "no setups"}
    return {
        "instrument": inst, "campaigns": len(R),
        "win%": round((R > 0).mean() * 100, 1),
        "mean_R": round(float(R.mean()), 3),
        "median_R": round(float(np.median(R)), 3),
        "worst_R": round(float(R.min()), 2),
        "stderr": round(float(R.std() / np.sqrt(len(R))), 3),
    }


# --------------------------------------------------------------------------- #
#  (B) RUIN — literal 50/20 sizing, per seed-month, blow-up frequency
# --------------------------------------------------------------------------- #
def ruin_table(n_seeds=120, months=1):
    p = LayerParams()  # 50% / 20% defaults
    rows = []; paths = {}
    for inst in SYNTH:
        finals = []; blown = 0; ncamp = []; sample_paths = []
        for s in range(n_seeds):
            df = long_series(inst, s, months)
            res, eqp, _ = run_instrument(inst, df, p, COST[inst])
            finals.append(res["final_equity"]); ncamp.append(res["campaigns"])
            blown += int(res["blown"])
            if len(sample_paths) < 12:
                sample_paths.append(eqp)
        finals = np.array(finals)
        paths[inst] = sample_paths
        rows.append({
            "instrument": inst,
            "avg_campaigns/mo": round(np.mean(ncamp), 1),
            "median_final_$": round(float(np.median(finals)), 0),
            "mean_final_$": round(float(finals.mean()), 0),
            "%_blown(<20%)": round(blown / n_seeds * 100, 0),
            "%_ended_up": round((finals > p.start_equity).mean() * 100, 0),
            "worst_$": round(float(finals.min()), 0),
        })
    return pd.DataFrame(rows), paths


def plot_ruin(paths, p_start=10_000.0):
    fig, axes = plt.subplots(1, len(paths), figsize=(4 * len(paths), 4), sharey=True)
    for ax, (inst, ps) in zip(axes, paths.items()):
        for eqp in ps:
            ax.plot(eqp, lw=1, alpha=0.7)
        ax.axhline(p_start, color="k", lw=0.6, ls="--")
        ax.axhline(0.20 * p_start, color="red", lw=0.8, ls=":")
        ax.set_title(inst, fontsize=10)
        ax.set_xlabel("campaign #"); ax.set_yscale("symlog")
    axes[0].set_ylabel("equity $ (symlog; red = ruin line)")
    fig.suptitle("50%/20% layering on double-top/bottom — sample equity paths per month\n"
                 "(each line = one simulated month; RNG synthetics)", fontsize=11)
    fig.tight_layout()
    fig.savefig("layering_ruin_paths.png", dpi=110)
    print("saved layering_ruin_paths.png")


if __name__ == "__main__":
    print("=" * 74); print("(A) EDGE — per-campaign expectancy (tiny risk, pooled)"); print("=" * 74)
    et = edge_table()
    print(et.to_string(index=False))
    et.to_csv("layering_edge.csv", index=False)

    print("\n" + "=" * 74); print("(B) RUIN — literal 50% + 20% sizing, per simulated month"); print("=" * 74)
    rt, paths = ruin_table()
    print(rt.to_string(index=False))
    rt.to_csv("layering_ruin.csv", index=False)
    plot_ruin(paths)
    print("\n[written] layering_edge.csv, layering_ruin.csv, layering_ruin_paths.png")
