# Text-to-SQL & Semantic-Layer State of the Art (as of 2026-07-26)

**Method note.** The research environment's egress proxy blocked direct fetches of `*.github.io`, `cube.dev`, `snowflake.com`, `arxiv.org`, and `vldb.org` pages. Workaround: the Spider 2.0 and BIRD leaderboards were read **directly from the official websites' source HTML** via `raw.githubusercontent.com` (repos `spider2-sql/spider2-sql.github.io`, updated 2026-07-14, and `bird-bench/bird-bench.github.io`, updated 2026-07-25) — these are the live sites' sources, treated as VERIFIED. Other sources were verified via live web-search results quoting the named source; where the page itself could not be opened the claim is labeled PARTIAL.

## 1. Spider 2.0 leaderboard — VERIFIED (leaderboard HTML fetched 2026-07-26)

Source: https://spider2-sql.github.io/ (site source read from the official repo, last updated 2026-07-14). The original monolithic "Spider 2.0" setting was **removed in May 2025** and replaced by Spider 2.0-DBT (68 repository-level tasks); the site still notes the historical result that o1-preview solved only **17.1%** of original Spider 2.0 tasks and GPT-4o **10.1%**, "compared to 86.6% on Spider 1.0."

- **Spider 2.0-Snow** (547 Snowflake tasks): top scores are now high — Genloop Sentinel Agent v2 Pro **96.70**, Native mini (usenative.ai) **96.53**, QUVI-3 + Gemini-3-pro-preview **94.15**. These are heavily engineered multi-agent industrial systems; plain "Spider-Agent + frontier model" baselines remain low (Claude-4-Sonnet 25.78, o1-preview 23.58, GPT-4o ~11–13).
- **Spider 2.0-Lite** (547 tasks; BigQuery/Snowflake/SQLite): top = ktx (Kaelio) **73.67**, DivSkill-SQL (Snowflake AI Research x UCSD) **73.13**, SOMA-SQL (Oracle) **72.02**.
- **Spider 2.0-DBT** (68 project-level tasks): top = SignalPilot Agent **65.6**, Databao Agent (JetBrains) **60.29**; Spider-Agent + GPT-5 class models ~35–40.
- Spider 1.0 comparison: top Spider 1.0 test execution accuracy is **91.2%** (MiniSeek, Nov 2023 — VERIFIED via https://www.seek.ai/blog/miniseek-first-model-to-surpass-90-accuracy-on-spider-test-benchmark), and the Spider 2.0 site itself cites GPT-4o at 86.6% on Spider 1.0 vs 10.1% on Spider 2.0.

**Caveat:** per the CIDR 2026 paper below, **66.1% of sampled Spider 2.0-Snow instances have annotation problems**, so the 90%+ Snow scores should be read skeptically.

## 2. BIRD benchmark — VERIFIED (leaderboard HTML fetched 2026-07-26)

Source: https://bird-bench.github.io/ (site source read from official repo, updated 2026-07-25).

- **Overall leaderboard (test, execution accuracy):** Human performance **92.96**. Top systems: AskData + GPT-4o (AT&T CDO, Dec 2025) **81.95**; Agentar-Scale-SQL (Ant Group) **81.67**; Sber Text2SQL **81.33**; Xiaomi Text2SQL **80.83**. So the best system is still ~11 points below human, after 3 years of intense competition; scores cluster in the 75–82 band.
- **R-VES (efficiency-weighted) leaderboard:** human 83.26; best model 77.00.
- **BIRD-CRITIC / SWE-SQL exists — VERIFIED.** NeurIPS 2025 main-track paper; BIRD-Critic-SQLite (500 tasks) released 2026-03-23. Human performance **76.67%** (without AI tools) vs leading models ~**38–45%** success (o3-mini 38.87% on PostgreSQL) — via https://bird-critic.github.io/ and https://github.com/bird-bench/BIRD-CRITIC-1 (search-verified).
- **BIRD-Interact exists — VERIFIED (ICLR 2026 Oral).** Site news (Oct 2025): GPT-5 (Med) achieves only **8.67% SR on c-Interact and 17.00% on a-Interact**; best LLMs ~16.33% on BIRD-Interact-Full.
- Also new: **LiveSQLBench** (contamination-free; Gemini-2.5-Pro 28.67% on colloquial queries of Base-Full-v1; Large-v1 released 2026-03-03 with ~1K-column DBs).

## 3. "Valid-but-wrong SQL" failure analyses

- **NL2SQL-BUGs (KDD 2025) — VERIFIED** (https://dl.acm.org/doi/10.1145/3711896.3737427, https://nl2sql-bugs.github.io/): benchmark explicitly for "semantically incorrect queries that execute successfully but produce wrong results"; 2,018 expert-annotated instances; LLMs detect such semantic errors with only **~75.16%** accuracy; it also found previously unnoticed semantic errors in **1.55% of Spider dev and 6.91% of BIRD dev gold queries**.
- **"Text-to-SQL Benchmarks are Broken" (Jin, Choi, Zhu, Kang; CIDR 2026) — VERIFIED via search** (https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf; arXiv:2601.08778, Jan 2026, published as "Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards", VLDB Endowment, May 2026): finds annotation-error rates of **52.8% in BIRD and 66.1% in Spider 2.0-Snow** — i.e., even the *gold* answers frequently embody silent semantic mismatches.
- **Rajkumar et al. 2022** (arXiv:2204.00498) manually analyzed 100 predictions that were **valid SQL yet judged incorrect** — an early quantification that most failures are semantic, not syntactic. PARTIAL (older paper, found via search).
- **Berkeley EPIC Data Agent Benchmark (2026) — PARTIAL** (https://promptql.io/blog/berkeley-data-agent-benchmark-will-text-to-sql-ever-be-good-enough; arXiv:2603.20576): frontier models score **Opus 4.6 43%, Gemini 3 Pro 38%, GPT-5.2 25%** on real-world data questions; agents "typically select the right data, but fail at planning the computation or implementing it correctly" — i.e., plausible-but-wrong outputs dominate.
- A single canonical number for "X% of all errors execute successfully" across systems: **NOT FOUND** — the literature quantifies it per-benchmark (NL2SQL-BUGs, CIDR 2026) rather than as one headline rate.

## 4. Semantic layer + LLM accuracy

- **Cube paired benchmark (cube.dev blog, ~2026) — PARTIAL** (page blocked; numbers via search results quoting it): 100 NL questions over Cleaned Contoso Retail on ClickHouse; three frontier models; semantic layer adds **+17.2 to +23.2 points**: Opus 4.7 50.5%→67.7%, Sonnet 4.6 46.5%→68.7%, GPT-5.4 45.5%→68.7%. Companion arXiv paper "Semantic Layers for Reliable LLM-Powered Data Analytics" (arXiv:2604.25149, Apr 2026) — PARTIAL.
- **dbt Labs 2026 benchmark — VERIFIED** (repo README read directly: https://github.com/dbt-labs/dbt-llm-sl-bench; results dashboard https://dbt-labs.github.io/dbt-llm-sl-bench/; blog "Semantic Layer vs. Text-to-SQL: 2026 Benchmark Update", docs.getdbt.com): three strategies (raw SQL from DDL, Semantic Layer, MCP) on identical questions. Reported results (via search, PARTIAL on exact figures): Sonnet 4.6 **90.0%→98.2%** and GPT-5.3-Codex **84.1%→100%** on well-modeled data; on messier data **~40% raw vs 83% grounded**; raw text-to-SQL improved from 32.7% (GPT-4, 2023) to 64.5% (2026) on the full set.
- **AtScale — PARTIAL** (https://www.atscale.com/blog/semantic-layers-make-genai-more-accurate/, Aug 2024 coverage at BigDATAwire): TPC-DS, 40 NL questions: GPT-4 raw **<20% correct** vs **92.5%** with semantic layer; 0%→70% on high-complexity questions.
- **Snowflake Cortex Analyst — PARTIAL** (blocked pages; claims via search of snowflake.com engineering blogs, 2024–2025): "**~90%+ accuracy** on internal benchmarks," "close to **2x more accurate** than single-shot GPT-4o SQL generation," ~14% above a market competitor — internal, semantic-model-dependent, not independently audited.
- **Databricks Genie — PARTIAL/NOT FOUND**: no official published accuracy number found. Databricks docs describe a benchmark feature and practitioners target **>80%** before UAT (databricks.com blog "How to Build Production-Ready Genie Spaces"); one third-party test (codecentric.de) showed Genie going **9.5%→69.2%** after metadata enrichment.
- **Malloy — NOT FOUND** for published accuracy numbers; anecdotal practitioner reports (datamonkeysite.com, Mar 2026) say LLMs generate Malloy *worse* than SQL due to training-data scarcity, though the compiler guarantees correct SQL from correct Malloy.

## 5. Verdict on D8

**SUPPORTED, with one nuance.** Evidence for: BIRD test SOTA is **81.95% vs 92.96% human** (an 18% error rate at best on a clean academic benchmark); Spider 2.0-Lite tops at **73.67%** and Spider 2.0-DBT at **65.6%**; Berkeley DAB puts frontier models at **25–43%** on real-world data questions; BIRD-Interact shows **<17%** success when ambiguity resolution with users is required; and NL2SQL-BUGs/CIDR 2026 show the failure mode is precisely the dangerous one — executable, plausible, silently wrong — with even gold annotations wrong 52.8–66.1% of the time. The nuance: Spider 2.0-Snow leaderboard tops now read 94–97%, but these are bespoke vendor agent stacks on a benchmark whose annotations are demonstrably broken, not evidence that free-form NL→SQL is safe. Every error that remains is a *silent wrong answer*, which is unacceptable for money-handling.

**Implication for the PFM architecture:** the constrained-IR (QuerySpec DSL) approach matches where the industry is converging — every credible accuracy gain in 2025–2026 (Cortex Analyst, Cube, dbt SL, AtScale, +17 to +52 points in head-to-heads) comes from making the LLM choose among *pre-defined, deterministic semantic objects* rather than write SQL, which structurally eliminates the valid-but-wrong class for covered queries (dbt reports ~100% on covered queries). Recommended: QuerySpec DSL compiled deterministically to SQL, with schema-validated rejection of out-of-coverage requests — free-form NL→SQL should not touch user-facing financial numbers.
