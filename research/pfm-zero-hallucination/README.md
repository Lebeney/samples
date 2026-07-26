# Zero-Hallucination PFM Assistant — Deep-Research Synthesis

**Research date:** 2026-07-26 · **Method:** 10 parallel research agents with live web search, each instructed to cite URLs + dates and to label every claim VERIFIED / PARTIAL / NOT FOUND rather than answer from training memory. Full per-topic reports with citations are in [`detail/`](detail/).

**Bottom line:** the evidence strongly supports Doc A's structural-enforcement position. Every credible shipping product (Intuit GenRuntime, Cleo, Origin) converges on the same architecture — *deterministic code computes every number; the LLM plans, routes, and narrates* — and every open disagreement in §B resolves toward the structural side, with two refinements: streaming is viable via a buffer-verify-release pattern (B6 flips), and Doc B's `seed: 42` "determinism locking" is confirmed wrong (B7). One Doc A assumption fails pressure-testing: MCC is not a usable primary enrichment signal (~63% correct, absent on non-card rails).

---

## 1. Verdicts on the open disagreements (§B)

| # | Question | Verdict | Evidence (see detail reports) |
|---|---|---|---|
| **B1** | What does the narrator receive? | **Doc A — flat pre-computed envelope.** No direct published A/B exists (PARTIAL), but all adjacent evidence points one way: flat key-value formats beat tables for value lookup (60.7% vs 44.3% CSV in an 11-format benchmark); measured numeric-hallucination rates when narrating financial tables run 4–6.5% even for frontier models, dominated by "context mismatch" (right number, wrong referent); Ehud Reiter's data-to-text guidance is to compute insights outside the LLM and pass them in. | [detail/02](detail/02-grounding.md) §1 |
| **B2** | Text-to-SQL vs constrained IR | **Doc A — constrained QuerySpec IR.** BIRD SOTA is 81.95% vs 92.96% human; Spider 2.0-Lite tops at 73.67%; a 2026 Berkeley benchmark puts frontier models at 25–43% on real-world data questions. The failure mode is exactly the dangerous one: valid-but-wrong SQL (NL2SQL-BUGs, KDD 2025). Meanwhile every credible 2025–26 accuracy gain (Cube +17–23 pts, dbt SL to ~98–100% on covered queries, AtScale <20%→92.5%, Cortex Analyst ~90%) comes from constraining the LLM to pre-defined semantic objects — i.e., the industry converged on Doc A's approach. | [detail/01](detail/01-text-to-sql.md) |
| **B3** | Post-generation verifier necessary? | **Doc A — mandatory.** No published "do not calculate" violation rate exists, but frontier models fail 20–40% of verifiable instructions (IFEval-class evals), and 2026 work ("The Compliance Gap") documents models verbally committing to process instructions then defecting — precisely the narrator-helpfully-computes failure mode. Temperature 0 does not enforce compliance. No provider ships an exact-match numeric verifier (see D3), so it must be built. | [detail/02](detail/02-grounding.md) §2, §4 |
| **B4** | Templates vs LLM narration | **Doc A's hybrid, weakly held.** No rigorous published production A/B (PARTIAL). Directional: template systems structurally cannot hallucinate; Reiter recommends template-then-polish or insights-as-input hybrids. Treat as a cost/latency decision, not a safety one — the verifier is the safety layer either way, and templates double as the verified fallback path on verification failure. | [detail/02](detail/02-grounding.md) §7 |
| **B5** | Build vs buy enrichment | **Split decision.** Buy for US/EU card rails (vendor merchant databases are the moat: Ntropy beats GPT-4 by 15 pts on its benchmark; MX claims +30 pts vs nearest competitor). Build for Africa — no major vendor covers it (Plaid Enrich/Spade are US/CA-only; Okra shut down May 2025). Adopt Plaid's open PFC taxonomy (16 primary / 104 detailed, free CSV) either way. | [detail/04](detail/04-enrichment.md) |
| **B6** | Streaming | **Doc A's position is now outdated — verify-then-stream works.** Sentence-level buffer→verify→release is a published, shipped pattern (SentGuard 2026; NVIDIA NeMo Guardrails streaming validation; Guardrails AI chunk validation) with ~one-sentence latency cost. Stream, but only verified sentences. | [detail/02](detail/02-grounding.md) §7 |
| **B7** | `seed` for determinism | **Doc A confirmed; Doc B's "deterministic response locking" is wrong.** OpenAI documents seed as explicitly best-effort; Gemini's seed is best-effort; **Anthropic has no seed parameter at all**, and the newest Claude/GPT models reject `temperature`/`top_p` outright. Root cause of temp-0 nondeterminism is batch-variance in inference (Thinking Machines, Sep 2025); no major API provider serves batch-invariant inference as of mid-2026. Design for *system-level* reproducibility (canonicalized QuerySpec, cached prompt→spec pairs), not token-level determinism. | [detail/03](detail/03-structured-outputs.md) §4 |

## 2. Fact-check results (§D)

| # | Claim | Verdict |
|---|---|---|
| D1 | `top_p: 0` is a no-op or error at temp 0 | **CONFIRMED** — no-op where accepted (OpenAI), rejected as out-of-range on several Anthropic-compatible surfaces, and newest Claude/GPT models 400 on the parameter entirely. Don't send it. |
| D2 | `seed` is best-effort only | **CONFIRMED** — explicitly documented best-effort on OpenAI and Google; Anthropic offers none. |
| D3 | No provider ships a built-in numeric-grounding verifier | **CONFIRMED** — Bedrock contextual grounding and Azure groundedness are probabilistic model-scored checks; Bedrock Automated Reasoning checks (GA Aug 2025) are the closest deterministic offering but validate policy compliance via an LLM translation step, not number-vs-ledger equality. Build it. |
| D4 | Financial QA benchmarks are document-QA, not transaction analytics | **CONFIRMED** — FinQA/ConvFinQA/TAT-QA/DocMath/BizBench and the 2025–26 additions (FinBen, FailSafeQA, Finance Agent Benchmark) all target filings/market documents. No personal-transaction-analytics benchmark exists; build the golden set. |
| D5 | Small fine-tuned encoders still beat LLMs on categorization cost/consistency | **CONFIRMED with caveat** — 2026 studies show 1–2 orders of magnitude cost/latency advantage (one: ~300× faster inference at higher accuracy). Caveat: LLMs win the unseen long tail; the consensus production pattern is cached lookup → fine-tuned encoder head → LLM tail fallback. |
| D6 | No injection defence is complete; structural avoidance is primary | **CONFIRMED** — OpenAI/Anthropic/DeepMind all state injection is unsolved in current architectures; classifier defences (Prompt Shields, PromptGuard) have documented 100% evasions; CaMeL-style structural isolation is the only *provable* class of defence. Bonus: the transaction-memo vector Doc A flagged as underappreciated has since been publicly demonstrated (the "One-Cent Attack" via SEPA memo fields). |
| D7 | CFPB §1033 status | **MATERIALLY CHANGED** — rule finalized Oct 2024, then: CFPB reversal + accelerated re-rulemaking (Jul–Aug 2025 ANPR reopening fees/scope), preliminary injunction Nov 2025, April 2026 compliance date passed without effect. As of Jul 2026: codified but unenforceable; replacement rule pending; state data-sharing laws filling the gap. Aggregator access continues contractually; budget for possible data-access fees. |
| D8 | Text-to-SQL execution accuracy remains below money-product requirements | **CONFIRMED** — see B2. Nuance: Spider 2.0-Snow leaderboard tops read 94–97%, but those are bespoke vendor agent stacks on a benchmark shown to have 66.1% annotation errors (CIDR 2026); not evidence of safety. |

## 3. The confirmed architecture ("a good way to do this")

Converging evidence from research, provider docs, and production teardowns supports this pipeline:

```
user NL question
  │
  ▼
PLANNER (strong model; free-text/extended thinking FIRST, then grammar-
constrained emit of QuerySpec JSON — never answer-field-first)
  │  Pydantic/semantic validation; ≤2 error-feedback retries; then cannot_answer
  ▼
QuerySpec (constrained IR) ──deterministic compiler──▶ SQL ──▶ ledger/analytics store
  │                                                              (append-only, bi-temporal,
  ▼                                                               integer minor units)
RESULT ENVELOPE (flat, pre-computed figures + allowed-values whitelist,
canonical category labels; NO raw descriptors, NO multi-row tables)
  │
  ▼
NARRATOR (small fast model: Haiku 4.5 / GPT-5 mini / Flash-Lite class)
  │
  ▼
NUMERIC WHITELIST GATE (deterministic, exact Decimal match after
normalization; rounding-only tolerance; number↔label pairing check)
  │  pass → release sentence (buffer-verify-release streaming)
  │  fail → one named-violation retry, then template fallback; fail closed
  ▼
user
```

Key design points, each grounded in the detail reports:

1. **Planner reasons before it emits.** The "constrained decoding hurts reasoning" result (Tam et al. 2024) is now understood mechanistically: forcing the answer before chain-of-thought is the harm; free-text reasoning followed by grammar-constrained emit recovers essentially all the loss (CRANE 2025, "Thinking Before Constraining" 2026). Claude's extended thinking + structured outputs implements exactly this. [detail/03 §1–2]
2. **Grammar-constrained structured outputs eliminate syntactic retries;** budget max 2 error-feedback retries for *semantic* validation only — returns plateau after the first retry. [detail/03 §3]
3. **The verifier is a numeric whitelist gate** — lineage: HERMAN (EMNLP 2020), QuanTemp (SIGIR 2024); no commercial equivalent exists. Normalize (strip separators/currency, words→values, percent vs fraction, sign), compare as exact `Decimal`, allow only envelope-declared rounded renderings, and check number-to-label pairing (context-mismatch is the dominant error type). LLM-as-judge is strictly worse here: judges approved 7.1% of wrong answers *with ground truth in hand*. [detail/02 §3–6]
4. **Prompt-injection posture:** the analytics path never sees raw descriptors (breaks Willison's "lethal trifecta" structurally — the CaMeL/Plan-Then-Execute pattern); the enrichment path treats descriptors as untrusted input to a quarantined, tool-less classifier whose only output is a validated enum; classifier-based shields are defence-in-depth only (documented 100% evasions). [detail/07]
5. **Data foundation:** single-entry append-only observation ledger (you mirror external systems of record; double-entry buys nothing here — Modern Treasury/TigerBeetle are money-movement systems), bi-temporal (`effective_at` + `recorded_at`), corrections as superseding records, integer minor units. Pending→posted: trust `pending_transaction_id` when present but always run a fallback matcher (Plaid documents matching failures). DuckDB-per-tenant is production-credible in 2026 via catalog-plus-Parquet or MotherDuck hypertenancy; DuckLake 1.0 (Apr 2026) removes the single-writer constraint. Postgres stays the system of record. [detail/05]
6. **Enrichment:** demote MCC to a weak prior (~63% correct by MCC alone; absent on ACH/mobile-money rails). Pattern: cached merchant dictionary → fine-tuned encoder head → LLM tail fallback; buy vendor coverage for US/EU, build for Africa (Mono is the surviving Nigerian aggregator post-Okra). [detail/04]
7. **Evaluation:** build a 250–300-item golden set over a deterministic Plaid-schema synthetic generator (ground truth computed by an independent reference implementation); metrics = QuerySpec exact match, executed-result numeric match (headline), correct-refusal rate; CI-gate at ≥90% overall and 100% on a ~50-item never-break core (Langfuse self-hosted + pytest deterministic scorers; note Promptfoo was acquired by OpenAI, Mar 2026). ~90% on a curated set is the de-facto enterprise bar (Cortex Analyst); ThoughtSpot's honest ~60%-on-complex-models figure shows why the constrained-IR approach is needed to beat it. [detail/06]
8. **Model/config stance:** planner = Sonnet-class/GPT-5 with structured outputs + thinking (prompt-cache the schema: ~0.1× cached-read pricing); narrator = Haiku 4.5 ($1/$5 per MTok) / GPT-5 mini ($0.25/$2) / Flash-Lite class. Do not fine-tune the planner below millions of specs/month — OpenAI is sunsetting self-serve fine-tuning (new jobs end Jan 2027). Omit sampling params on newest models; never send `top_p: 0`. [detail/03 §5–6]
9. **Insights engine:** recurring-stream extraction first (≥3 occurrences, calendar-jitter handling), MAD-based robust z-scores on the residual, robust STL/changepoint only with ≥2 seasonal cycles; cap pushes at ~1–3/week with ≥80–90% estimated precision (2–5 pushes/week → ~46% of users disable notifications); low-confidence insights go to an in-app feed. [detail/08]
10. **Regulatory:** stay behind the advice line (budgeting/spending analytics; no personalized securities recommendations) or register the channel (Origin's SEC-RIA route). EU AI Act Article 50 AI-disclosure applies **Aug 2, 2026** — imminent; high-risk (creditworthiness) obligations delayed to Dec 2027. UK's targeted-support regime (live Apr 2026) is the most PFM-favorable advice-boundary development. Nigeria: CBN open banking phasing in through 2026 via NIBSS registry; NDPA/GAID compliance (DPO, registration, audit returns) required. Disclaimers don't immunize conduct — FTC v. Cleo ($17M, Mar 2025). [detail/09]

## 4. Where the evidence is thin (honest gaps)

- **B1** has no direct published A/B of table-vs-envelope narration error rates — run the internal experiment; the golden set makes it cheap.
- **B4** (templates vs LLM narration) has no production-grade published comparison; decide on cost/latency, keep templates as the fallback path.
- Transfer-pair detection and pending→posted matching have **no published accuracy rates anywhere** — instrument your own matcher from day one.
- Consumer cashflow-forecast accuracy (MAPE) is unpublished across the industry; Digit's overdraft-reimbursement guarantee is the only visible precision proxy.
- Several primary sources (arXiv PDFs, Plaid blog, Snowflake blog) were bot-blocked during research; affected figures are labeled PARTIAL in the detail reports and rest on search-index excerpts or secondary citations.

## 5. Mapping to the planned deliverables (§E of the agenda)

| Deliverable | Status after this research |
|---|---|
| E1 Verifier module spec | Prior art identified (HERMAN, QuanTemp, SentGuard, VeNRA); normalization + tolerance rules drafted in detail/02 §Implications — ready to write as a spec |
| E2 Corrected QuerySpec schema | Provider constraints now known (no recursive schemas on Anthropic; enum-size limits on Gemini; `additionalProperties:false` required) — see detail/03 §2 |
| E3 Build-vs-buy enrichment | Decided: buy US/EU (Ntropy/Tapix multi-region; Plaid/Spade US), build Africa; MCC demoted — detail/04 |
| E4 Eval plan | Full skeleton with sizes, mix, metrics, CI gates, tooling — detail/06 |
| E5 Regulatory one-pagers | Per-jurisdiction status, risk table, draft disclosure language — detail/09 |
| E6 Aggregator shortlist | Plaid primary US + MX/Finicity fallback; Tink/TrueLayer/Salt Edge EU; Mono for Nigeria; avoid GoCardless BAD — detail/10 |
| E7 Build Note v2.0 | All §B disagreements resolved with evidence above; ready to merge the two documents |

## Detail reports

| File | Covers |
|---|---|
| [detail/01-text-to-sql.md](detail/01-text-to-sql.md) | Spider 2.0 / BIRD leaderboards, valid-but-wrong SQL, semantic layers (B2, C1, D8) |
| [detail/02-grounding.md](detail/02-grounding.md) | Numeric faithfulness, verifier prior art, provider grounding checks, verify-then-stream (B1, B3, B4, B6, C2, D3) |
| [detail/03-structured-outputs.md](detail/03-structured-outputs.md) | Constrained decoding, provider parity, retries, determinism, pricing (B7, C3, C12, D1, D2) |
| [detail/04-enrichment.md](detail/04-enrichment.md) | Categorization SOTA, MCC reliability, vendor table, merchant normalization (B5, C4, D5) |
| [detail/05-ledger.md](detail/05-ledger.md) | Bi-temporal ledgers, pending→posted, transfer pairs, DuckDB-per-tenant (C5) |
| [detail/06-evaluation.md](detail/06-evaluation.md) | Benchmark transferability, golden-set methodology, eval tooling, CI gating (C6, D4) |
| [detail/07-prompt-injection.md](detail/07-prompt-injection.md) | OWASP status, memo-field attacks, defence effectiveness (C7, D6) |
| [detail/08-insights.md](detail/08-insights.md) | Anomaly detection, cashflow forecasting, notification fatigue (C8) |
| [detail/09-regulatory.md](detail/09-regulatory.md) | CFPB §1033, EU AI Act/PSD3/FiDA, FCA, Nigeria CBN/NDPA (C9, D7) |
| [detail/10-competitive-aggregators.md](detail/10-competitive-aggregators.md) | Intuit/Cleo/Origin/Nubank teardowns, aggregator comparison, Africa (C10, C11) |
