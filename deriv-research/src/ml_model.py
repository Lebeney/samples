"""ML direction model on candlestick anatomy, evaluated walk-forward.

Features per bar: the last LOOKBACK bars' normalized anatomy (body fraction,
wick fractions, direction, ATR-relative range, ATR-normalized return) plus
rolling momentum/mean-reversion summaries. Target: next bar closes up.

Evaluation is strictly walk-forward INSIDE the 5-year training half
(the last 5 years stay sealed): expanding-window yearly folds --
train on years 1..k, test on year k+1, for k = 2, 3, 4.

Also reports a toy backtest: trade the predicted direction each bar when
the model is confident, minus a Deriv-realistic spread.
"""

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from candlestick_features import add_anatomy

LOOKBACK = 10
BASE_COLS = ["body_frac", "uw_frac", "lw_frac", "dir", "range_atr"]


def build_dataset(df):
    df = add_anatomy(df)
    df["nret"] = df["ret"] / (df["atr"] / df["close"] + 1e-12)  # ATR-normalized return
    feats = {}
    for lag in range(LOOKBACK):
        for col in BASE_COLS + ["nret"]:
            feats[f"{col}_l{lag}"] = df[col].shift(lag)
    feats["mom_5"] = df["nret"].rolling(5).sum()
    feats["mom_20"] = df["nret"].rolling(20).sum()
    feats["updown_ratio_20"] = (df["ret"] > 0).rolling(20).mean()
    feats["close_pos"] = df["close_pos"]
    X = pd.DataFrame(feats, index=df.index)
    y = (df["close"].shift(-1) > df["close"]).astype(int)
    fwd_ret = np.log(df["close"].shift(-1) / df["close"])
    keep = X.notna().all(axis=1) & df["atr"].notna() & fwd_ret.notna()
    return (X[keep], y[keep], fwd_ret[keep], df.loc[keep, "epoch"],
            df.loc[keep, ["close", "atr"]])


def yearly_folds(epoch):
    year = pd.to_datetime(epoch, unit="s").dt.year
    years = sorted(year.unique())
    for k in range(2, len(years) - 1 + 1):
        train_years, test_year = years[:k], years[k]
        yield (year.isin(train_years).to_numpy(), (year == test_year).to_numpy(),
               f"train{train_years[0]}-{train_years[-1]}_test{test_year}")


def run(df, symbol, timeframe, spread_frac_of_atr=0.10):
    X, y, fwd_ret, epoch, px = build_dataset(df)
    Xv, yv, fr = X.to_numpy(), y.to_numpy(), fwd_ret.to_numpy()
    rows = []
    for tr, te, tag in yearly_folds(epoch):
        models = {
            "logistic": LogisticRegression(max_iter=1000),
            "gbm": HistGradientBoostingClassifier(max_iter=200, max_depth=6,
                                                  random_state=0),
        }
        for name, model in models.items():
            model.fit(Xv[tr], yv[tr])
            proba = model.predict_proba(Xv[te])[:, 1]
            auc = roc_auc_score(yv[te], proba)
            acc = ((proba > 0.5) == yv[te]).mean()
            # confident-only toy backtest, cost = spread as fraction of ATR
            conf = np.abs(proba - 0.5) > 0.02
            side = np.where(proba > 0.5, 1.0, -1.0)
            cost = spread_frac_of_atr * (px["atr"].to_numpy()[te] /
                                         px["close"].to_numpy()[te])
            pnl = np.where(conf, side * fr[te] - cost, 0.0)
            n_tr = int(conf.sum())
            rows.append({
                "symbol": symbol, "timeframe": timeframe, "fold": tag,
                "model": name, "n_test": int(te.sum()),
                "auc": round(auc, 5), "accuracy": round(acc, 5),
                "trades": n_tr,
                "gross_bps_per_trade": round(float(
                    np.where(conf, side * fr[te], 0.0).sum() / max(n_tr, 1)) * 1e4, 4),
                "net_bps_per_trade": round(float(pnl.sum() / max(n_tr, 1)) * 1e4, 4),
            })
            print(rows[-1])
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--symbols", nargs="+", default=["V75", "V100"])
    ap.add_argument("--timeframes", nargs="+", default=["5m", "1h"])
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    all_rows = []
    for sym in args.symbols:
        for tf in args.timeframes:
            df = pd.read_parquet(os.path.join(args.datadir, f"{sym}_train_{tf}.parquet"))
            all_rows.append(run(df, sym, tf))
    out = pd.concat(all_rows, ignore_index=True)
    path = os.path.join(args.outdir, "ml_walkforward.csv")
    out.to_csv(path, index=False)
    print(f"\nwrote {path}")
    print("\n== Summary: mean test AUC by symbol/timeframe/model ==")
    print(out.groupby(["symbol", "timeframe", "model"])[["auc", "accuracy",
          "net_bps_per_trade"]].mean().round(4).to_string())


if __name__ == "__main__":
    main()
