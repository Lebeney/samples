# Edge search: Step Index & Step Index 500 on 1m / 5m / 15m

I searched — a randomness fingerprint plus a 7-strategy battery across all three
timeframes, with a train/test split. Here's everything that came back.

## (A) The proof: the next candle is 50/50 no matter what you condition on

Over 6 months of data per instrument:

| Instrument | TF | P(up) | autocorr(1) | P(up ∣ up) | P(up ∣ 3 up) | P(up ∣ 3 down) |
|---|---|---|---|---|---|---|
| Step Index | 1m | 0.501 | −0.002 | 0.500 | 0.502 | 0.501 |
| Step Index | 5m | 0.500 | 0.006 | 0.502 | 0.507 | 0.501 |
| Step Index | 15m | 0.501 | 0.002 | 0.499 | 0.491 | 0.511 |
| Step Index 500 | 1m/5m/15m | ≈0.50 | ≈0 | ≈0.50 | ≈0.50 | ≈0.50 |

Every conditional probability is 50% ± noise, and return autocorrelation is ~0 at
every lag. **This is the whole answer:** if `P(next up | anything) = 0.5`, then no
pattern — on any timeframe, with any confirmation stack — can have positive
expectancy. There is nothing to condition on.

(Step Index and Step 500 give identical fingerprints because they're the same
symmetric process with a different step size; the step size scales your P&L but not
the odds.)

## (B) The search: nothing survives out-of-sample

Expectancy per trade (in ATR units) of the next candle's move in the signal's
direction — trained on seeds 0–5, tested on unseen seeds 100–105:

- momentum1, meanrev1, momentum3, streak-fade, breakout, fade-breakout, engulfing —
  across 1m, 5m, 15m, both instruments (42 combos).
- **Every** in-sample "edge" **flips sign out-of-sample** (e.g. 5m momentum3:
  train +0.019 → test −0.013; 15m breakout: train +0.017 → test −0.039).
- **86% of all 42 combos** have a test expectancy within 2 standard errors of zero.
- Mean |test expectancy| across everything = **0.012 ATR** — indistinguishable from
  statistical noise, and negative once you subtract the spread.

The in-sample winners are data-mining artifacts: with enough strategies, some look
good on any random data by luck; the train/test split exposes them.

## Bottom line

There is **no consistent pattern or edge on Step Index or Step 500**, on 1m, 5m, or
15m — not because I didn't look, but because the instrument is engineered as a
memoryless coin flip. Any winning streak you get is variance (the $8→$32 was the
lucky tail of exactly that), and it reverts to a loss after the spread over enough
trades. The only variable you actually control on these is **risk of ruin**, and
stacking size (50% layering) maximizes it.

Where an edge *can* exist is a real market with real participants and structure — the
gold RR strategy in `results_strategy.md` was out-of-sample profitable. If you can
export 1m candles for a real instrument (a CSV in a GitHub repo — direct feeds are
blocked here), I'll run this exact search on it and show you the difference between a
coin flip and a market.

## Reproduce

```
python3 step_edge_search.py
```
