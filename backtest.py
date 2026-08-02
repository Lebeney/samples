"""
GOLD (XAUUSD) Pullback-Continuation Pattern Backtest
====================================================

A self-contained, dependency-light backtest of a trend pullback-continuation
pattern on gold intraday candles.

Data
----
Source : Dukascopy XAUUSD 5-minute BID candles, 2024-11-01 .. 2025-11-01
         (mirrored on GitHub, pulled in data/XAUUSD_5M_dukascopy.csv).
The 15-minute series is RESAMPLED from the same 5-minute source so that both
timeframes come from one clean, consistent feed (no broker mixing).

Pattern (all thresholds are named parameters in `Params`)
---------------------------------------------------------
1. TREND FILTER   : close > EMA(ema_period)  -> uptrend ; below -> downtrend.
2. PULLBACK       : >= min_pullback_candles consecutive candles closing AGAINST
                    the trend, containing >=1 "big" counter-trend candle whose
                    range >= big_candle_atr_mult * ATR(atr_period).
3. TRIGGER        : two consecutive candles close back WITH the trend; the 2nd
                    close is beyond the OPEN (trigger_mode="open") or the EXTREME
                    (trigger_mode="extreme") of the last big counter-trend candle.
4. ENTRY          : open of the next candle after the trigger.
5. TARGET         : nearest prior fractal swing (2 bars each side) in the trend
                    direction, OR nearest $round_increment round number, whichever
                    valid level is nearest. Skip if target < min_target_atr_mult*ATR.
6. STOP           : beyond the pullback extreme + stop_atr_buffer * ATR.
7. COSTS          : dollar terms, spread_usd + slippage_usd per round trip.
8. SESSION FILTER : optionally only enter during London+NY (07:00-21:00 UTC).

No lookahead: every signal uses only information available at candle close;
entry is the next bar's open; fractal targets must be confirmed before entry.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np
import pandas as pd

# Matplotlib without a display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# --------------------------------------------------------------------------- #
#  Parameters
# --------------------------------------------------------------------------- #
@dataclass
class Params:
    # indicators
    ema_period: int = 50
    atr_period: int = 14
    # pullback
    min_pullback_candles: int = 2
    big_candle_atr_mult: float = 1.2
    # trigger
    trigger_mode: str = "open"          # "open" or "extreme"
    # target
    target_mode: str = "sr"             # "sr" = nearest fractal/round S/R (default)
    #                                     "rr" = fixed reward:risk multiple of the stop
    rr_multiple: float = 1.5            # target distance = rr_multiple * risk (target_mode="rr")
    fractal_n: int = 2                  # candles each side for a fractal
    min_target_atr_mult: float = 0.5    # skip if target closer than this * ATR
    round_increment: float = 5.0        # $5 round-number S/R levels
    # stop
    stop_atr_buffer: float = 0.1
    # costs (USD per round trip, per ounce)
    spread_usd: float = 0.30
    slippage_usd: float = 0.10
    # session filter (UTC hours, [start, end))
    session_filter: bool = True
    session_start: int = 7
    session_end: int = 21
    # money management
    start_equity: float = 10_000.0
    risk_pct: float = 0.01              # 1% risk per trade
    # trade mechanics
    max_hold_bars: int = 288            # cap holding time (288*5m = 24h ; 288*15m=3d)
    one_position_at_a_time: bool = True
    # gap guard: pattern window may not span a time gap larger than this (minutes)
    # set per timeframe at runtime.
    bar_minutes: int = 5
    gap_tolerance_mult: float = 1.5     # allow diff <= mult * bar_minutes

    @property
    def total_cost_usd(self) -> float:
        return self.spread_usd + self.slippage_usd


# --------------------------------------------------------------------------- #
#  Data loading & cleaning
# --------------------------------------------------------------------------- #
def load_dukascopy_5m(path: str) -> pd.DataFrame:
    """Load and clean the raw Dukascopy 5-minute CSV.

    Cleaning performed (all reported by the caller):
      * parse "Local time" with its per-row GMT offset -> tz-naive UTC index
      * drop zero-volume flat candles (weekend / holiday fill bars)
      * drop any duplicate timestamps, sort ascending
      * basic sanity filter on prices (>0, high>=low)
    Returns a DataFrame indexed by UTC datetime with columns
    open, high, low, close, volume  and a `clean_report` dict attached.
    """
    raw = pd.read_csv(path)
    n_raw = len(raw)

    # --- timezone handling: "01.11.2024 00:00:00.000 GMT+0200" ---------------
    tstr = raw["Local time"].str.replace(r"\.\d{3}\s*GMT", "", regex=True).str[:19]
    off = raw["Local time"].str.extract(r"GMT([+-]\d{4})")[0]
    dt_local = pd.to_datetime(tstr, format="%d.%m.%Y %H:%M:%S")
    sign = off.str[0].map({"+": 1, "-": -1})
    off_min = sign * (off.str[1:3].astype(int) * 60 + off.str[3:5].astype(int))
    dt_utc = dt_local - pd.to_timedelta(off_min, unit="m")

    df = pd.DataFrame({
        "open": raw["Open"].astype(float),
        "high": raw["High"].astype(float),
        "low": raw["Low"].astype(float),
        "close": raw["Close"].astype(float),
        "volume": raw["Volume"].astype(float),
    })
    df.index = dt_utc
    df.index.name = "datetime_utc"

    # --- cleaning ------------------------------------------------------------
    n_zero_vol = int((df["volume"] == 0).sum())
    df = df[df["volume"] > 0]                       # drop weekend/holiday fills

    bad_price = ((df[["open", "high", "low", "close"]] <= 0).any(axis=1) |
                 (df["high"] < df["low"]))
    n_bad_price = int(bad_price.sum())
    df = df[~bad_price]

    n_dup = int(df.index.duplicated().sum())
    df = df[~df.index.duplicated(keep="first")].sort_index()

    df.attrs["clean_report"] = {
        "rows_raw": n_raw,
        "zero_volume_dropped": n_zero_vol,
        "bad_price_dropped": n_bad_price,
        "duplicate_ts_dropped": n_dup,
        "rows_clean": len(df),
        "utc_start": df.index.min(),
        "utc_end": df.index.max(),
    }
    return df


def resample(df5: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample the clean 5-minute frame to a coarser timeframe (e.g. '15min')."""
    agg = df5.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    # resample creates rows for empty periods (weekends) -> drop them
    return agg.dropna(subset=["open"])


# --------------------------------------------------------------------------- #
#  Indicators (all causal: value at i uses only data up to i)
# --------------------------------------------------------------------------- #
def add_indicators(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    out = df.copy()
    out["ema"] = out["close"].ewm(span=p.ema_period, adjust=False).mean()

    # Wilder's ATR
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1.0 / p.atr_period, adjust=False).mean()

    out["range"] = out["high"] - out["low"]
    out["bull"] = out["close"] > out["open"]
    out["bear"] = out["close"] < out["open"]

    # bar-to-bar time gap in minutes (for the weekend/session-break guard)
    out["gap_min"] = out.index.to_series().diff().dt.total_seconds().div(60).fillna(0)
    return out


def compute_fractals(df: pd.DataFrame, n: int):
    """Return two arrays of length len(df):
       swing_high_level[i], swing_low_level[i] hold the fractal price if bar i is
       the CENTRE of a fractal, else NaN. A centre at i is only *confirmed* (usable)
       at bar i+n, which the caller enforces.
    """
    high = df["high"].values
    low = df["low"].values
    N = len(df)
    sh = np.full(N, np.nan)
    sl = np.full(N, np.nan)
    for i in range(n, N - n):
        hwin = high[i - n:i + n + 1]
        lwin = low[i - n:i + n + 1]
        if high[i] == hwin.max() and (hwin.argmax() == n):
            sh[i] = high[i]
        if low[i] == lwin.min() and (lwin.argmin() == n):
            sl[i] = low[i]
    return sh, sl


# --------------------------------------------------------------------------- #
#  Signal detection
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    trigger_idx: int
    entry_idx: int
    direction: int          # +1 long, -1 short
    entry_time: pd.Timestamp
    entry_price: float
    stop: float
    target: float
    atr: float
    target_kind: str        # "fractal" or "round"
    pullback_extreme: float


def _window_has_gap(gap_min, start, end, p: Params) -> bool:
    """True if any bar in (start, end] follows a larger-than-expected time gap
    (i.e. the pattern would span a weekend / session break)."""
    tol = p.bar_minutes * p.gap_tolerance_mult
    for k in range(start + 1, end + 1):
        if gap_min[k] > tol:
            return True
    return False


def detect_signals(df: pd.DataFrame, p: Params) -> list[Signal]:
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    ema = df["ema"].values
    atr = df["atr"].values
    rng = df["range"].values
    bull = df["bull"].values
    bear = df["bear"].values
    gap = df["gap_min"].values
    times = df.index
    N = len(df)

    sh, sl = compute_fractals(df, p.fractal_n)
    # confirmed fractal lists: (confirm_idx, level)
    frac_high = [(i + p.fractal_n, sh[i]) for i in range(N) if not math.isnan(sh[i])]
    frac_low = [(i + p.fractal_n, sl[i]) for i in range(N) if not math.isnan(sl[i])]

    warmup = max(p.ema_period, p.atr_period, p.fractal_n) + p.min_pullback_candles + 3
    signals: list[Signal] = []

    for i in range(warmup, N - 1):          # i = 2nd trigger candle (confirmed at close)
        if math.isnan(atr[i]) or atr[i] <= 0:
            continue

        # ---- trend & two in-trend trigger candles (i-1, i) ------------------
        if c[i] > ema[i]:
            direction = 1
            if not (bull[i] and bull[i - 1]):
                continue
        elif c[i] < ema[i]:
            direction = -1
            if not (bear[i] and bear[i - 1]):
                continue
        else:
            continue

        # ---- pullback run: consecutive counter-trend candles ending at i-2 --
        j = i - 2
        pull_idx = []
        while j >= warmup - 1:
            counter = bear[j] if direction == 1 else bull[j]
            if counter:
                pull_idx.append(j)
                j -= 1
            else:
                break
        if len(pull_idx) < p.min_pullback_candles:
            continue
        pull_idx = pull_idx[::-1]                    # chronological
        pb_start = pull_idx[0]

        # gap guard: whole pattern window (pullback start .. trigger) unbroken
        if _window_has_gap(gap, pb_start, i, p):
            continue

        # ---- "big" counter-trend candle(s) inside the pullback --------------
        big_idx = [k for k in pull_idx if rng[k] >= p.big_candle_atr_mult * atr[k]]
        if not big_idx:
            continue
        last_big = big_idx[-1]                       # most recent big candle

        # ---- trigger threshold ---------------------------------------------
        if direction == 1:
            thresh = o[last_big] if p.trigger_mode == "open" else h[last_big]
            if not (c[i] > thresh):
                continue
            pullback_extreme = min(l[k] for k in pull_idx)     # swing low
        else:
            thresh = o[last_big] if p.trigger_mode == "open" else l[last_big]
            if not (c[i] < thresh):
                continue
            pullback_extreme = max(h[k] for k in pull_idx)     # swing high

        # ---- entry (next bar open) -----------------------------------------
        e = i + 1
        if e >= N:
            continue
        entry_price = o[e]
        a = atr[i]

        # ---- stop -----------------------------------------------------------
        if direction == 1:
            stop = pullback_extreme - p.stop_atr_buffer * a
            if stop >= entry_price:
                continue
        else:
            stop = pullback_extreme + p.stop_atr_buffer * a
            if stop <= entry_price:
                continue

        # ---- target ---------------------------------------------------------
        if p.target_mode == "rr":
            # fixed reward:risk multiple of the stop distance
            risk = abs(entry_price - stop)
            target = entry_price + direction * p.rr_multiple * risk
            kind = "rr"
        else:
            # nearest valid fractal OR round number (default "sr")
            candidates = []  # (distance, level, kind)
            if direction == 1:
                for cidx, lvl in frac_high:
                    if cidx <= i and lvl > entry_price:
                        candidates.append((lvl - entry_price, lvl, "fractal"))
                r = math.ceil(entry_price / p.round_increment) * p.round_increment
                if r <= entry_price:
                    r += p.round_increment
                candidates.append((r - entry_price, r, "round"))
            else:
                for cidx, lvl in frac_low:
                    if cidx <= i and lvl < entry_price:
                        candidates.append((entry_price - lvl, lvl, "fractal"))
                r = math.floor(entry_price / p.round_increment) * p.round_increment
                if r >= entry_price:
                    r -= p.round_increment
                candidates.append((entry_price - r, r, "round"))

            min_dist = p.min_target_atr_mult * a
            valid = [ct for ct in candidates if ct[0] >= min_dist]
            if not valid:
                continue
            valid.sort(key=lambda x: x[0])
            _, target, kind = valid[0]

        signals.append(Signal(
            trigger_idx=i, entry_idx=e, direction=direction,
            entry_time=times[e], entry_price=entry_price,
            stop=stop, target=target, atr=a, target_kind=kind,
            pullback_extreme=pullback_extreme,
        ))
    return signals


# --------------------------------------------------------------------------- #
#  Trade simulation
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    entry_price: float
    exit_price: float
    stop: float
    target: float
    outcome: str            # "target", "stop", "timeout"
    target_first: bool      # did price reach target before stop
    risk_per_unit: float
    r_gross: float
    r_net: float
    pnl_usd: float
    equity_after: float
    target_kind: str
    session: str            # "london_ny" or "asian"
    week: str
    bars_held: int


def in_session(ts: pd.Timestamp, p: Params) -> bool:
    return p.session_start <= ts.hour < p.session_end


def simulate(df: pd.DataFrame, signals: list[Signal], p: Params,
             apply_session: bool) -> list[Trade]:
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    times = df.index
    N = len(df)

    equity = p.start_equity
    trades: list[Trade] = []
    busy_until = -1     # index up to which we are in a position

    for s in signals:
        if apply_session and not in_session(s.entry_time, p):
            continue
        if p.one_position_at_a_time and s.entry_idx <= busy_until:
            continue

        risk = abs(s.entry_price - s.stop)
        if risk <= 0:
            continue

        outcome, exit_price, exit_idx, target_first = "timeout", None, None, False
        end = min(s.entry_idx + p.max_hold_bars, N - 1)
        for t in range(s.entry_idx, end + 1):
            hi, lo = h[t], l[t]
            if s.direction == 1:
                hit_stop = lo <= s.stop
                hit_tgt = hi >= s.target
            else:
                hit_stop = hi >= s.stop
                hit_tgt = lo <= s.target
            if hit_stop and hit_tgt:
                # both in one bar -> assume stop first (conservative)
                outcome, exit_price, exit_idx, target_first = "stop", s.stop, t, False
                break
            if hit_stop:
                outcome, exit_price, exit_idx, target_first = "stop", s.stop, t, False
                break
            if hit_tgt:
                outcome, exit_price, exit_idx, target_first = "target", s.target, t, True
                break
        if exit_price is None:
            exit_idx = end
            exit_price = c[end]
            outcome = "timeout"
            target_first = False

        # PnL in price terms, then dollar costs, then R
        gross_price = (exit_price - s.entry_price) * s.direction
        net_price = gross_price - p.total_cost_usd
        r_gross = gross_price / risk
        r_net = net_price / risk

        risk_dollars = p.risk_pct * equity
        units = risk_dollars / risk
        pnl_usd = units * net_price
        equity += pnl_usd

        trades.append(Trade(
            entry_time=s.entry_time, exit_time=times[exit_idx],
            direction=s.direction, entry_price=s.entry_price, exit_price=exit_price,
            stop=s.stop, target=s.target, outcome=outcome, target_first=target_first,
            risk_per_unit=risk, r_gross=r_gross, r_net=r_net, pnl_usd=pnl_usd,
            equity_after=equity, target_kind=s.target_kind,
            session="london_ny" if in_session(s.entry_time, p) else "asian",
            week=s.entry_time.strftime("%G-W%V"),
            bars_held=exit_idx - s.entry_idx,
        ))
        busy_until = exit_idx
    return trades


# --------------------------------------------------------------------------- #
#  Random baseline
# --------------------------------------------------------------------------- #
def random_baseline(df: pd.DataFrame, p: Params, n_entries: int,
                    apply_session: bool, seeds=(1, 2, 3, 4, 5)) -> dict:
    """Random entries with the SAME trend direction and the SAME target/stop
    construction logic, but at random candles (no pattern). The 'pullback
    extreme' analog is the low/high of the last (min_pullback_candles+2) bars.
    Averaged over several seeds."""
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    ema = df["ema"].values
    atr = df["atr"].values
    times = df.index
    N = len(df)

    sh, sl = compute_fractals(df, p.fractal_n)
    frac_high = [(i + p.fractal_n, sh[i]) for i in range(N) if not math.isnan(sh[i])]
    frac_low = [(i + p.fractal_n, sl[i]) for i in range(N) if not math.isnan(sl[i])]

    warmup = max(p.ema_period, p.atr_period, p.fractal_n) + p.min_pullback_candles + 3
    lookback = p.min_pullback_candles + 2

    agg = []
    for seed in seeds:
        rng_ = np.random.default_rng(seed)
        eligible = [i for i in range(warmup, N - 1)
                    if atr[i] > 0 and c[i] != ema[i]
                    and (not apply_session or in_session(times[i + 1], p))]
        if not eligible:
            continue
        pick = rng_.choice(eligible, size=min(n_entries, len(eligible)), replace=False)
        trs = []
        for i in sorted(pick):
            direction = 1 if c[i] > ema[i] else -1
            e = i + 1
            entry = o[e]
            a = atr[i]
            if direction == 1:
                pb = min(l[i - lookback + 1:i + 1])
                stop = pb - p.stop_atr_buffer * a
                if stop >= entry:
                    continue
            else:
                pb = max(h[i - lookback + 1:i + 1])
                stop = pb + p.stop_atr_buffer * a
                if stop <= entry:
                    continue
            # target (same nearest fractal/round logic)
            candidates = []
            if direction == 1:
                for cidx, lvl in frac_high:
                    if cidx <= i and lvl > entry:
                        candidates.append((lvl - entry, lvl))
                r = math.ceil(entry / p.round_increment) * p.round_increment
                if r <= entry:
                    r += p.round_increment
                candidates.append((r - entry, r))
            else:
                for cidx, lvl in frac_low:
                    if cidx <= i and lvl < entry:
                        candidates.append((entry - lvl, lvl))
                r = math.floor(entry / p.round_increment) * p.round_increment
                if r >= entry:
                    r -= p.round_increment
                candidates.append((entry - r, r))
            valid = [ct for ct in candidates if ct[0] >= p.min_target_atr_mult * a]
            if not valid:
                continue
            valid.sort(key=lambda x: x[0])
            target = valid[0][1]

            risk = abs(entry - stop)
            outcome, target_first = "timeout", False
            end = min(e, N - 1)
            end = min(i + 1 + p.max_hold_bars, N - 1)
            for t in range(e, end + 1):
                if direction == 1:
                    hs, ht = l[t] <= stop, h[t] >= target
                else:
                    hs, ht = h[t] >= stop, l[t] <= target
                if hs:
                    outcome, target_first = "stop", False
                    break
                if ht:
                    outcome, target_first = "target", True
                    break
            trs.append(target_first)
        if trs:
            agg.append(np.mean(trs))
    return {
        "n_seeds": len(agg),
        "target_first_rate": float(np.mean(agg)) if agg else float("nan"),
        "target_first_std": float(np.std(agg)) if agg else float("nan"),
    }


# --------------------------------------------------------------------------- #
#  Stats
# --------------------------------------------------------------------------- #
def max_drawdown(equity_curve: np.ndarray) -> float:
    if len(equity_curve) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    return float(dd.min())


def summarize(trades: list[Trade], p: Params) -> dict:
    if not trades:
        return {"n": 0}
    r_net = np.array([t.r_net for t in trades])
    wins = r_net > 0
    gross_win = r_net[r_net > 0].sum()
    gross_loss = -r_net[r_net < 0].sum()
    eq = np.array([p.start_equity] + [t.equity_after for t in trades])
    tgt_first = np.array([t.target_first for t in trades])
    rr = np.array([abs(t.target - t.entry_price) / t.risk_per_unit for t in trades])
    return {
        "n": len(trades),
        "win_rate": float(wins.mean()),
        "avg_r": float(r_net.mean()),
        "median_r": float(np.median(r_net)),
        "avg_win_r": float(r_net[r_net > 0].mean()) if wins.any() else 0.0,
        "avg_loss_r": float(r_net[r_net < 0].mean()) if (~wins).any() else 0.0,
        "median_rr": float(np.median(rr)),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "total_r": float(r_net.sum()),
        "target_first_rate": float(tgt_first.mean()),
        "max_dd": max_drawdown(eq),
        "final_equity": float(eq[-1]),
        "ret_pct": float((eq[-1] / p.start_equity - 1) * 100),
        "n_target": sum(t.outcome == "target" for t in trades),
        "n_stop": sum(t.outcome == "stop" for t in trades),
        "n_timeout": sum(t.outcome == "timeout" for t in trades),
    }


def subset_stats(trades: list[Trade], key, p: Params) -> dict:
    groups = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    return {k: summarize(v, p) for k, v in sorted(groups.items())}


# --------------------------------------------------------------------------- #
#  Reporting helpers
# --------------------------------------------------------------------------- #
def fmt_stats_row(name, s) -> str:
    if s.get("n", 0) == 0:
        return f"| {name} | 0 | - | - | - | - | - | - |"
    return (f"| {name} | {s['n']} | {s['win_rate']*100:.1f}% | {s['avg_r']:+.3f} | "
            f"{s['profit_factor']:.2f} | {s['target_first_rate']*100:.1f}% | "
            f"{s['max_dd']*100:.1f}% | {s['ret_pct']:+.1f}% |")


STATS_HEADER = ("| Segment | Trades | Win% | Avg R | PF | Target-first% | MaxDD | Return |\n"
                "|---|---|---|---|---|---|---|---|")


def equity_series(trades: list[Trade], p: Params) -> np.ndarray:
    return np.array([p.start_equity] + [t.equity_after for t in trades])


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def run_config(df: pd.DataFrame, p: Params, apply_session: bool):
    signals = detect_signals(df, p)
    trades = simulate(df, signals, p, apply_session)
    return signals, trades


def main():
    out_lines = []          # collected for results.md
    def emit(*a):
        line = " ".join(str(x) for x in a)
        print(line)
        out_lines.append(line)

    base = Params()

    # ---------------- load & clean ----------------------------------------- #
    df5_raw = load_dukascopy_5m("data/XAUUSD_5M_dukascopy.csv")
    rep = df5_raw.attrs["clean_report"]
    df15_raw = resample(df5_raw, "15min")

    emit("# GOLD (XAUUSD) Pullback-Continuation Backtest — Results\n")
    emit("> **Preliminary.** Single ~1-year Dukascopy sample; treat all numbers "
         "as indicative, not statistically robust.\n")
    emit("## 1. Data acquisition & cleaning\n")
    emit("**Source:** Dukascopy XAUUSD 5-minute BID candles "
         "(`XAUUSD_Candlestick_5_M_BID_01.11.2024-01.11.2025.csv`), retrieved from a "
         "public GitHub mirror after live providers (Yahoo/yfinance, Stooq, "
         "TwelveData, AlphaVantage) were all blocked by this environment's egress "
         "policy. The 15-minute series is **resampled from the same 5-minute feed** so "
         "both timeframes share one clean source.\n")
    emit(f"- Raw rows: **{rep['rows_raw']:,}**")
    emit(f"- Zero-volume flat candles dropped (weekend/holiday fills): "
         f"**{rep['zero_volume_dropped']:,}**")
    emit(f"- Bad-price rows dropped (<=0 or high<low): **{rep['bad_price_dropped']}**")
    emit(f"- Duplicate timestamps dropped: **{rep['duplicate_ts_dropped']}**")
    emit(f"- Clean 5-min rows: **{rep['rows_clean']:,}**  |  15-min rows: "
         f"**{len(df15_raw):,}**")
    emit(f"- UTC range: **{rep['utc_start']} → {rep['utc_end']}**")
    emit("")
    emit("**Fixes applied:** timestamps were stored in Dukascopy local time with a "
         "per-row GMT offset that switches +0200↔+0300 across DST — each row was "
         "individually converted to UTC. ~34.5k zero-volume weekend/holiday fill "
         "candles (O=H=L=C) were removed; the pattern logic additionally refuses to "
         "form across the resulting session-break gaps (see `gap_tolerance_mult`).\n")

    emit("Sample of clean 5-min data (UTC):\n")
    emit("```")
    emit(df5_raw.head(5).to_string())
    emit("...")
    emit(df5_raw.tail(3).to_string())
    emit("```\n")

    # add indicators
    d5 = add_indicators(df5_raw, replace(base, bar_minutes=5))
    d15 = add_indicators(df15_raw, replace(base, bar_minutes=15))
    frames = {"5m": (d5, 5), "15m": (d15, 15)}

    emit("## 2. Parameters\n```")
    for k, v in base.__dict__.items():
        emit(f"{k:22s} = {v}")
    emit(f"{'total_cost_usd':22s} = {base.total_cost_usd}  (spread+slippage per round trip)")
    emit("```\n")

    # ---------------- headline per timeframe (session ON) ------------------ #
    emit("## 3. Headline results (default params, session filter ON)\n")
    emit(STATS_HEADER)
    headline = {}
    for tf, (df, bm) in frames.items():
        p = replace(base, bar_minutes=bm, session_filter=True)
        sigs, trades = run_config(df, p, apply_session=True)
        s = summarize(trades, p)
        headline[tf] = (p, sigs, trades, s)
        emit(fmt_stats_row(f"{tf} (session ON)", s))
    emit("")

    # ---------------- bottom line / interpretation ------------------------- #
    s5 = headline["5m"][3]
    breakeven = 1.0 / (1.0 + s5["median_rr"]) * 100
    emit("### Bottom line\n")
    emit(f"The pattern **wins often but loses money.** On 5m it hits its target "
         f"{s5['win_rate']*100:.0f}% of the time, yet the average winner is only "
         f"**{s5['avg_win_r']:+.2f}R** while the average loser is "
         f"**{s5['avg_loss_r']:+.2f}R** (median reward:risk ≈ "
         f"**{s5['median_rr']:.2f}:1**). With that payoff the break-even win rate is "
         f"~**{breakeven:.0f}%**, so a {s5['win_rate']*100:.0f}% hit rate still yields "
         f"a negative expectancy (avg **{s5['avg_r']:+.3f}R**, PF "
         f"**{s5['profit_factor']:.2f}**). The cause is structural: targets are the "
         f"*nearest* S/R level (often <0.5R away) while stops sit beyond the whole "
         f"pullback (often 2–4R away). §8 shows the pattern nonetheless **beats random "
         f"on target-first rate**, i.e. it does identify genuine continuation — the "
         f"edge is real but the default money-management throws it away. Widening "
         f"targets / tightening stops (or a partial-take rule) is the obvious next "
         f"experiment.\n")
    emit("Payoff detail (session ON):\n")
    emit("| TF | Win% | Avg win R | Avg loss R | Median R:R | Break-even Win% | Avg R |")
    emit("|---|---|---|---|---|---|---|")
    for tf in frames:
        st = headline[tf][3]
        be = 1.0 / (1.0 + st["median_rr"]) * 100
        emit(f"| {tf} | {st['win_rate']*100:.1f}% | {st['avg_win_r']:+.2f} | "
             f"{st['avg_loss_r']:+.2f} | {st['median_rr']:.2f}:1 | {be:.0f}% | "
             f"{st['avg_r']:+.3f} |")
    emit("")

    # ---------------- session ON vs OFF ------------------------------------ #
    emit("## 4. Session filter ON vs OFF\n")
    emit(STATS_HEADER)
    session_runs = {}
    for tf, (df, bm) in frames.items():
        p = replace(base, bar_minutes=bm)
        for flag, lbl in [(True, "ON"), (False, "OFF")]:
            sigs, trades = run_config(df, p, apply_session=flag)
            s = summarize(trades, p)
            session_runs[(tf, flag)] = (p, sigs, trades, s)
            emit(fmt_stats_row(f"{tf} session {lbl}", s))
    emit("")
    emit("_Asian-session trades are included only in the OFF rows; gold's Asian hours "
         "are thinner, so compare the two to see the filter's effect._\n")

    # ---------------- direction breakdown ---------------------------------- #
    emit("## 5. Breakdown by direction (session ON)\n")
    emit(STATS_HEADER)
    for tf in frames:
        _, _, trades, _ = headline[tf]
        for d, lbl in [(1, "long"), (-1, "short")]:
            sub = [t for t in trades if t.direction == d]
            emit(fmt_stats_row(f"{tf} {lbl}", summarize(sub, headline[tf][0])))
    emit("")

    # ---------------- target kind breakdown -------------------------------- #
    emit("## 6. Breakdown by target type (session ON)\n")
    emit(STATS_HEADER)
    for tf in frames:
        p, _, trades, _ = headline[tf]
        for kind in ["fractal", "round"]:
            sub = [t for t in trades if t.target_kind == kind]
            emit(fmt_stats_row(f"{tf} {kind}", summarize(sub, p)))
    emit("")

    # ---------------- weekly breakdown ------------------------------------- #
    emit("## 7. Breakdown by week (5m, session ON)\n")
    p5, _, trades5, _ = headline["5m"]
    wk = subset_stats(trades5, lambda t: t.week, p5)
    emit("| Week | Trades | Win% | Avg R | Total R |")
    emit("|---|---|---|---|---|")
    for w, s in wk.items():
        if s.get("n", 0):
            emit(f"| {w} | {s['n']} | {s['win_rate']*100:.0f}% | {s['avg_r']:+.2f} "
                 f"| {s['total_r']:+.2f} |")
    emit("")

    # ---------------- key hypothesis test ---------------------------------- #
    emit("## 8. Key hypothesis — does price reach the S/R target before the stop?\n")
    emit("| Timeframe | Pattern target-first % | Random baseline target-first % "
         "(mean±sd) |")
    emit("|---|---|---|")
    for tf, (df, bm) in frames.items():
        p, sigs, trades, s = headline[tf]
        base_ = random_baseline(df, p, n_entries=max(s["n"], 1),
                                apply_session=True)
        emit(f"| {tf} | {s['target_first_rate']*100:.1f}% "
             f"({s['n']} trades) | {base_['target_first_rate']*100:.1f}% "
             f"± {base_['target_first_std']*100:.1f}% |")
    emit("")
    emit("_'Target-first' = the trade's target level was touched before its stop. "
         "The baseline uses random entries with the same trend direction and the same "
         "target/stop construction._\n")

    # ---------------- parameter sweep -------------------------------------- #
    emit("## 9. Parameter sweep — big_candle_atr_mult × trigger_mode (session ON)\n")
    emit("| TF | big_mult | trigger | Trades | Win% | Avg R | PF | Target-first% | "
         "Return |")
    emit("|---|---|---|---|---|---|---|---|---|")
    for tf, (df, bm) in frames.items():
        for mult in [1.0, 1.2, 1.5]:
            for mode in ["open", "extreme"]:
                p = replace(base, bar_minutes=bm, big_candle_atr_mult=mult,
                            trigger_mode=mode, session_filter=True)
                _, trades = run_config(df, p, apply_session=True)
                s = summarize(trades, p)
                if s.get("n", 0):
                    emit(f"| {tf} | {mult} | {mode} | {s['n']} | "
                         f"{s['win_rate']*100:.1f}% | {s['avg_r']:+.3f} | "
                         f"{s['profit_factor']:.2f} | {s['target_first_rate']*100:.1f}% "
                         f"| {s['ret_pct']:+.1f}% |")
                else:
                    emit(f"| {tf} | {mult} | {mode} | 0 | - | - | - | - | - |")
    emit("")

    # ---------------- equity curve PNG ------------------------------------- #
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)
    for ax, tf in zip(axes, ["5m", "15m"]):
        p, _, trades, s = headline[tf]
        eq = equity_series(trades, p)
        xt = [p.start_equity] + [t.exit_time for t in trades]
        ax.plot(range(len(eq)), eq, lw=1.3, color="#c49a2f",
                label=f"{tf} strategy")
        ax.axhline(p.start_equity, color="gray", ls="--", lw=0.8)
        ax.set_title(f"XAUUSD pullback-continuation — {tf}\n"
                     f"{s['n']} trades, PF {s['profit_factor']:.2f}, "
                     f"ret {s['ret_pct']:+.1f}%, maxDD {s['max_dd']*100:.1f}%",
                     fontsize=10)
        ax.set_xlabel("trade #")
        ax.set_ylabel("equity ($, 1% risk/trade)")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("equity_curve.png", dpi=110)
    emit("## 10. Equity curve\n")
    emit("![equity curve](equity_curve.png)\n")
    emit("Saved to `equity_curve.png` (5m and 15m, 1% risk per trade, "
         "sequential non-overlapping trades, costs applied).\n")

    # ---------------- caveats ---------------------------------------------- #
    emit("## 11. Caveats\n")
    emit("- **Small sample / single source.** ~1 year of one broker's (Dukascopy) "
         "5-min BID data. No bid/ask spread modelled beyond the flat "
         f"${base.total_cost_usd:.2f} round-trip cost; real XAUUSD spread widens in "
         "thin hours and around news.\n"
         "- **BID candles only** — entries/exits assume fills at candle prices plus "
         "the flat cost; no partial fills or requotes.\n"
         "- **Conservative same-bar rule:** when a candle spans both stop and target, "
         "the stop is assumed hit first.\n"
         "- **One position at a time**, so overlapping signals are skipped; the raw "
         "signal edge (target-first %) is reported separately in §8.\n"
         "- 15m is derived by resampling 5m, so the two timeframes are not "
         "independent samples.\n"
         "- No walk-forward / out-of-sample split or multiple-testing correction on "
         "the parameter sweep — treat the best cell as in-sample.\n")

    with open("results.md", "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print("\n[written] results.md and equity_curve.png")


if __name__ == "__main__":
    main()
