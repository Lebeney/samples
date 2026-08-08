# Deriv Synthetic Index Research

Candlestick / chart-pattern / ML study on 10 years of Deriv-style synthetic
index data (V75, V100): first 5 years for research, last 5 sealed as a blind
holdout. Full write-up: [report/FINDINGS.md](report/FINDINGS.md).

## Layout

```
src/generate_synthetic.py    seeded generator calibrated to Deriv's documented specs
src/fetch_deriv_data.py      fetch REAL history from the Deriv API (run off-sandbox)
src/sanity_check.py          validates data against generator theory
src/candlestick_features.py  candle anatomy + 22 pattern detectors
src/pattern_study.py         pattern -> forward outcome statistics (FDR-corrected)
src/ml_model.py              walk-forward ML direction models + cost-aware backtest
src/mine_patterns.py         exhaustive 3-candle pattern discovery + decay test
results/                     output tables (CSV)
report/FINDINGS.md           findings and discussion
```

## Reproduce

```bash
pip install pandas numpy scipy scikit-learn pyarrow websocket-client
python src/generate_synthetic.py --outdir data       # or fetch_deriv_data.py for real data
python src/sanity_check.py --datadir data
python src/pattern_study.py --datadir data --outdir results --split train
python src/ml_model.py --datadir data --outdir results
python src/mine_patterns.py --datadir data --outdir results --symbol V75 --timeframe 1m
```

The holdout files (`*_holdout_*.parquet`) are sealed: SHA256 hashes are
recorded in the data directory's `manifest.json` and nothing reads them until
the pre-registered reveal described in the report.
