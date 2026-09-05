<div align="center">

<img src="docs/assets/logo.svg" width="116" alt="ScholarSeed — a seed sprouting from an open book with a verification checkmark"/>

# ScholarSeed

**The proof-carrying paper pipeline** — a deterministic [MCP server](https://modelcontextprotocol.io) + CLI + agent-skills toolkit that turns drafts into submittable academic manuscripts: **every citation verified against live databases, every statistical redline enforced, every gate output archived as evidence.**

[![CI](https://github.com/Morningstar202604/ScholarSeed/actions/workflows/ci.yml/badge.svg)](https://github.com/Morningstar202604/ScholarSeed/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/tag/Morningstar202604/ScholarSeed?label=release&sort=semver)](https://github.com/Morningstar202604/ScholarSeed/releases)
[![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-purple.svg)](LICENSE)
![Spec](https://img.shields.io/badge/spec-Agent%20Plugins%201.0-8A2BE2.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**41 deterministic MCP tools · 5 pipeline skills · calibrated on 70 real arXiv papers · zero dependencies (pure Python stdlib)**

Sister project of [AgentSeed](https://gitcode.com/badhope/AgentSeed): AgentSeed keeps code honest, ScholarSeed keeps papers deliverable — **write with any AI you like, submit only through gates that can prove the manuscript is clean.**

> 🇨🇳 中文文档：[README.zh-CN.md](README.zh-CN.md)

</div>

---

## Table of Contents

- [Why ScholarSeed](#why-scholarseed)
- [How It Works](#how-it-works)
- [The Writing Pipeline](#the-writing-pipeline)
- [Writing Self-Check, Not a Verdict Machine](#writing-self-check-not-a-verdict-machine)
- [Quick Taste](#quick-taste)
- [Workflows: What Should I Run?](#workflows-what-should-i-run)
- [Core Capabilities](#core-capabilities)
- [Skills](#skills)
- [MCP Tools](#mcp-tools)
- [Corpus Benchmark](#corpus-benchmark)
- [Install](#install)
- [CLI (no agent required)](#cli-no-agent-required)
- [Documentation Index](#documentation-index)
- [FAQ](#faq)
- [Compatibility · Scope & Limitations · Development · Security](#compatibility)

## Why ScholarSeed

Drafting stopped being the bottleneck of academic writing — any LLM produces a workable first draft in minutes. **Getting a manuscript accepted is the bottleneck**: hallucinated references trigger desk rejections, `p=0.000` and missing effect sizes draw reviewer fire, broken figure numbering and mixed citation styles read as carelessness, and institutions increasingly gate submissions with AIGC rules.

ScholarSeed is built around that asymmetry:

| | Generic AI writing assistants | ScholarSeed |
|---|---|---|
| What it does for you | Produces prose (quality varies with the model) | **Decides whether prose can be delivered** — reproducible rules with file/line evidence |
| Citation truthfulness | Whatever the model remembers | **Live Crossref / Semantic Scholar / OpenAlex verification, A/B/C graded, CI-gateable** |
| Statistics | Model's best guess | **Redline checker**: test name near every p-value, `p=0.000` rewrite, effect size + CI required for significance claims, sample-partition sum consistency |
| Reproducibility | Changes silently with the model | **Same input → same report**, every time |
| Runs where | Cloud app | Anywhere Python 3.9+ runs: laptop, lab server, CI pipeline, air-gapped machine |
| Dependencies | Proprietary | Zero (pure stdlib) |

**Positioning in one sentence:** ScholarSeed is the Ruff/ESLint of academic writing — a proof-carrying gate layer between *"the draft is done"* and *"the manuscript can be submitted."*

## How It Works

One engine, two surfaces:

```
                       ┌─────────────────────────────────────────┐
   Manuscript (.md /   │            Deterministic Engine          │
   .tex / best-effort  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
   .pdf)               │  │ Citations│ │  Gates   │ │ Reporting│ │
   ┌────────────┐      │  │ Crossref │ │ style·num│ │ score 0- │ │
   │  MCP server ├─────┼─▶│ S2       │ │ stats·fig│ │ 100+A/B/C│ │
   │ (41 tools)  │JSON │  │ OpenAlex │ │ traces…  │ │ evidence │ │
   └────────────┘      │  └────┬─────┘ └──────────┘ └──────────┘ │
   ┌────────────┐      │       │ disk cache                       │
   │    CLI     ├──────┼───────┘ TTL 24h (tunable)                │
   │ (humans/CI)│      │  exit codes 0 ok · 1 gate fail · 2 input │
   └────────────┘      └─────────────────────────────────────────┘
```

1. **Same engine everywhere.** `scripts/paper_tools.py` exposes 41 tools over the Model Context Protocol (for Cursor/Claude/Codex/any MCP client); `scripts/cli.py` drives the identical functions for humans and CI scripts. No behavior drift between the two.
2. **Deterministic rules, not vibes.** Every gate is a reproducible rule: same input always yields the same findings, each with line numbers you can verify by hand.
3. **Live sources, cached.** `citation_verify` / `verify_references` / `lit_search` / `journal_search_openalex` hit real APIs (Crossref, Semantic Scholar, OpenAlex) through a disk cache (default TTL 24h, `SCHOLARSEED_CACHE_TTL` to tune, `0` disables).
4. **Honest degradation.** When something can't be checked reliably (e.g., CID-encoded Chinese PDFs), reports say so explicitly instead of guessing.
5. **Gate-ready.** Exit codes and `--fail-on` thresholds make any check a hard gate in CI or an agent workflow.
6. **Plugin-shaped.** Follows Agent Plugins 1.0: drop the folder into your client's plugin directory; skills and the MCP server auto-discover. `validate_plugin.py` enforces spec conformance and single-source versioning.

## The Writing Pipeline

The five bundled skills turn 41 tools into a pipeline (topic → literature → outline → drafting → citation verification → polish → pre-submission review → publish). The agent writes prose; the skills force a tool gate at every stage and forbid advancing until it passes:

| Pipeline stage | Gate tool | Pass condition |
|---|---|---|
| Literature survey | `verify_references` | no grade-C (unconfirmed) entries survive |
| Outline & drafting | `render_template` / `word_count` / `word_budget` | genre structure present, section budgets on target |
| Citations | `format_citation` + `citation_verify` | entries generated **only** from verified Crossref metadata |
| Polishing | `check_style` + `check_ai_signature` | AI-flavored phrasing rewritten as plain academic prose |
| Delivery | `proofread` / `audit_paper` | **ERROR count must be zero** |
| Integrity | `check_stats` / `check_numbers` | statistical redlines and partition sums clear |

Every gate's machine output is attached to the delivery as evidence — *"it passed"* is never claimed without the report.

## Writing Self-Check, Not a Verdict Machine

Two instruments ship for **polishing your own draft** — neither claims to judge anyone:

- **`check_ai_signature` — style lint (heuristic hint).** Scores 0–100 how strongly prose resembles typical LLM output patterns: sentence-length burstiness (CV), MATTR lexical richness, 51 curated template phrases (*underscores the importance, multifaceted nature…* — grounded in Liang et al. 2024), transition openers, em-dash density. Every hit carries a line number. Texts under 8 sentences return "too short to evaluate" instead of a guess. Use it to rewrite template-y paragraphs into plain prose — as a writing-quality aid, not a detector.
- **`check_tamper_traces` — artifact forensics (objective fact).** Finds invisible characters your draft may have picked up from processing tools and copy-paste chains: zero-width/invisible characters (U+200B/200C/200D/2060/FEFF, soft hyphens), Cyrillic/Greek homoglyphs injected inside Latin words (`аpproach`; genuine Russian/Greek passages auto-exempt), abnormal in-line whitespace runs (RAID-benchmark attack signatures, Dugan et al., ACL 2024). Finding traces proves the text was processed by unusual tooling — it does **not** prove who wrote it.

We deliberately refuse to output a single "AI %" verdict — that number is scientifically indefensible (Stanford researchers measured a 61.3% false-positive rate on non-native English writers, Liang et al., *Patterns* 2023; no tool exceeded 80% accuracy in Weber-Wulff et al. 2023). Detection *recall* on deliberately evasive AI text is likewise unmeasured and unpublished — see [docs/CAPABILITY-ASSESSMENT.md](docs/CAPABILITY-ASSESSMENT.md) for the honest measured numbers.

> Full methodology and competitor landscape: [docs/AI-DETECTION-LANDSCAPE.md](docs/AI-DETECTION-LANDSCAPE.md)

## Quick Taste

Hand your manuscript to `audit_paper` and get a full health report in seconds:

```markdown
# Paper Audit Report (audit_paper)

Score: **85 / 100**

ERROR 0 · WARNING 5 · INFO 3  |  AI-likeness 41/100 (medium)  |  genre [empirical]

- [WARNING] 'p=0.000' should be written as p<0.001
- [WARNING] Reference [2] is never cited in text
- [WARNING] Partition sum 180 + 200 = 380 exceeds stated total 300
- [INFO] Absolute term '显然/obviously' — confirm direct evidence
```

And the citation gate, against the live Crossref API:

```
$ python scripts/cli.py citation 10.1038/nature14539
grade=A  "Deep learning"  (Nature, 2015)          ← real paper, fields match
$ python scripts/cli.py citation 10.1234/fake.journal.2026
grade=C  HTTP 404: Not Found                      ← fabricated DOI blocked
```

## Workflows: What Should I Run?

**Graduate student finishing a thesis**
```bash
python scripts/cli.py project ./thesis-chapters     # merge chapters, cross-chapter audit
python scripts/cli.py verify-refs thesis.md --fail-on C   # no unverified citations survive
python scripts/cli.py proofread thesis.md           # full-text gate sweep
```

**Researcher preparing a journal submission**
```bash
python scripts/cli.py audit-paper paper.md --genre empirical --journal top_empirical
python scripts/cli.py format-citation 10.1038/nature14539 --style apa   # verified entries only
python scripts/cli.py check abstract paper.md        # purpose/methods/results/conclusion coverage
```

**Lab running delivery gates in CI**
```yaml
- name: Citation gate
  run: python scripts/cli.py verify-refs paper.md --fail-on B   # exit 1 blocks the PR
```

**Writer polishing an AI-assisted draft**
```bash
python scripts/cli.py check style draft.md          # locate AI-flavored phrasing, rewrite by hand
python scripts/cli.py check tamper draft.md         # confirm no invisible artifacts remain
```

End-to-end pipeline (topic → submission): use the bundled skills — `literature-search` → `paper-writing` → `paper-review` → `paper-publish`, calling the MCP tools at every gate.

## Core Capabilities

- **Citation existence verification** (`citation_verify`): real-time Crossref lookup with DOI precision matching, title-similarity threshold to prevent false matches, field-level cross-check (authors/year), and A/B/C grading consistent with the literature checklist.
- **Batch reference gating** (`verify_references`): per-entry DOI-first lookup with title fallback; Markdown summary report with A/B/C counts. The mandatory gate before delivery/submission.
- **Real literature search** (`lit_search`): Semantic Scholar API with automatic backoff retry on rate limits; optional `SEMANTIC_SCHOLAR_API_KEY` env var for higher quota.
- **Live journal discovery** (`journal_search_openalex`): OpenAlex API search across any discipline — journal name, publisher, works count, citations, h-index, ISSN, OA status.
- **Built-in journal matcher** (`journal_matcher`): curated 20-journal database (management / IS / AI / medicine / ethics) stored in editable `data/journals.json`.
- **Deterministic writing tools**: template rendering with target-length planning, word counting, heading structure validation, outline generation, literature and submission checklists.
- **Skill knowledge base**: the end-to-end pipeline skills that sequence the tools and enforce the gates.

## Skills

Five knowledge-base skills ship alongside the tools (auto-discovered under `skills/`):

| Skill | What it does |
|-------|--------------|
| `paper-writing` | **The pipeline orchestrator**: topic → literature → outline → chapter drafting → figures → citation verification → polish → self-check, with a mandatory tool gate at every stage and an evidence chain attached to the delivery |
| `literature-search` | Multi-database search strategy, PRISMA-style screening, citation cross-validation, citation-inflation auditing |
| `paper-review` | Pre-submission review in a picky-reviewer + copy-editor dual perspective: claim-evidence alignment, reviewer's 10 questions, red-team stress test, BLOCKER/WARNING/OK report |
| `paper-card` | Deep-read one paper into a structured 16-section evidence card (problem → method → evidence chain → conclusion boundaries → critique) |
| `paper-publish` | Platform-fit adaptation and full submission pipeline: metadata, cover letter, ethics compliance, revision handling |

## MCP Tools

**Live verification & search**

| Tool | Description |
|------|-------------|
| `citation_verify` | Crossref existence check: DOI precise match or title search with similarity threshold; field cross-checks; A/B/C grade |
| `verify_references` | **Batch reference verification**: per-entry DOI-first lookup with title fallback; Markdown summary with A/B/C counts. Mandatory gate before delivery/submission |
| `format_citation` | **Citation entry formatter**: verify via Crossref then emit APA 7 / GB-T 7714 / IEEE / MLA 9 / Chicago / BibTeX entries; no entry unless verified (anti-hallucination gate) |
| `lit_search` | Semantic Scholar paper search: title/authors/year/abstract/citations/DOI |
| `journal_search_openalex` | OpenAlex live journal search across all disciplines |
| `literature_checklist` | Per-entry verification checklist from references (A/B/C grading, DOI status) |
| `journal_matcher` | Heuristic journal recommendations by topic keywords and paper type |

**Full-text gates**

| Tool | Description |
|------|-------------|
| `check_style` | Style gate: AI-flavor words, colloquialisms, filler phrases, overclaims, long paragraphs/sentences (with line numbers) |
| `check_punctuation` | Punctuation: CJK/Latin half-full-width mixing (code blocks ignored) |
| `check_figures_tables` | Figure/table integrity: numbering gaps, caption ↔ in-text reference mismatch |
| `check_terms` | Terminology: undefined acronyms, unused definitions, inconsistent variants; common acronyms exempt |
| `check_duplicates` | Duplicates: identical normalized sentences appearing multiple times |
| `check_references_format` | Reference format: duplicates, future years (hallucination signal), mixed APA/GB-T/IEEE styles |
| `check_intext_citations` | **Bidirectional in-text ↔ reference-list check**: numeric [1]/[2,5]/[3-7] cross-check (phantom citations / orphan entries / duplicate numbers), author-year matching, style-mix warning |
| `check_sections` | Genre-aware required-sections completeness + keywords line presence/count |
| `check_numbers` | **Numeric consistency engine**: same-keyword sample-size conflicts, partition ("of which… another…") sum overflow, percent-sum overflow, ratios >100% — classic fabrication signals |
| `check_hedging` | Per-section assertion-strength profile: absolute terms vs hedges; dense unhedged sections flagged |
| `check_stats` | **Statistical reporting redlines**: test name near every p-value, out-of-range & p=0.000 fixes, significant claims require effect size + CI |
| `check_abstract` | **Abstract four-element check**: purpose/methods/results/conclusion coverage, length band, quantified-numbers presence for empirical papers |
| `check_title` | **Title quality**: length band, vague wording, all-caps conventions, question-form and subtitle hints |
| `check_structure` | Validates heading level continuity (ignores fenced code blocks) |
| `word_count` | Counts Chinese characters, English words, code blocks after stripping Markdown; body-only caliber (references excluded) |

**Self-check instruments**

| Tool | Description |
|------|-------------|
| `check_ai_signature` | **AI-writing style lint**: sentence-length burstiness, MATTR lexical richness, 51-phrase template density, transition openers, em-dash density → 0-100 score + per-item evidence (heuristic hint, refuses too-short texts) |
| `check_tamper_traces` | **Tamper-trace forensics**: zero-width/invisible chars, Cyrillic/Greek homoglyphs inside Latin words (genuine Russian/Greek auto-exempt), in-line whitespace runs — objective processing-artifact evidence, never a style verdict |
| `check_self_plagiarism` | **Cross-document self-overlap**: n-gram overlap vs a corpus directory of past manuscripts (.md/.txt/.tex) — thesis chapter reuse, series template sentences. Legit reuse also hits; human judgement required |

**Composite audits & scaffolding**

| Tool | Description |
|------|-------------|
| `proofread` | **Composite gate entry**: runs all checkers + structure validation, one ERROR/WARNING/INFO report (`format=json` for structured output) |
| `audit_paper` | **One-shot full audit**: all checkers + style lint + artifact forensics + section completeness + stats integrity + optional word budget → heuristic score (0-100), fmt=json; `brief=true` returns errors-only compact verdict for agent loops |
| `audit_project` | **Multi-file thesis audit**: merges chapter files in natural order → per-chapter word table + full gate suite on merged text (cross-chapter acronyms, self-repetition, citation cross-check) |
| `audit_pdf` | **PDF submission audit (best-effort)**: stdlib-only text extraction then style/duplication/hedging/numbers/stats subset; unreliable checks honestly marked as skipped |
| `render_template` | Genre-based Markdown templates (survey/empirical/tech/thesis/argumentative) with optional journal length planning |
| `generate_outline` | Structured outline by genre |
| `word_budget` | Per-section word counts vs journal length targets (same source as render_template) |
| `submission_checklist` | Pre-submission checklist (journal fit, ICMJE authorship, cover letter, ethics & AI disclosure) |
| `next_actions` | **Agent plan router**: ordered JSON plan (tool / params template / pass condition per step) for a goal — submission / thesis / polish — so the agent drives the pipeline step by step |
| `gate_suite` | **Composite gate suite**: runs all (or selected) offline deterministic checkers in one call, unified JSON verdict (pass = zero errors) + blocking list — the primitive for agent fix-then-rerun loops |
| `audit_delta` | **Fix-delta comparison**: same gate bundle on before/after manuscripts, reports fixed vs introduced vs persisted findings with a net-improvement verdict |
| `check_references_completeness` | **Reference completeness**: missing year/source/volume-pages per entry, CJK entries without GB-T 7714 type markers, malformed DOIs (bad registrant length, embedded spaces, trailing punctuation) |
| `check_references_recency` | **Literature recency**: median reference age and stale ratio; flags all-stale or 70%+ older-than-10-years reviews |
| `check_placeholders` | **Unfinished-work traces**: TODO / FIXME / ??? / [citation needed] / 待补充 — must be zero before delivery |
| `check_links` | **Link trustworthiness**: placeholder domains (example.com/localhost), reserved TLDs, hostless URLs offline; `live=true` HEAD-verifies each URL (404/410 = dead link) |
| `check_vague_attribution` | **Vague attribution**: sentences appealing to unnamed authorities ("studies show", "experts agree", 人们普遍认为) with no citation in the same sentence — the polished-but-vague hallmark of AI text; exempt when a citation appears in-sentence |

LaTeX support: word_count / check_structure / proofread / audit_paper accept `source_format=latex` — commands/math/comments stripped, section structure restored.

All external API calls are disk-cached (default TTL 24h, tunable via `SCHOLARSEED_CACHE_TTL`, `0` disables).

## Corpus Benchmark

Gate thresholds calibrated on **70 arXiv papers across 9 disciplines**: all 70 scored in the low band of the style lint (zero false alarms on the human corpus), median audit score 82 with healthy spread. Measured honestly: **this is a negative-sample benchmark only** — detection recall on AI-written positives is not yet measured (planned; see [docs/ROADMAP.md](docs/ROADMAP.md)). See [docs/CORPUS-BENCHMARK.md](docs/CORPUS-BENCHMARK.md).

## Install

1. Drop this folder into your client's plugin directory.
2. Restart the client; skills under `skills/` and the MCP server in `mcp.json` are auto-discovered.
3. Verify: `python scripts/validate_plugin.py` prints `PASS`.

No pip install, no virtualenv, no compiled extensions — if `python` runs, ScholarSeed runs.

### Repositories & Mirrors

| Platform | URL | Notes |
|----------|-----|-------|
| GitCode (primary) | <https://gitcode.com/badhope/ScholarSeed> | Mainline development; file Issues/PRs here |
| GitHub mirror | <https://github.com/Morningstar202604/ScholarSeed> | Sync mirror (releases & star history tracked here) |

## CLI (no agent required)

Same engine as the MCP server, usable by humans and CI pipelines:

```bash
python scripts/cli.py version
python scripts/cli.py proofread paper.md --genre empirical
python scripts/cli.py verify-refs paper.md --fail-on C   # CI gate: exit 1 if unverified refs remain
python scripts/cli.py citation 10.1038/nature14539 --style gbt
python scripts/cli.py check abstract paper.md            # single gates: style/numbers/stats/tamper/...
python scripts/cli.py project ./thesis-chapters          # multi-file thesis audit
```

Exit codes: `0` ok · `1` gate failed (`--fail-on`) · `2` input error. Zero dependencies.

## Documentation Index

| Doc | Contents |
|-----|----------|
| [CORPUS-BENCHMARK](docs/CORPUS-BENCHMARK.md) | Threshold calibration on 70 real papers; anti-overfitting rules |
| [CAPABILITY-ASSESSMENT](docs/CAPABILITY-ASSESSMENT.md) | Measured capability, adversarial probes, upgrade paths |
| [AI-DETECTION-LANDSCAPE](docs/AI-DETECTION-LANDSCAPE.md) | Academic & industry detection landscape; what to trust and what not to |
| [VERSIONING](docs/VERSIONING.md) | SemVer policy, single-source versioning, release discipline |
| [SECURITY](SECURITY.md) | Threat model, credential policy |
| [CHANGELOG](CHANGELOG.md) | Notable changes |

## FAQ

**Is this an AI-writing assistant?**
It is the quality-gate layer *around* AI-assisted writing. The bundled skills sequence any LLM through the writing pipeline; ScholarSeed's own 41 tools never generate prose — they verify, gate, and archive evidence.

**Is it an AI detector like GPTZero?**
No. It ships a *style lint* (to polish your own draft) and *artifact forensics* (objective processing traces). It refuses to output a single "AI %" verdict — that number is scientifically indefensible, and recall on evasive text is unmeasured (see [Why ScholarSeed](#why-scholarseed)).

**Can it prove a citation doesn't exist?**
It verifies existence against Crossref/Semantic Scholar in real time and grades it A/B/C. Grade C means "unconfirmed," which is exactly what should block a submission until resolved.

**Does it send my manuscript anywhere?**
Only reference titles/DOIs go to public scholarly APIs during verification, through a local disk cache. Full-text checking is entirely offline.

**What languages does it support?**
English and Chinese text are first-class (bilingual lexicons throughout); LaTeX and Markdown inputs are first-class formats; PDF extraction is best-effort.

**Why zero dependencies?**
So it runs on any machine with Python — lab servers, student laptops, air-gapped review environments, CI containers — with nothing to break and nothing to audit beyond our code.

**How do I trust the heuristics aren't tuned ad hoc?**
Thresholds may only change with corpus-level regression re-runs (anti-overfitting rules in CORPUS-BENCHMARK.md), enforced through 237 unit tests and a release gate in CI on Python 3.9–3.13.

## Compatibility

Works with clients supporting Agent Plugins 1.0: ChatGPT, Codex, Cursor, GitHub Copilot, Kiro, VS Code, etc.

### Scope & Limitations

- **Input formats**: Markdown / LaTeX sources are first-class; PDF extraction is best-effort and does not support CID/CJK-encoded Chinese PDFs — provide Markdown/LaTeX sources for Chinese papers.
- **Nature of findings**: full-text gates are deterministic heuristics — hints for human review, not verdicts. Citation tools (`citation_verify`/`verify_references`) return live API results and can gate delivery directly.
- **Style-lint recall**: the statistical profile catches typical LLM patterns; deliberately evasive text can pass it — treat low scores as "nothing obviously template-y," not proof of human authorship.
- **No auto-submission**: no journal system integration; submission is executed by the author.

## Development

```bash
python scripts/validate_plugin.py        # plugin spec validation
python -m unittest discover -s tests -v  # unit tests (237)
python benchmarks/adversarial_suite.py   # adversarial regression (RAID-style attacks)
python scripts/release_gate.py           # release gate (validate + tests)
```

CI runs the release gate on Python 3.9–3.13 via GitHub Actions (on the GitHub mirror; GitCode is mainline development without runners — one pipeline, no platform-specific duplicates to drift or break).

## Security

No credentials bundled. Live submission requires your own platform logins/API keys. Agent Plugins 1.0 defines no permission model or sandbox — review third-party plugins before installing. See [SECURITY.md](SECURITY.md).

## License

[PolyForm Noncommercial 1.0.0](LICENSE) © 2026 ScholarSeed contributors — free for research, learning, and personal use; commercial use requires a separate license from the maintainers.

## Support

If ScholarSeed saved you time hunting references or proofreading drafts, one click below helps other researchers find it:

<div align="center">

[![Star ScholarSeed](https://img.shields.io/badge/%E2%AD%90_Star_this_repo-FBBA00?style=for-the-badge)](https://github.com/Morningstar202604/ScholarSeed/stargazers)
[![Report an issue](https://img.shields.io/badge/%F0%9F%90%9B_Report_an_issue-2EA043?style=for-the-badge)](https://gitcode.com/badhope/ScholarSeed/issues)
[![Fork & contribute](https://img.shields.io/badge/%F0%9F%8D%B4_Fork_%26_contribute-0969DA?style=for-the-badge)](CONTRIBUTING.md)

[![Star History Chart](https://api.star-history.com/svg?repos=Morningstar202604/ScholarSeed&type=Date)](https://star-history.com/#Morningstar202604/ScholarSeed&Date)

</div>

## Keywords

paper writing pipeline · citation verification · reference checker · research integrity · academic writing · thesis audit · LaTeX proofreading · submission checklist · hallucination prevention · research tools · MCP server · Model Context Protocol · statistical reporting · reference formatting · Crossref · Semantic Scholar · anti-plagiarism · scholarly writing · dissertation checklist · research ethics · AIGC compliance · CI quality gate

## AIGC Disclosure

This repository's documentation was produced with generative-AI assistance; content-provenance identifiers are disclosed in [README.zh-CN.md](README.zh-CN.md) (Chinese platform compliance labels).
