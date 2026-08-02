import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from dataclasses import replace
from backtest import *

base = Params(bar_minutes=5, session_filter=True)
df = load_dukascopy_5m("data/XAUUSD_5M_dukascopy.csv"); d = add_indicators(df, base)
split = df.index.min() + (df.index.max()-df.index.min())*0.67

def eq_curve(p):
    tr = simulate(d, detect_signals(d,p), p, True)
    x = [t.exit_time for t in tr]; y=[t.equity_after for t in tr]
    return [df.index.min()]+x, [p.start_equity]+y, summarize(tr,p)

fig, ax = plt.subplots(figsize=(11,5.5))
for name,p,c in [("SR nearest (original)", replace(base,target_mode="sr"), "#b0392f"),
                 ("RR 2.0", replace(base,target_mode="rr",rr_multiple=2.0), "#2f7bb0"),
                 ("RR 3.0", replace(base,target_mode="rr",rr_multiple=3.0), "#c49a2f")]:
    x,y,s = eq_curve(p)
    ax.plot(x,y,lw=1.4,color=c,label=f"{name}: {s['n']} tr, PF {s['profit_factor']:.2f}, ret {s['ret_pct']:+.0f}%")
ax.axvline(split, color="gray", ls="--", lw=1); ax.axhline(base.start_equity,color="k",lw=.6,alpha=.4)
ax.text(split, ax.get_ylim()[1], " test split", va="top", fontsize=8, color="gray")
ax.set_title("Gold 5m pullback-continuation: nearest-S/R target vs fixed reward:risk target\n(1% risk/trade; dashed line = out-of-sample split)", fontsize=11)
ax.set_ylabel("equity ($)"); ax.set_xlabel("date"); ax.grid(alpha=.25); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig("improved_gold_equity.png", dpi=110)
print("saved improved_gold_equity.png")
