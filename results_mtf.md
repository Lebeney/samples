# Simple 1m engulfing-continuation + 5m/15m confirmation — tested

Your exact rule, mechanical: on 1m, candle A (against) → candle B **engulfs** it (with) →
candle C (with) ⇒ enter on the next candle, **only if the last completed 5m and 15m
candles both point the same way**. One position, fixed risk, target = 2R, costs on, no
lookahead. Run on the synthetic indices (built from one tick stream so 1m/5m/15m are
consistent). Live third-party feeds are blocked in this environment, so this is simulated —
but the synthetics *are* the instruments you trade.

| Instrument | Signals | Win% | Avg R | PF | Verdict |
|---|---|---|---|---|---|
| Step | 3398 | 33.9% | −0.335 | 0.63 | **loses** |
| Volatility 75 | 3902 | 34.6% | −0.086 | 0.88 | loses |
| Volatility 100 | 3899 | 34.6% | −0.055 | 0.92 | loses |
| Boom 1000 | 1175 | 93.1% | +0.46 | 1.38 | **see caveat** |
| Crash 1000 | 1158 | 91.6% | +0.11 | 1.07 | see caveat |

**Step and the Volatility indices lose.** They're memoryless random walks — the engulfing
pattern and the 5m/15m "confirmation" carry no information, so it's a coin flip minus cost.
Same conclusion as everything before.

## Boom/Crash look like a 90%-win goldmine — it's an artifact, and it's the exact trap that blew up your $8

Boom/Crash post 90%+ win rates because they **drift slowly one way and spike hard the
other**: you collect lots of small 2R drift-wins, and the rare spike goes *against* you.
Whether that's a strategy or a disaster depends entirely on **how a spike fills your stop** —
and a spike gaps straight through it:

| How a spike fills your stop | Boom avg R | Crash avg R |
|---|---|---|
| Ignore the gap (the naive backtest) | **+1.61** | **+1.53** |
| Fill halfway through the stop | +0.86 | +0.37 |
| Fill at the spike's extreme (realistic) | **+0.10** | **−0.80** |

The entire "edge" lives in that assumption. Model the spike honestly and it's **≈0 or
negative** — which is what the math demands, because a drift-free process can't be beaten by
any stop/target. The 90% win rate is not an edge; it's the signature of a strategy that wins
small over and over and then gives it **all** back (plus more) on one spike.

And that is precisely your Step Index sequence: you were on the ~16% lucky side of exactly
this shape. With the **50% layering and no stop**, there's nothing for the spike to gap
through — it hits the whole stacked position at once.

## Bottom line

- **No edge on any of these** — Step/Vol lose outright; Boom/Crash's 90% win rate is a
  spike-fill mirage that vanishes once the gap-through is modeled.
- The high win rate is the danger, not the attraction: **many small wins, one spike takes
  the account.** No amount of 1m/5m/15m confirmation changes that, because the confirmation
  has nothing real to confirm on an RNG feed.

## Reproduce

```
python3 mtf_engulf.py   # main table + the spike-fill sensitivity that exposes the artifact
```
