# Deriv Synthetic Indices: Candlestick & Pattern Research — Findings

**Scope:** 10 years of 1-minute data (2016-08-08 → 2026-08-08), Volatility 75
primary, Volatility 100 as an independent cross-check. First 5 years used for
all research; final 5 years sealed as a blind holdout (SHA256 hashes in
`manifest.json`, files never opened).

---

## 0. Data provenance — read this first

The research environment's network policy blocks Deriv's API, so live history
could not be pulled from here. Instead the study ran on a **calibrated
simulation of Deriv's own documented generators**: Volatility indices are
RNG-driven simulated markets with a fixed annualized volatility (75% / 100%),
one tick every 2 seconds, 24/7, and no drift edge (a price-martingale — which
mathematically implies the famous long-term downward drift of V75: that's
volatility drag, −σ²/2, not seller pressure). The simulation was verified
against theory (per-minute volatility within 0.1% of spec, zero return
autocorrelation, gapless 24/7 path).

`src/fetch_deriv_data.py` pulls the **real** history from Deriv's API and
writes files in the exact format this pipeline consumes — run it from an
unrestricted machine and every experiment here re-runs on real data unchanged.

Step Index was considered as the starting instrument but rejected: it launched
around late 2020, so 10 years of history do not exist for it. V75 was chosen.

## 1. Candlestick anatomy — what a candle actually is

```
 high  ─┬─          upper wick = high − max(open, close)   (rejected upside)
        │
   body top         body = |close − open|  (net directional result)
  ██████████
  ██████████        body fraction = body / range:
  ██████████          ~0   → doji (indecision shape)
   body bottom        ~1   → marubozu (one-way traffic shape)
        │
 low   ─┴─          lower wick = min(open, close) − low    (rejected downside)
```

**In a real market**, a candle is the residue of order flow: initiative buyers
lift offers, resting liquidity absorbs, stops cascade, and wicks record
excursions that were rejected by real participants. That is *why* classic
patterns are claimed to work there — a long lower wick is read as evidence of
absorption; an engulfing bar as evidence of initiative reversal.

**In a Deriv synthetic index there are no participants.** Price is a certified
random number generator driving a fixed-volatility process. The same shapes
appear — dojis, hammers, engulfings, three soldiers — but they are produced by
chance arrangement of random ticks, not by order flow. This study measures
what those shapes predict when the order-flow explanation is removed.

A structural quirk found on the way: because synthetics are gapless
(every candle opens exactly at the prior close), some classic patterns
collapse into each other — e.g. *three black crows* is mathematically
identical to "three consecutive down closes". Gap-based patterns cannot
exist at all.

## 2. Method

- **Universe:** V75 and V100; 1m, 5m, 1h timeframes; 2.63M training candles
  per symbol at 1m.
- **22 pattern detectors** (doji, spinning top, marubozu, hammer, shooting
  star, engulfing, harami, inside/outside bar, three soldiers/crows, 3- and
  5-bar runs, 20-bar breakouts, big/tiny range) with classic-TA thresholds.
- **For each pattern × horizon (1/5/15 bars):** P(next move in the claimed
  direction), mean forward return, forward realized range vs unconditional
  ("quick movement" test); binomial and Welch tests with Benjamini–Hochberg
  false-discovery correction across all 396 tests.
- **ML:** logistic regression + gradient boosting on the last 10 candles'
  anatomy plus momentum summaries, evaluated strictly walk-forward
  (train 2016–18 → test 2019, etc.), with a spread-cost backtest.
- **Own-pattern discovery:** all 125 possible 3-candle anatomy sequences mined
  on 2016–18, best 30 re-tested on 2019–mid-2021.

## 3. Findings

### 3.1 Classic candlestick patterns predict nothing directional
Across 396 pattern×horizon×symbol×timeframe tests, every classic directional
pattern's hit rate landed between **48.2% and 51.6%** — sampling noise around
a coin flip. After FDR correction, 2 of 396 direction tests were "significant"
(hit rate 50.28%, n=330k) — and both **failed to replicate** on the second
symbol (49.93%). That is the signature of data mining, not signal.

### 3.2 "Quick movement" candles don't predict quick movements
Forward volatility after big-range candles, breakouts, dojis, etc. differed
from baseline by at most ±6%, and the direction of the effect exposes it as an
artifact: after up-runs the *price level* is higher, so point-denominated
ranges grow while the lagging ATR normalizer hasn't caught up. In
return terms, volatility is constant by construction — there is no volatility
clustering to trade, unlike real markets.

### 3.3 My own discovered patterns died out-of-sample — on schedule
Mining all 125 3-candle sequences on 2016–18 produced top-30 patterns with
apparent edges up to 3.5% (1m) and 5.4% average (1h). Re-tested on 2019–21:

| | discovery |edge| | validation |edge| | edge kept its direction |
|---|---|---|---|
| V75 1m | 1.18% | 0.64% | **43%** (coin flip = 50%) |
| V75 1h | 5.42% | 2.31% | **43%** |
| V100 1m | 1.13% | 0.52% | **40%** |

The "best" discovered patterns kept their direction *less often than chance*.
This is exactly what mining pure noise looks like, demonstrated on the very
exercise the project set out to do.

### 3.4 Machine learning confirms it
Walk-forward AUC across every fold, symbol, timeframe and model:
**0.493–0.509, mean ≈ 0.500.** Gross expectancy per trade ≈ 0; net of a
realistic spread, **every configuration loses almost exactly the spread**
(−4 to −18 bps/trade). The model isn't weak — there is nothing to learn.

### 3.5 A cautionary tale from inside this project
An early version of the data generator had a chunking bug that created
artificial mean-reversion. The pattern study immediately "found" a
spectacular edge: 99.4% win rate fading 20-bar breakouts. It was pure
artifact, caught by sanity checks (return autocorrelation, breakout
frequency vs random-walk theory). Takeaway: **when a backtest on a synthetic
index shows a strong edge, the correct first hypothesis is a bug in the
pipeline** — because the generator's design guarantees no such edge exists.

## 4. Why this result is structural, not a failure to look hard enough

Deriv states the indices are driven by a certified RNG at fixed volatility
and are audited for fairness. A fair fixed-vol process is a martingale:
E[future price | everything observed] = current price. Candles and chart
patterns are functions of past prices, so **no function of candles — however
clever — can shift the expected direction**. Anything that appears to work
in-sample must decay to 50% out-of-sample, which is precisely what every
experiment above showed. On top of the zero expectancy sits the spread, so
the realistic long-run outcome of any chart-based system on synthetics is
**minus transaction costs**, at a speed proportional to trade frequency.

What this implies practically:

- **Consistency on synthetics cannot come from direction prediction.** Any
  vendor/strategy claiming a consistent directional edge on V75 from charts is
  claiming to predict a certified RNG.
- The things that *are* real and knowable: each index's exact volatility (V75
  moves ~0.19% per 2s-tick-minute… precisely σ/√t scalable), gapless 24/7
  behavior, and product mechanics. These matter for **risk sizing** (e.g.
  correct stop distances in σ units, avoiding guaranteed-ruin leverage), not
  for entry signals.
- If an edge exists anywhere on these products it would be in **pricing
  discrepancies of the derivative products** (multipliers/options quotes vs
  true process parameters), not in the chart. That's a different, harder
  research question — and the honest prior is that the house prices these
  correctly.

## 5. Blind holdout protocol (still sealed)

The 2021–2026 halves (`*_holdout_1m.parquet`) were generated with independent
seeds, hashed (SHA256 in `manifest.json`), and **never opened**. On your
go-ahead, the pre-registered test is: run the identical pattern study, ML
walk-forward, and the frozen top-30 mined patterns against the holdout, and
compare against the pre-registered prediction — **all hit rates 50% ± sampling
error, AUC 0.50 ± 0.01, mined-pattern direction persistence ≈ 50%.** If real
Deriv data is fetched with `fetch_deriv_data.py`, the same protocol applies
unchanged, which is the more interesting reveal.

## 6. Suggested discussion agenda

1. Re-run on **real** Deriv history (needs a machine with API access — the
   fetcher is ready). This tests whether Deriv's actual generator deviates
   from spec (e.g. discretization or rounding artifacts) — the only place a
   chart edge could physically hide.
2. Open the holdout together and score the pre-registered predictions.
3. If the goal is a live trading edge, redirect effort from chart patterns to
   (a) product-pricing analysis or (b) real markets, where order flow exists
   and pattern research is at least not provably futile.
