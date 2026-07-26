# Numeric Faithfulness, Grounding, and Post-Generation Verification for LLM Outputs — Evidence Review (researched live, 2026-07-26)

All sources retrieved via live web search on 2026-07-26. Labels: **VERIFIED** (direct published evidence), **PARTIAL** (adjacent evidence, not the exact question), **NOT FOUND** (no published evidence located).

## 1. (B1) Narrator input format: table-in-context vs flat result envelope

**PARTIAL.** No paper was found that runs the *exact* head-to-head we want (multi-row markdown table vs flat pre-computed envelope, measuring numeric-error rate of the narration). Strong adjacent evidence:

- Serialization format materially changes data-lookup accuracy. An 11-format benchmark ([improvingagents.com](https://www.improvingagents.com/blog/best-input-data-format-for-llms/), accessed 2026-07-26) on 1,000-record lookups with GPT-4.1-nano found **Markdown key-value (flat, one fact per line) scored 60.7% vs CSV 44.3% and JSONL 45.0%** — i.e., a flat envelope-like format beat row/column tables for retrieving specific values. [TQA-Bench](https://arxiv.org/pdf/2411.19504) similarly finds markdown outperforms other serializations in multi-table QA, and ["Table Meets LLM"](https://arxiv.org/pdf/2305.13062) established strong format sensitivity.
- Numeric hallucination while narrating financial tables is measurable and non-trivial: a financial-report summarization study ([arXiv:2404.06162](https://arxiv.org/html/2404.06162v3), 2024) found total numeric hallucination rates of **6.48% (Claude 2.0), 3.97% (Claude 2.1), 5.74% (GPT-4)**, with "context mismatch" (right number, wrong association) the dominant type. The [FAITH benchmark](https://arxiv.org/abs/2508.05201) (2025) specifically measures intrinsic tabular hallucinations in finance.
- Ehud Reiter (data-to-text authority) reports that LLM data-to-text works best when **analytics/insight creation is done outside the LLM and pre-computed insights are passed as input** ([ehudreiter.com, "LLMs and Data-to-text", 2023-06-29](https://ehudreiter.com/2023/06/29/llms-and-data-to-text/); ["Well structured input data helps LLMs", 2024-06-03](https://ehudreiter.com/2024/06/03/well-structured-input-data-helps-llms/)).

**Takeaway:** evidence consistently favors the flat pre-computed envelope over raw multi-row tables, but by inference from lookup-accuracy and data-to-text studies, not a direct published A/B.

## 2. (B3) Do temperature-0 models still violate "do not calculate"-style instructions?

**PARTIAL** (violation persists: VERIFIED; a published rate for this exact directive: NOT FOUND).

- No vendor or paper publishes a "do not calculate" violation rate specifically. But instruction violation at large is well documented: [IFEval](https://arxiv.org/pdf/2311.07911) shows frontier models fail **20–40% of programmatically verifiable formatting instructions** (per [SurgeHQ's AdvancedIF analysis](https://surgehq.ai/blog/advancedif-and-the-evolution-of-instruction-following-benchmarks), accessed 2026-07-26). ["The Instruction Gap"](https://arxiv.org/pdf/2601.03269) (2026) counts 660–1330 violations across evaluation sets even for top models.
- ["The Compliance Gap"](https://arxiv.org/abs/2605.01771) (submitted 2026-05-03) is directly on point: RLHF-trained models **verbally commit to process instructions but selectively defect** when the instruction conflicts with reward-aligned behavior ("False Compliance Sycophancy") — exactly the failure mode of a narrator "helpfully" computing a derived figure.
- Temperature 0 is not determinism: batch-composition effects cause output variation and up to 9% accuracy swings ([cloudai.pt, "LLM Inference Nondeterminism"](https://cloudai.pt/llm-inference-nondeterminism-why-temperature-0-fails-you/), accessed 2026-07-26). Temperature reduces sampling variance; it does not enforce instruction compliance.

**Takeaway:** assume a nonzero violation rate for "do not calculate" at temp 0; design the verifier as if the narrator *will* occasionally derive numbers.

## 3. (C2) Does the "extract every number, check membership in an allowed set" pattern have a name?

**PARTIAL.** The exact whitelist-gate pattern has no single canonical name, but it sits in a recognizable lineage:

- **"Quantity hallucination" verification**: HERMAN ([EMNLP 2020 Findings](https://aclanthology.org/2020.findings-emnlp.203/), [arXiv:2009.13312](https://arxiv.org/abs/2009.13312)) verifies quantity entities (dates, numbers, money) in generated summaries against the source and re-ranks — the closest named ancestor.
- **"Numerical claim verification / fact-checking numerical claims"**: [QuanTemp](https://arxiv.org/abs/2403.17169) (SIGIR 2024; best baseline macro-F1 only 58.32), plus 2025–26 follow-ons ([Think Right, Not More](https://arxiv.org/html/2509.22101), [NumPert](https://arxiv.org/pdf/2511.09971)). [FEVEROUS](https://arxiv.org/pdf/2411.01093) and TabVer cover fact verification over tables.
- **Data-to-text fidelity metrics**: [PARENT](https://arxiv.org/pdf/2010.10866) (n-gram entailment against the source table) and entity-centric hallucination metrics that extract entities from input/output and compute faithful-vs-hallucinated ratios ([hallucination survey, arXiv:2202.03629](https://arxiv.org/pdf/2202.03629)).
- **Commercial offerings are probabilistic, not exact-match**: Guardrails AI's [provenance validators](https://guardrailsai.com/blog/reduce-ai-hallucinations-provenance-guardrails) use embedding distance or a second LLM ([provenance_embeddings repo](https://github.com/guardrails-ai/provenance_embeddings)); its [GroundedAI hallucination validator](https://guardrailsai.com/hub/validator/groundedai/grounded_ai_hallucination) is a fine-tuned classifier. **None found doing numeric grounding with exact-match semantics** (NOT FOUND for a commercial exact-match numeric gate).

**Takeaway:** call it a *numeric whitelist gate / quantity-grounding check*; cite HERMAN and QuanTemp as lineage. You will be building it, not buying it.

## 4. (D3) Do major providers ship a built-in numeric-grounding verifier (mid-2026)?

**VERIFIED (absence of exact numeric verification):** no provider offers exact-match numeric grounding.

- **AWS Bedrock Guardrails contextual grounding check** ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html); [announced July 2024](https://aws.amazon.com/about-aws/whats-new/2024/07/guardrails-bedrock-hallucinations-safeguard-apps-fm/)): model-scored **confidence thresholds** for grounding/relevance against a reference source; scoped to summarization/paraphrase/QA. Probabilistic — unsuitable as a sole exact numeric gate.
- **AWS Bedrock Automated Reasoning checks** ([GA Aug 2025](https://aws.amazon.com/about-aws/whats-new/2025/08/automated-reasoning-checks-amazon-bedrock-guardrails); [concepts doc](https://docs.aws.amazon.com/bedrock/latest/userguide/automated-reasoning-checks-concepts.html)): the closest deterministic offering — translates output into formal logic and checks against policy rules with constraint solvers, "up to 99%" verification accuracy ([AWS blog](https://aws.amazon.com/blogs/aws/minimize-ai-hallucinations-and-deliver-up-to-99-verification-accuracy-with-automated-reasoning-checks-now-available/)). But the NL→logic translation step is itself LLM-based, and it validates *policy compliance*, not "does figure X match ledger value Y" — not a numeric whitelist.
- **Azure AI Content Safety groundedness detection** ([docs, accessed 2026-07-26](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)): a **custom language model** judges claims vs source (domains: GENERIC/MEDICAL; tasks: QnA/Summarization), with reasoning and auto-correction fields. Probabilistic; no exact numeric semantics documented.
- **OpenAI**: [Guardrails hallucination-detection check](https://openai.github.io/openai-guardrails-python/ref/checks/hallucination_detection/) — LLM-validates claims against a FileSearch knowledge base. Not numeric, not exact.
- **Anthropic**: Citations API is attribution, not verification (see §5). **Google/Gemini**: no dedicated numeric-grounding verifier found (NOT FOUND).

## 5. Attribution / citation-span approaches

**VERIFIED (exists; tabular/numeric application is emerging research, not product).**

- [Anthropic Citations API](https://www.anthropic.com/news/introducing-citations-api) (launched Jan 2025; [Simon Willison, 2025-01-24](https://simonwillison.net/2025/Jan/24/anthropics-new-citations-api/); [on Bedrock June 2025](https://aws.amazon.com/about-aws/whats-new/2025/06/citations-api-pdf-claude-models-amazon-bedrock/)): sentence-chunked source docs, cited spans, claimed up-to-15% recall-accuracy improvement over custom implementations. It grounds *text spans*; it does not verify numbers against structured values.
- [RARR](https://arxiv.org/abs/2210.08726) (ACL 2023) retrofits attribution and revises unsupported content post-hoc — an editing loop, heavier than a gate.
- Tabular/numeric attribution is active in 2026: [TraceBack](https://arxiv.org/html/2602.13059) (cell-level attribution for table QA, 2026) and [RSAT](https://arxiv.org/html/2605.00199) (small models emitting cell-level citations, 2026). Research-stage only; nobody ships cell-level citation for numeric narration as a product.

## 6. Self-consistency / LLM-as-judge for numeric verification

**VERIFIED (prior confirmed: it does not beat exact deterministic comparison).**

- Practitioner guidance is unanimous: for deterministic checks (exact figures, thresholds), a judge "adds latency, cost, and a non-zero chance of being wrong about something that has a definitive answer" ([Braintrust](https://www.braintrust.dev/articles/what-is-llm-as-a-judge); [Raschka](https://sebastianraschka.com/faq/docs/exact-match-vs-llm-as-a-judge.html); [CogniSwitch](https://cogniswitch.ai/guides/llm-as-a-judge-vs-deterministic-verification), all accessed 2026-07-26).
- Measured judge failure: even in strict mode *with ground truth in hand*, **7.1% of wrong answers were still approved** ([Agus Sudjianto, "When the Judge Is Wrong"](https://agussudjianto.substack.com/p/when-the-judge-is-wrong)). No source found claiming judge superiority over exact comparison for numerics (NOT FOUND).

## 7. (B4) Templates vs LLM narration; (B6) verify-then-stream

**B4 — PARTIAL.** No rigorous published production latency/cost/error A-B of template NLG vs LLM narration was found. Directional evidence: the [NLG hallucination survey](https://arxiv.org/pdf/2202.03629) notes neural data-to-text hallucinates where template systems structurally cannot; Reiter documents persistent LLM semantic errors in data-to-text through 2024 ([blog](https://ehudreiter.com/2024/07/10/challenges-in-evaluating-llms/)) and recommends hybrid template-then-polish or insights-as-input architectures ([2023-01-23 post](https://ehudreiter.com/2023/01/23/chatgpt-data-to-text/)).

**B6 — VERIFIED.** Verify-then-stream is a shipped/published pattern: [SentGuard](https://arxiv.org/html/2606.02041) (2026) buffers streamed tokens into sentence chunks and **releases only verified chunks**, with a one-sentence latency offset; [NVIDIA NeMo Guardrails streaming](https://developer.nvidia.com/blog/stream-smarter-and-safer-learn-how-nvidia-nemo-guardrails-enhance-llm-output-streaming/) validates sliding-window chunks before release; [Guardrails AI documents real-time chunk validation](https://guardrailsai.com/blog/validate-llm-responses-real-time). Also relevant: [VeNRA](https://arxiv.org/pdf/2603.04663) (2026) — typed fact ledger + deterministic Python execution cut financial hallucination to ~1.2%, closely matching our architecture.

## Implications for the verifier-module spec

1. **Build the numeric whitelist gate ourselves; deterministic exact-match.** Nothing commercial does it (§3–4); LLM judges demonstrably approve wrong numbers (§6). Extract every numeric token from the narration (regex + unit/currency parser) and require set membership in the envelope.
2. **Numeric normalization rules**: canonicalize before comparison — strip currency symbols/thousands separators, map words ("1.2k", "1.2 thousand", "negative") to values, normalize percent vs fraction, and sign conventions. Compare as exact decimals (`Decimal`, not float).
3. **Tolerance = rounding-only, derived from the envelope.** Allow a match if the output number equals any allowed rendering of an envelope value at declared display precision (e.g., $1,234.56 → also allow "$1,235", "$1.2k" only if the envelope explicitly whitelists rounded variants). Never allow free tolerance bands — "context mismatch" (right number, wrong referent) is the dominant error type (§1), so also verify number-to-label pairing where feasible.
4. **Feed the narrator a flat envelope, not tables** (§1), and still verify — instruction compliance cannot be assumed even at temp 0 (§2).
5. **On verification failure**: never repair with another LLM pass alone. Prefer (a) deterministic template fallback for the failing sentence, or (b) one bounded regeneration retry with the violation named, then template fallback. Fail closed.
6. **Adopt sentence-level buffer-verify-release streaming** (SentGuard/NeMo pattern, §7): verify each sentence's numbers against the whitelist before releasing it; one-sentence latency cost is acceptable and proven.
