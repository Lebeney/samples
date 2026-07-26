# Insight Detection & Forecasting for Personal Finance — Research Brief (as of 2026-07-26)

## 1. Anomaly detection for short, noisy, seasonal spend series

**PARTIAL.** No published head-to-head of MAD/robust-z vs changepoint vs STL specifically on *individual* spending series was found; the evidence is from adjacent domains (ops metrics, business KPIs):

- Twitter's **Seasonal Hybrid ESD (S-H-ESD)** (Hochenbaum, Vallis, Kejariwal, arXiv:1704.07706, Apr 2017 — https://arxiv.org/abs/1704.07706) combines STL-style decomposition with **median/MAD-based robust ESD tests**, explicitly because mean/SD z-scores break down when anomalies contaminate short seasonal windows. This is the closest canonical "robust stats + decomposition beats plain z-score" result. VERIFIED that the method exists and is the de-facto baseline; precision figures are for cloud metrics, not spending.
- **RobustSTL** (Alibaba, arXiv:1812.01767, Dec 2018 — https://arxiv.org/abs/1812.01767) and "Anomaly Detection on Seasonal Metrics via Robust Time Series Decomposition" (arXiv:2008.09245, Aug 2020 — https://arxiv.org/abs/2008.09245) show classic STL is fragile to outliers and abrupt trend changes — exactly the failure mode of personal-spend series — and fix it with LAD/ℓ1-regularized decomposition. **StructuralDecompose** (arXiv:2510.04974, Oct 2025 — https://arxiv.org/abs/2510.04974) packages changepoint-aware robust decomposition in R.
- Practitioner guidance (CleverTap tech blog, "Anomaly Detection for Time Series Data, Part 2" — https://tech.clevertap.com/anomaly-detection-for-time-series-data-part-2/; TigerData guide — https://www.tigerdata.com/learn/time-series-anomaly-detection-methods-sql-real-time-implementation, accessed 2026-07-26) converges on: **MAD-based robust z for high-contamination series; STL-residual thresholding when seasonality is strong**.
- Fintech engineering blogs: **PARTIAL.** Monzo publishes on ML for transactions but framed as fraud/scam detection, not consumer spend-insight anomalies (InfoQ on Monzo's real-time fraud architecture, Nov 2025 — https://www.infoq.com/news/2025/11/monzo-real-time-fraud-detection/; "Machine Learning at Monzo in 2025" — https://monzo.com/blog/machine-learning-at-monzo-in-2025). Mint documented *that* it alerted on "unusual spending" but never published the algorithm (https://mint.intuit.com/how-mint-works/alerts, archived product page). Cleo: **NOT FOUND** (no engineering write-up located). No bank has published spend-insight anomaly precision.

## 2. Acceptable false-positive rates in consumer fintech alerts

**NOT FOUND (fintech-specific precision thresholds); PARTIAL (general industry data).** No published study states "insight alerts must be ≥X% precise." Proxies:

- Braze: ~**60% of iOS and 40% of Android users opt out** of push overall ("Don't Push Me" — https://www.braze.com/resources/articles/opt-out-of-push-notifications-why-users-do-it, accessed 2026-07-26); an older Localytics/andrewchen figure also puts opt-out near 60% driven by irrelevant alerts (https://andrewchen.com/why-people-are-turning-off-push/).
- Airship 2025 benchmarks: **finance apps have the highest opt-in (~72%)** of any vertical — users *want* money alerts, raising the cost of squandering that trust (https://www.airship.com/resources/benchmark-report/mobile-app-push-notification-benchmarks-for-2025/).

## 3. Individual cashflow forecasting

**PARTIAL.** Consumer-grade published accuracy is thin; most "cashflow forecasting" literature is corporate treasury (e.g., ION, GTreasury claiming 10–30% error reduction — marketing, not peer-reviewed).

- The most on-point academic work: **"Financial Forecasting and Analysis for Low-Wage Workers"** (arXiv:1806.05362, Jun 2018 — https://arxiv.org/abs/1806.05362): predicts personal bank balances with a **hybrid of historical averaging + regularized regression on top of heuristically extracted recurring transactions** — i.e., recurring-schedule detection + residual modelling, exactly the architecture in question. VERIFIED the architecture; exact error figures could not be retrieved (arXiv fetch blocked via proxy) — treat numbers as unconfirmed.
- **Digit (Oportun) safe-to-save:** PARTIAL. Multiple credible reviews describe the approach — forecast paychecks, upcoming bills, and typical discretionary spend, then sweep only the residual "safe" amount daily, with an overdraft reimbursement guarantee as the business-level precision backstop (https://clark.com/personal-finance-credit/budgeting-saving/digit-review/; https://www.thepennyhoarder.com/save-money/digit-review/, accessed 2026-07-26). No published accuracy metrics.
- Overdraft prediction: mostly patents (e.g., US 11,010,844 "Preemptive data processing to mitigate against overdraft") and trade press (https://www.cardrates.com/news/study-reveals-predictive-analytics-helps-consumers-avoid-overdrafts/). One adjacent peer-reviewed datapoint: checking-account features predict default with **AUC ≈ 0.79** (arXiv:1707.00757 — enterprises, not consumers). **NOT FOUND:** any bank publishing consumer balance-forecast MAPE.

## 4. Recurring-transaction detection

**VERIFIED (products/algorithms exist); PARTIAL (accuracy).**

- **Plaid Recurring Transactions** groups streams by description + amount + cadence and requires **≥3 occurrences** for a "matured" stream (https://plaid.com/docs/transactions/ and https://plaid.com/blog/recurring-transactions/, accessed 2026-07-26). Plaid's adjacent income work reports a **variable-frequency-detection (autoregression-based) rate of 95% for salary and 97% for government income streams** (https://plaid.com/blog/machine-learning-income-verification/).
- **BBVA AI Factory, ICAIF '24**: "Unveiling Recurring Financial Patterns" (Nov 2024 — https://dl.acm.org/doi/10.1145/3677052.3698596) — unsupervised filtering to isolate recurring streams before next-transaction forecasting, explicitly addressing noise, overlapping patterns, and short history; also notes calendar **jitter** (month lengths, holidays) forces combining amount periodicity with text descriptions. Full metrics paywalled (fetch 403): PARTIAL.

## 5. Notification fatigue thresholds

**VERIFIED (numbers exist from industry studies; vendor-reported, not peer-reviewed):**

- **2–5 pushes/week → ~46% of users disable notifications; 6–10/week → ~32% uninstall** (widely cited CleverTap/Localytics data — https://clevertap.com/blog/push-notification-metrics-ctr-open-rate/; https://wisernotify.com/blog/push-notification-stats/, accessed 2026-07-26).
- **52% of users who disable push eventually churn** (Localytics, via same sources). Braze attributes opt-outs primarily to irrelevance and excessive frequency (URL above).

## Recommendation for our insights engine

**Detection stack:** (1) recurring-stream extraction first (description clustering + amount tolerance + cadence with calendar-jitter handling, ≥3 occurrences to mature — mirror Plaid/BBVA); (2) subtract recurring streams, then run **MAD-based robust z-scores per category on the residual** for point anomalies (contamination-safe on 6–24 months of weekly/monthly buckets); (3) add **robust STL / S-H-ESD only for series long enough to estimate seasonality** (≥2 seasonal cycles), and a simple changepoint test (e.g., PELT on medians) to distinguish "new normal" from one-off spikes so we stop re-alerting after a genuine level shift; (4) cashflow forecast = recurring schedule projection + conservative quantile (e.g., P10 balance) residual model, Digit-style "safe amount" framing.

**Precision targets:** given ~46% disable risk at even 2–5 pushes/week, cap proactive insight notifications at **~1–3/week**, require an estimated **precision ≥80–90% for pushed alerts** (tune thresholds so false alarms are rarer than ~1/month/user), and route lower-confidence findings to an in-app feed instead of push. For overdraft/balance warnings, bias to recall but pair with conservative quantile forecasts; for "unusual spend" pushes, bias hard to precision. These thresholds are engineering judgment derived from the fatigue data above — no published fintech-specific precision standard exists (NOT FOUND).

**Caveats:** several primary sources (arXiv PDFs, ACM full text, Pushwoosh benchmarks) returned 403 via the proxy, so some figures rely on search-result summaries and secondary citations; the Localytics fatigue numbers are vendor research (~2015-era) that the industry still cites in 2026.
