"""
Illustrative test: run the SAME pullback-continuation engine on Deriv-style
synthetic indices, simulated from their DOCUMENTED generating processes.

*** NOT live Deriv data and NOT a prediction of real results. ***
Deriv synthetics are RNG feeds behind a paid API (websocket); the point here is
to show how the strategy interacts with each instrument's known structure, and
that a single month is a random draw around a negative mean.
"""
import numpy as np, pandas as pd
from dataclasses import replace
from backtest import Params, add_indicators, detect_signals, simulate, summarize

CANDLES_PER_MONTH = 30*24*12      # 8640 five-min candles, 24/7
TPC = 48                          # ~6s sub-ticks per 5m candle
N_MONTHS = 20                     # independent simulated months per instrument

def ticks_to_candles(price, tpc, start_time="2025-01-06"):
    n = len(price)//tpc*tpc
    p = price[:n].reshape(-1, tpc)
    df = pd.DataFrame({
        "open": p[:,0], "high": p.max(1), "low": p.min(1),
        "close": p[:,-1], "volume": float(tpc)})
    df.index = pd.date_range(start_time, periods=len(df), freq="5min")
    df.index.name = "datetime_utc"
    return df

def gen(instrument, seed):
    rng = np.random.default_rng(seed)
    N = CANDLES_PER_MONTH*TPC
    if instrument.startswith("Vol"):
        sigma = float(instrument[3:])/100.0
        dt = 6.0/(365*24*3600)                     # 6s tick in year units
        r = (-0.5*sigma**2)*dt + sigma*np.sqrt(dt)*rng.standard_normal(N)
        return 1000.0*np.exp(np.cumsum(r))
    if instrument == "Step":
        inc = rng.choice([-0.1, 0.1], size=N)
        return 9000.0 + np.cumsum(inc)
    if instrument.startswith(("Boom","Crash")):
        period = int(instrument.split()[-1])       # 500 or 1000
        drift_sign = +1 if instrument.startswith("Crash") else -1   # slow drift dir
        spike_sign = -drift_sign                                    # spike opposite
        delta = 0.05
        noise = rng.normal(0, 0.08, N)
        inc = drift_sign*delta + noise
        spikes = rng.random(N) < 1.0/period
        # spike magnitude ~ enough to overwhelm the between-spike drift
        mag = rng.uniform(0.6, 1.0, N)*(period*delta*1.6)
        inc = inc + spike_sign*spikes*mag
        return 10000.0 + np.cumsum(inc)
    raise ValueError(instrument)

INSTRUMENTS = ["Vol75","Vol100","Step","Boom 1000","Crash 1000","Boom 500","Crash 500"]
# synthetics trade 24/7 -> session filter OFF; small per-trade markup in points
COST = {"Vol75":0.5,"Vol100":0.6,"Step":0.1,"Boom 1000":1.0,"Crash 1000":1.0,
        "Boom 500":1.0,"Crash 500":1.0}

rows=[]
for inst in INSTRUMENTS:
    p = replace(Params(), bar_minutes=5, session_filter=False,
                spread_usd=COST[inst], slippage_usd=0.0)
    rets=[]; wins=[]; tgtfirst=[]; ntr=[]; worst_trade=[]
    for m in range(N_MONTHS):
        df = ticks_to_candles(gen(inst, seed=1000*hash(inst)%9999 + m), TPC)
        d = add_indicators(df, p)
        sigs = detect_signals(d, p)
        trades = simulate(d, sigs, p, apply_session=False)
        s = summarize(trades, p)
        if s["n"]==0: continue
        rets.append(s["ret_pct"]); wins.append(s["win_rate"]*100)
        tgtfirst.append(s["target_first_rate"]*100); ntr.append(s["n"])
        worst_trade.append(min(t.r_net for t in trades))
    rets=np.array(rets)
    rows.append({
        "instrument":inst,
        "months":len(rets),
        "avg_trades_per_month":np.mean(ntr).round(0),
        "mean_month_ret_%":rets.mean().round(2),
        "median_month_ret_%":np.median(rets).round(2),
        "%_months_green":round((rets>0).mean()*100,0),
        "best_%":rets.max().round(1),
        "worst_%":rets.min().round(1),
        "win_rate_%":round(np.mean(wins),1),
        "target_first_%":round(np.mean(tgtfirst),1),
        "worst_single_trade_R":round(float(np.mean(worst_trade)),1),
    })

res=pd.DataFrame(rows)
pd.set_option("display.width",200,"display.max_columns",20)
print(res.to_string(index=False))
res.to_csv("sim_synthetics_results.csv", index=False)

# random-walk baseline target-first for reference (Vol75, pooled)
p = replace(Params(), bar_minutes=5, session_filter=False)
from backtest import random_baseline
df = ticks_to_candles(gen("Vol75", seed=42), TPC)
d = add_indicators(df, p)
sigs = detect_signals(d, p); tr = simulate(d, sigs, p, False)
bl = random_baseline(d, p, n_entries=max(len(tr),1), apply_session=False)
print(f"\nVol75 pattern target-first: {summarize(tr,p)['target_first_rate']*100:.1f}%  "
      f"vs random baseline: {bl['target_first_rate']*100:.1f}% ± {bl['target_first_std']*100:.1f}%")
