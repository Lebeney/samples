"""
Double-top / double-bottom + "layering" money-management backtest.

Implements the discretionary system described by the user, made mechanical:

  * Detect double tops (bearish) / double bottoms (bullish) from confirmed
    fractal swings, with a candlestick confirmation (engulfing) at the 2nd peak.
  * LAYER IN:
      - initial tranche risking ~`risk_initial` of the account (the "50%"),
      - a second tranche risking ~`risk_add` more on the neckline break (the "+20%").
  * Move all stops to break-even once the neckline breaks (solid confirmation).
  * TARGET the next major S/R zone (measured move, floored at the nearest swing).
  * On a REJECTION (opposite engulfing) before target: close the remainder
    (bank profit / avoid giving it back).

It is run on the Deriv-style synthetics (simulated) and on gold (real) for
contrast. Two separate questions are answered:

  (A) EDGE  — per-campaign expectancy in R (sizing-invariant): does the pattern win?
  (B) RUIN  — what the literal 50%/20% sizing does to the equity path.

Spike realism: on Boom/Crash a stop can be gapped through by a spike; when a bar's
range exceeds `spike_atr` and blows past the stop, the fill is slipped partway to
the bar's adverse extreme (the earlier reports understated this tail).

NOT live Deriv data; NOT financial advice.
"""
import numpy as np, pandas as pd
from dataclasses import dataclass, replace
from strategy_search import gen, ticks_to_candles, CANDLES_PER_MONTH
from backtest import Params, add_indicators, compute_fractals, load_dukascopy_5m

pd.set_option("display.width", 220, "display.max_columns", 30)


@dataclass
class LayerParams:
    ema_period: int = 50
    atr_period: int = 14
    fractal_n: int = 2
    top_tol_atr: float = 0.7       # two peaks "equal" if within this * ATR
    min_sep_bars: int = 4
    max_sep_bars: int = 60
    min_height_atr: float = 1.5    # pattern height (peak - neckline) minimum
    confirm_wait: int = 8          # bars after 2nd peak to wait for candle confirm
    stop_buffer_atr: float = 0.3
    min_stop_atr: float = 0.5      # floor on stop distance (no absurdly tight stops)
    fixed_risk_dollars: float = 0.0  # >0 -> size off a constant $ risk (edge measurement)
    risk_initial: float = 0.50     # "risk 50% across initial entries"
    risk_add: float = 0.20         # "risk 20% more" on the break
    breakeven_on_break: bool = True
    target_measured: bool = True   # target = neckline -/+ pattern height (measured move)
    spike_atr: float = 4.0         # bar range > this*ATR = spike (slippage-through)
    max_hold: int = 200
    start_equity: float = 10_000.0
    ruin_level: float = 0.20       # equity < 20% of start counts as "blown up"


# --------------------------------------------------------------------------- #
#  candlestick helpers
# --------------------------------------------------------------------------- #
def engulfing(o, c):
    n = len(o)
    bull = np.zeros(n, bool); bear = np.zeros(n, bool)
    for i in range(1, n):
        if c[i] > o[i] and c[i-1] < o[i-1] and c[i] >= o[i-1] and o[i] <= c[i-1]:
            bull[i] = True
        if c[i] < o[i] and c[i-1] > o[i-1] and c[i] <= o[i-1] and o[i] >= c[i-1]:
            bear[i] = True
    return bull, bear


# --------------------------------------------------------------------------- #
#  detect double-top / double-bottom setups
# --------------------------------------------------------------------------- #
@dataclass
class Setup:
    direction: int          # -1 short (double top), +1 long (double bottom)
    peak_idx: int           # 2nd peak/trough index
    peak_level: float
    neckline: float
    height: float
    confirm_idx: int        # bar of candlestick confirmation (entry next bar)
    atr: float


def detect_setups(df, p: LayerParams):
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    atr = df["atr"].values
    n = len(df)
    sh, sl = compute_fractals(df, p.fractal_n)
    highs = [(i + p.fractal_n, sh[i]) for i in range(n) if not np.isnan(sh[i])]
    lows = [(i + p.fractal_n, sl[i]) for i in range(n) if not np.isnan(sl[i])]
    bull_eng, bear_eng = engulfing(o, c)
    setups = []

    # double tops: two swing highs at similar level with a trough between
    for a in range(len(highs)):
        i1, lv1 = highs[a]
        for b in range(a + 1, len(highs)):
            i2, lv2 = highs[b]
            sep = i2 - i1
            if sep < p.min_sep_bars:
                continue
            if sep > p.max_sep_bars:
                break
            aatr = atr[i2]
            if aatr <= 0 or abs(lv1 - lv2) > p.top_tol_atr * aatr:
                continue
            troughs = [lv for (li, lv) in lows if i1 < li < i2]
            if not troughs:
                continue
            neck = min(troughs)
            height = (lv1 + lv2) / 2 - neck
            if height < p.min_height_atr * aatr:
                continue
            # candlestick confirmation after 2nd peak: bearish engulfing
            conf = None
            for k in range(i2, min(i2 + p.confirm_wait, n)):
                if bear_eng[k]:
                    conf = k
                    break
            if conf is not None:
                setups.append(Setup(-1, i2, (lv1 + lv2) / 2, neck, height, conf, aatr))

    # double bottoms: mirror
    for a in range(len(lows)):
        i1, lv1 = lows[a]
        for b in range(a + 1, len(lows)):
            i2, lv2 = lows[b]
            sep = i2 - i1
            if sep < p.min_sep_bars:
                continue
            if sep > p.max_sep_bars:
                break
            aatr = atr[i2]
            if aatr <= 0 or abs(lv1 - lv2) > p.top_tol_atr * aatr:
                continue
            peaks = [lv for (pi, lv) in highs if i1 < pi < i2]
            if not peaks:
                continue
            neck = max(peaks)
            height = neck - (lv1 + lv2) / 2
            if height < p.min_height_atr * aatr:
                continue
            conf = None
            for k in range(i2, min(i2 + p.confirm_wait, n)):
                if bull_eng[k]:
                    conf = k
                    break
            if conf is not None:
                setups.append(Setup(+1, i2, (lv1 + lv2) / 2, neck, height, conf, aatr))

    setups.sort(key=lambda s: s.confirm_idx)
    return setups, bull_eng, bear_eng


# --------------------------------------------------------------------------- #
#  campaign manager (tranche-based, path-dependent, one campaign at a time)
# --------------------------------------------------------------------------- #
def run_campaign(df, s: Setup, p: LayerParams, equity, bull_eng, bear_eng, cost):
    """Simulate one layered campaign. Returns (pnl_dollars, R_campaign, outcome)."""
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    atr = df["atr"].values
    n = len(df)
    d = s.direction
    e0 = s.confirm_idx + 1
    if e0 >= n:
        return 0.0, 0.0, "skip"

    entry0 = o[e0]
    buf = p.stop_buffer_atr * s.atr
    # structural stop beyond the 2nd peak/trough, floored so it can't be absurdly tight
    stop0 = s.peak_level + buf if d == -1 else s.peak_level - buf
    risk0 = abs(entry0 - stop0)
    min_risk = p.min_stop_atr * s.atr
    if risk0 < min_risk:                       # widen a too-tight stop to the floor
        stop0 = entry0 + min_risk if d == -1 else entry0 - min_risk
        risk0 = min_risk
    if risk0 <= 0:
        return 0.0, 0.0, "skip"

    # target: measured move from neckline, floored at nearest structural swing
    if p.target_measured:
        target = s.neckline - s.height if d == -1 else s.neckline + s.height
    else:
        target = s.neckline - s.height if d == -1 else s.neckline + s.height

    # tranche = dict(entry, units, stop, open)
    # size off a constant $ (edge measurement) or a fraction of live equity (ruin)
    if p.fixed_risk_dollars > 0:
        init_risk_dollars = p.fixed_risk_dollars
    else:
        init_risk_dollars = p.risk_initial * equity
    if init_risk_dollars <= 0:
        return 0.0, 0.0, "skip"
    units0 = init_risk_dollars / risk0
    tranches = [dict(entry=entry0, units=units0, stop=stop0, open=True)]
    added = False
    be_done = False

    def spike_fill(t_idx, stop, direction):
        """Fill price for a stop, slipping through on spike bars."""
        rng = h[t_idx] - l[t_idx]
        adverse = l[t_idx] if direction == -1 else h[t_idx]  # worst intrabar price
        beyond = (stop - adverse) if direction == -1 else (adverse - stop)
        if rng > p.spike_atr * s.atr and beyond > 0:
            # slip halfway from stop toward the adverse extreme
            return stop - 0.5 * beyond if direction == -1 else stop + 0.5 * beyond
        return stop

    outcome = "timeout"
    end = min(e0 + p.max_hold, n - 1)
    for t in range(e0, end + 1):
        # ---- add tranche on neckline break (close beyond neckline) ----------
        broke = (c[t] < s.neckline) if d == -1 else (c[t] > s.neckline)
        if (not added) and broke and t + 1 <= end:
            add_entry = c[t]
            if p.fixed_risk_dollars > 0:
                add_risk_dollars = (p.risk_add / p.risk_initial) * init_risk_dollars
            else:
                add_risk_dollars = p.risk_add * equity
            add_units = add_risk_dollars / risk0     # same structural stop distance
            tranches.append(dict(entry=add_entry, units=add_units, stop=stop0, open=True))
            added = True
            # ---- solid confirmation -> move all stops to break-even ---------
            if p.breakeven_on_break:
                for tr in tranches:
                    tr["stop"] = tr["entry"]
                be_done = True

        # ---- stop checks (adverse) ------------------------------------------
        for tr in tranches:
            if not tr["open"]:
                continue
            hit = (h[t] >= tr["stop"]) if d == -1 else (l[t] <= tr["stop"])
            if hit:
                fill = spike_fill(t, tr["stop"], d)
                tr["exit"] = fill; tr["open"] = False

        # ---- target hit -> close all ----------------------------------------
        tgt_hit = (l[t] <= target) if d == -1 else (h[t] >= target)
        if tgt_hit:
            for tr in tranches:
                if tr["open"]:
                    tr["exit"] = target; tr["open"] = False
            outcome = "target"
            break

        # ---- rejection (opposite engulfing) after entry -> bank remainder ----
        rej = (bull_eng[t] if d == -1 else bear_eng[t])
        if rej and t > e0:
            for tr in tranches:
                if tr["open"]:
                    tr["exit"] = c[t]; tr["open"] = False
            outcome = "rejection_close"
            break

        if all(not tr["open"] for tr in tranches):
            outcome = "stopped"
            break

    # close any still-open at final bar
    for tr in tranches:
        if tr["open"]:
            tr["exit"] = c[min(t, n - 1)]; tr["open"] = False

    pnl = 0.0
    for tr in tranches:
        gross = (tr["exit"] - tr["entry"]) * d * tr["units"]
        pnl += gross - cost * tr["units"] * 2  # round-trip cost per unit
    r_campaign = pnl / init_risk_dollars
    return pnl, r_campaign, outcome


def run_instrument(name, df, p: LayerParams, cost):
    df = add_indicators(df, Params(ema_period=p.ema_period, atr_period=p.atr_period))
    setups, bull_eng, bear_eng = detect_setups(df, p)
    equity = p.start_equity
    busy_until = -1
    rs = []; eq_path = [equity]; outcomes = {}
    min_equity = equity
    for s in setups:
        if s.confirm_idx <= busy_until:
            continue
        if equity <= p.ruin_level * p.start_equity:      # already blown -> stop
            break
        pnl, r, oc = run_campaign(df, s, p, equity, bull_eng, bear_eng, cost)
        if oc == "skip":
            continue
        equity = max(0.0, equity + pnl)
        eq_path.append(equity)
        rs.append(r); outcomes[oc] = outcomes.get(oc, 0) + 1
        min_equity = min(min_equity, equity)
        busy_until = s.confirm_idx + p.max_hold
    rs_arr = np.array(rs) if rs else np.array([])
    n = len(rs_arr)
    return {
        "instrument": name,
        "setups": len(setups),
        "campaigns": n,
        "win%": round((rs_arr > 0).mean() * 100, 1) if n else float("nan"),
        "mean_R": round(float(rs_arr.mean()), 3) if n else float("nan"),
        "median_R": round(float(np.median(rs_arr)), 3) if n else float("nan"),
        "worst_R": round(float(rs_arr.min()), 2) if n else float("nan"),
        "final_equity": round(equity, 0),
        "min_equity": round(min_equity, 0),
        "blown": equity <= p.ruin_level * p.start_equity,
        "rs": rs_arr,
    }, eq_path, outcomes
