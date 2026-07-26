# Constrained Decoding, Structured Outputs, Determinism, and Model Economics for a Two-Role LLM System (Planner → JSON QuerySpec; Narrator → short text)

**Research date: 2026-07-26. All claims from live web searches / current docs; status labels per item.**

## 1. (C3) Does constrained decoding degrade reasoning? — **VERIFIED (nuanced consensus)**

- **Original claim:** Tam et al., ["Let Me Speak Freely?"](https://arxiv.org/abs/2408.02442) (EMNLP-Industry 2024, [ACL Anthology](https://aclanthology.org/2024.emnlp-industry.91/)) found strict format restrictions degrade reasoning ~10–30% on reasoning-heavy tasks (GSM8K, Last Letter), with stricter constraints → worse.
- **Rebuttal:** dottxt's ["Say What You Mean"](https://blog.dottxt.ai/say-what-you-mean.html) (2024) re-ran the tasks on Llama-3-8B and found **structured generation matched or beat unstructured** — arguing the paper conflated "JSON-mode" prompting with true constrained decoding and used poor prompts/schemas.
- **Follow-ups (2025–2026):** [JSONSchemaBench / "Generating Structured Outputs from LMs"](https://arxiv.org/html/2501.10868v1) (2025) found degradation is real for open-weight models but **recent closed-weight models have largely closed the gap**. [CRANE](https://arxiv.org/pdf/2502.09061) (2025) showed adaptive constrained decoding beats both pure-constrained and unconstrained (+10% on symbolic reasoning). ["Thinking Before Constraining"](https://arxiv.org/html/2601.07525v2) (2026) and Banerjee et al. 2025 propose "reason free-text first, constrain later" frameworks; the ["Format Tax"](https://arxiv.org/html/2604.03616) and [follow-up studies](https://arxiv.org/pdf/2603.13351) (2026) confirm the mechanism: forcing answer fields **before** chain-of-thought is the main harm.
- **Consensus as of mid-2026:** constrained decoding per se is cheap; forcing the *answer* to be emitted before reasoning is what hurts. **A free-text (or thinking-block) reasoning step before structured emission recovers essentially all the loss** — this is exactly what CRANE/interleaved frameworks and provider "thinking + structured output" modes implement.

## 2. Provider structured-output parity — **VERIFIED (from provider docs)**

| Capability | OpenAI | Anthropic (Claude) | Google Gemini |
|---|---|---|---|
| Mechanism | `response_format: json_schema, strict:true` | `output_config.format` (GA; old `output_format`/beta header deprecated) + `strict: true` tool use | `responseSchema` / JSON-Schema support |
| Guaranteed valid JSON | Yes (grammar-constrained) | Yes — grammar-compiled, "always valid, no retries for schema violations" ([docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), fetched 2026-07-26) | Yes for supported schemas; complex schemas can be **rejected with 400** |
| Depth limit | 5 levels nesting; limits raised 2025-26: **5,000 object properties, 120K string chars, 1,000 enum values** ([community announcement](https://community.openai.com/t/structured-outputs-limits-are-raised-to-support-larger-schemas/1313593), [docs](https://developers.openai.com/api/docs/guides/structured-outputs)) | No fixed published depth, but **recursive schemas unsupported**; no `min/max`, `minLength/maxLength`; `additionalProperties:false` required; internal `$ref` only; 24h compiled-grammar cache | No hard published depth; "schema complexity" 400s (e.g., [~100-value enums rejected](https://github.com/googleapis/python-genai/issues/950)); docs advise trimming enums |
| Recursive schemas | Yes (via `$ref`, within depth limits) | **No** | Effectively no (complexity limits) |
| Tool-choice forcing | `tool_choice: required/named` | `tool_choice: {type:"tool"/"any"}` + `strict:true` tools; note: on Bedrock, forced tool_choice requires thinking disabled | Function-calling mode `ANY` |
| Ordering quirks | — | — | `propertyOrdering` matters; output follows schema key order ([Google blog](https://blog.google/technology/developers/gemini-api-structured-outputs/), [docs](https://ai.google.dev/gemini-api/docs/structured-output)) |

Anthropic structured outputs are **GA for Claude 4.5+ models** (incl. Haiku 4.5); on Claude the schema constraint applies to output while extended thinking still runs free-form first — directly implementing the Q1 recommendation.

## 3. Validation-repair loops — **PARTIAL (evidence thinner than folklore)**

- The [Instructor library](https://python.useinstructor.com/concepts/retrying/) ([retry docs](https://github.com/567-labs/instructor/blob/main/docs/concepts/retrying.md)) feeds Pydantic validation errors back on retry ("reask"); default `max_retries` is small (1–3; tenacity-configurable). Docs confirm error-feedback helps convergence but warn of **context growth per retry** hitting max_tokens ([issue #1466](https://github.com/instructor-ai/instructor/issues/1466)).
- Academic evidence: an [empirical self-correction study for data-science codegen](https://arxiv.org/pdf/2408.15658) found self-debugging gains **plateau after the first retry**; ["How Many Tries Does It Take?"](https://arxiv.org/html/2604.10508) (2026) finds self-repair universally helps but with sharply diminishing returns, and *mechanical* errors (parse/name errors — the QuerySpec case) repair at high rates on try 1 while *semantic* errors barely improve with more tries. [Self-Reflective APIs](https://arxiv.org/pdf/2606.05037) (2026): structured error messages beat verbose ones for recovery.
- **Takeaway:** with error-feedback, ~1–2 retries capture nearly all recoverable failures; beyond 2–3 is waste. NOT FOUND: a definitive published "optimal retry count" for JSON-schema validation specifically — the plateau-after-1 finding is the closest evidence. Note that with grammar-constrained outputs (Q2), *syntactic* retries become unnecessary; retries only remain for *semantic* validation (e.g., "field X must reference an existing table").

## 4. (B7/D2) Determinism — **VERIFIED**

- **OpenAI:** `seed` + `system_fingerprint` is explicitly **"best effort... determinism is not guaranteed"** ([OpenAI cookbook](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter), [Azure docs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reproducible-output?view=foundry-classic)); outputs can differ even with identical fingerprints. Newer reasoning models (GPT-5/o-series) don't expose temperature at all.
- **Anthropic:** **no seed parameter exists.** Temperature 0.0–1.0; docs note temp-0 is "not fully deterministic." Newer models go further: **Claude Opus 4.7+/Opus 5/Sonnet 5 reject `temperature`/`top_p`/`top_k` entirely (400)**; on Claude 4.5-era models you may set temperature *or* top_p, not both (verified via current Claude API reference, 2026-07-26).
- **Google:** Gemini **does** offer `seed` in `generationConfig` ([Vertex GenerationConfig docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/GenerationConfig)) — also explicitly best-effort, not guaranteed.
- **Why temp-0 isn't deterministic:** Thinking Machines' ["Defeating Nondeterminism in LLM Inference"](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) (Sep 2025) showed the root cause is **lack of batch invariance** — server batch size varies with load, floating-point reduction order changes, and tiny differences flip greedy argmax. Their [batch_invariant_ops](https://github.com/thinking-machines-lab/batch_invariant_ops) achieves bitwise reproducibility, and follow-ups ([LLM-42](https://arxiv.org/pdf/2601.17768), [MarginGate](https://arxiv.org/pdf/2605.30218), 2026) reduce its perf cost — but **no major API provider serves batch-invariant inference as of mid-2026**.
- **Fact-check D1 (`top_p:0` at temp 0):** **essentially a no-op where accepted, an error elsewhere.** At temp 0 decoding is already greedy, so top_p adds nothing; several Anthropic-compatible surfaces treat valid top_p as (0, 1] and [reject 0/out-of-range values](https://github.com/langfuse/langfuse/issues/12013), and newest Claude/GPT models reject the parameter outright. Verdict: **don't send it.** OpenAI accepts top_p:0 but [randomness persists anyway](https://community.openai.com/t/why-does-openai-api-behave-randomly-with-temperature-0-and-top-p-0/934104).
- **Fact-check D2 (seed best-effort only):** **TRUE** on both providers that offer it (OpenAI, Google); Anthropic offers none.

## 5. (C12) Small/fast model pricing & latency (mid-2026) — **VERIFIED prices / PARTIAL latency**

| Model | Input $/1M | Output $/1M | Notes |
|---|---|---|---|
| **Claude Haiku 4.5** (`claude-haiku-4-5`) | **$1.00** | **$5.00** | 200K ctx, 64K out (Anthropic pricing, verified via Claude API reference 2026-07-26) |
| **GPT-5 mini** | **$0.25** | **$2.00** | ([pricing trackers](https://pricepertoken.com/pricing-page/provider/openai), [CloudZero](https://www.cloudzero.com/blog/openai-pricing/)); GPT-5-nano from ~$0.05 in; GPT-4.1-mini legacy $0.40/$1.60 (being retired) |
| **Gemini Flash-Lite (3.x)** | **~$0.25** | **~$1.50** | [pricepertoken](https://pricepertoken.com/pricing-page/model/google-gemini-3.1-flash-lite-preview); full Gemini 3.5 Flash now $1.50/$9 — Flash has moved upmarket; Flash-Lite is the budget tier |

Latency (third-party benchmarks — treat as indicative): Haiku 4.5 TTFT ≈ **0.6 s** on medium prompts ([independent test](https://www.kunalganglani.com/blog/llm-api-latency-benchmarks-2026)); Gemini Flash family lowest TTFT (~0.35 s Flash-Lite) and highest throughput (**>200 tok/s**) ([ArtificialAnalysis comparisons](https://artificialanalysis.ai/models/comparisons/claude-4-5-haiku-vs-gpt-5-mini-minimal)); GPT-4.1-mini measured ~4× slower TTFT than Haiku in the same test. Providers don't publish official TTFT — **PARTIAL**.

## 6. Fine-tuning vs prompting a stronger model — **VERIFIED, with a major 2026 development**

- **OpenAI is winding down self-serve fine-tuning**: announced May 7, 2026 — no new orgs; inactive orgs cut July 2, 2026; **all new fine-tune jobs end Jan 6, 2027** ([tessl.io](https://tessl.io/blog/openai-shutting-fine-tuning-signals-for-enterprise-ai/), [OpenAI deprecations page](https://developers.openai.com/api/docs/deprecations)). Existing fine-tunes serve until base-model retirement. OpenAI's own guidance: prompt caching + small base models "match fine-tuned economics in most production workloads." Legacy training pricing was ~$0.80/1M tokens (4.1-mini).
- **Anthropic** offers no first-party fine-tuning for current Claude models. **Google** still offers supervised tuning for Gemini Flash on Vertex AI.
- **Break-even literature:** self-hosted fine-tuned 7B models cost 20–100× less than frontier APIs at ~1M conversations/month, with break-even reported around **~3 months** at high volume ([cost analyses](https://costlens.dev/blog/prompt-vs-fine-tune-the-2026-llm-efficiency-showdown), [aisuperior](https://aisuperior.com/cost-of-fine-tuning-llm/)); below ~millions of tokens/month, prompting wins.
- **Prompt-caching economics (verified):** OpenAI — automatic, **90% off cached input** on current models, no write surcharge, 1,024-token min ([leanlm](https://leanlm.ai/blog/prompt-caching)). Gemini — implicit caching, **90% off** on 2.5+ ([Google docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview)). Anthropic — explicit `cache_control`: reads **~0.1×** input price; writes **1.25×** (5-min TTL) or **2×** (1-h TTL); breaks even at 2 requests (5-min TTL). Caching an ~2–4K-token QuerySpec schema + few-shot prompt makes the "prompt a strong model" option far cheaper than 2024-era math assumed — which is precisely why OpenAI killed self-serve FT.

## Recommendations

**(a) Planner reasoning before JSON — yes.** Have the planner reason free-text first, then emit the QuerySpec under constrained decoding: either a two-phase prompt ("think, then emit"), or on Claude simply use extended/adaptive thinking + `output_config.format` (thinking runs unconstrained; only the final output is grammar-constrained). This matches the CRANE/2026 consensus and eliminates the Tam-et-al. degradation. Never put the answer field first in the schema.

**(b) Retry policy — max 2, with error feedback, semantic-only.** Use grammar-guaranteed structured outputs so JSON-syntax retries never happen. For semantic validation failures (bad column refs, impossible date ranges), retry **once** with the validator error appended (Instructor-style), optionally a second time; after 2 failures, fail over (to a stronger model or a human/default path). Evidence shows returns plateau after the first feedback retry.

**(c) Determinism stance — design for reproducibility, not bitwise determinism.** Treat all providers as best-effort: temp 0 (or omit sampling params entirely on newest Claude/GPT models, which reject them), **never send `top_p:0`** (no-op at best, 400 at worst — D1 confirmed), seed only on OpenAI/Gemini and only as variance reduction, log `system_fingerprint`/model version (D2 confirmed: best-effort). Get *system-level* determinism instead: validate against the schema, canonicalize the QuerySpec after parsing, and cache identical (prompt → QuerySpec) pairs so repeated queries are replay-deterministic.

**(d) Model shortlist:**

| Role | Primary | Alternative | Why |
|---|---|---|---|
| Planner | **Claude Sonnet-class or GPT-5** with structured outputs + thinking | Gemini Pro | Reasoning quality dominates; schema-constrained emit; prompt-cache the schema (90%/0.1× discounts) |
| Narrator | **Claude Haiku 4.5** ($1/$5, ~0.6 s TTFT) or **GPT-5 mini** ($0.25/$2) | **Gemini Flash-Lite** ($0.25/$1.50, fastest TTFT/throughput) | Short text, latency-bound; all three are more than adequate |
| Fine-tuning the planner | **Don't**, unless >millions of QuerySpecs/month | Gemini Flash tuning (Vertex) or self-hosted 7B if you must | OpenAI FT is being sunset (new jobs end Jan 2027); prompt-caching + few-shot on a strong base model is the durable path |
