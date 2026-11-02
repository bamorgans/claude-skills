---
name: codebase-xray
description: Use when the user wants a deep reverse-engineering report of a codebase — the full multi-persona x-ray, or one or more deep-dive components selected via the components parameter (ui-inventory, sitemap, graphql, server, ai, redesign). Triggers on "analyze this codebase", "reverse engineer", "x-ray this repo", "architecture report", "UI component inventory/report", "site map", "GraphQL audit", "server/API audit", "how is AI used", "redesign/re-architect the UI", "tech-stack analysis". Investigation only — never modifies target code. Minimizes token cost via deterministic Python scripts; agents are spent only on judgment.
---

# Codebase X-Ray

Produce an extensive, multi-perspective analysis report for any repository. **Deterministic Python scripts carry the structural/visual/library load at $0 tokens; LLM agents are spent only on judgment.** Always display which model each phase uses, and a full model/cost breakdown at the end.

## Operating principle (token minimization)

The scripts emit a compact `.xray/xray-facts.json`. **Every analysis agent reads that JSON (plus `design.json`/`libs.json`), never the raw repo.** That is the cost-control mechanism — do not let agents crawl the tree.

## Inputs

- **target**: path to analyze. Default to the current working directory if the user gives none.
- **components**: which report components to produce — one or more of the slugs below. Default `core`. Infer slugs from the user's words ("just the GraphQL audit" → `graphql`; "UI report and AI deep dive" → `ui-inventory,ai`; "everything"/"full audit" → `all`). Announce the resolved component list before running; if the request is genuinely ambiguous, ask.

  | slug | produces |
  |---|---|
  | `core` | the classic multi-persona x-ray: scorecard, prioritized recommendations, parallelization plan |
  | `ui-inventory` | per-UI-component audit: libraries used, what it composes, every usage site, better-implementation recs |
  | `sitemap` | complete site map: routes/pages flow, class atlas, UI vs logic component map, wiring map |
  | `graphql` | GraphQL audit: every operation/resolver — working / needs fix / improvement, client usage, fix list |
  | `server` | server-side audit: exposed APIs, external data connections, security, performance, vertical+horizontal scalability |
  | `ai` | AI integration deep dive: backend mechanics, frontend usage, exact call-site code locations, risks |
  | `redesign` | re-architecture blueprint: design system, presentational components, hooks, error boundaries, observability, caching, server/client separation, migration plan |
  | `all` | `core` + every deep dive |

- Config: `xray.config.json` (model tiers, persona subset, concurrency, default components). Model aliases resolve via `scripts/models.py`: built-in defaults, overridable by an optional `modelAliases` object in `xray.config.json`.

## Procedure

Create a TodoWrite list from these steps, then execute in order.

> **Resolving script paths.** Your working directory is the *target repo*, not this skill — so relative paths like `scripts/xray.py` will not resolve. This skill was launched with a "Base directory for this skill" line; set `XRAY=<that base dir>` once and prefix every script call with `$XRAY/scripts/`. The target repo path is a separate argument. (If you ever can't determine the base dir, locate it with `find ~/.claude -path '*codebase-xray/scripts/xray.py' 2>/dev/null | head -1`.)

### Step 1 — Deterministic prep ($0 tokens)
```
python3 $XRAY/scripts/xray.py prep <target>
```
This writes `<target>/.xray/{xray-facts.json, diagrams.md, design.json, design.md, libs.json, libs.md}`. Announce: `scan/diagram/design/libs: deterministic · $0`.

### Step 2 — Resolve and ANNOUNCE models
Read `$XRAY/xray.config.json` and resolve each phase with `models.py`:
```
python3 $XRAY/scripts/models.py
```
Print a table the user can see, e.g.:
```
extract    → Haiku 4.5
personas   → Sonnet 4.6   (×14, parallel)
deep dives → Sonnet 4.6   (×N requested, parallel)
synthesis  → Opus 4.8
```

### Step 3 — Dispatch the persona agents IN PARALLEL (`core` component only)

Skip Steps 3, 3.5 and 4 entirely if `components` does not include `core` (or `all`) — announce the skip and continue with Step 3b.
Use the **superpowers:dispatching-parallel-agents** skill. Dispatch in waves of `concurrency` (default 6).

**Adaptive subset:** unless `xray.config.json → personas` pins an explicit list, skip personas whose primary fact inputs are empty, and announce each skip ("skipping 📣 Marketing — no `docs_excerpt`, no routes"). Guide: sales / marketing / support need `docs_excerpt` or `routes`; usability-ux needs frontend files in `design.json`; data-access needs a non-empty `data_access` entry. Never skip: pm, engineer, architect, testing-qa, security, error-handling, observability, portability, competitive-stack.

For each remaining persona file in `$XRAY/personas/*.md`, spawn one `Agent` with:
- **model**: the resolved `persona` model (Sonnet by default). Pass it via the Agent `model` field so the dispatch is on the right tier — and so the displayed model is truthful.
- **prompt**: the contents of `$XRAY/personas/<n>.md` + the contents of `<target>/.xray/xray-facts.json` (and `design.json`, `libs.json`). Instruct the agent to return ONLY the JSON object the brief specifies (`{"name","model","findings":[...]}`; the competitive-stack persona also returns a `competitive` array).
- **Finding schema** (require it in every dispatch prompt): each finding is `{"severity":"red|orange|yellow|green","title","detail","citations":["<repo file:line or file>"],"confidence":0.0–1.0,"needs_verification":true|false}`.
- **Citation semantics:** citations are locations **in the target repo**, taken from the facts' location-bearing fields (`*_locations`, `network_binds`, `tests.files`, `largest_files`, `routes[].file`, `churn_hotspots[].file`, …) — NEVER line numbers of the facts JSON itself. If a fact is count-only, cite the facts key (e.g. `error_handling.todo_fixme`) and set `needs_verification: true`.
- Tell each agent: do not read the raw repo; reason from the facts provided. Consult `scan_coverage` before claiming something is absent — an empty `routes`/`import_graph`/`tests` list may mean the extractor doesn't support that stack, not that the thing doesn't exist; absence claims must carry `needs_verification: true`.

Announce each agent's model as you dispatch ("Dispatching 🔒 Security on Sonnet 4.6…"). Collect every agent's returned JSON.

### Step 3.5 — Verify red/orange findings (cheap, bounded)
A false red amplified through synthesis costs more than one `ls`. For every returned finding with severity `red` or `orange` AND `needs_verification: true`, run **at most one** cheap deterministic check yourself (Glob / `ls` / `grep -l` — max 10 checks total, no file reads, no crawling). Annotate the finding in place: `verified: true | false | "refuted"` plus a one-line `verification_note`. Downgrade refuted findings to `yellow`, keep the note — never silently drop them. This bounded pass is the ONLY sanctioned touch of the raw repo.

### Step 3b — Dispatch deep-dive agents IN PARALLEL (requested components only)

For each requested deep-dive component (`ui-inventory`, `sitemap`, `graphql`, `server`, `ai`, `redesign`), spawn one `Agent`:
- **model**: the resolved `deep_dive` tier (default sonnet). Announce it per dispatch, same as personas.
- **prompt**: the contents of `$XRAY/deep-dives/<slug>.md` + the target path + the contents of `<target>/.xray/xray-facts.json` (and `design.json`, `libs.json`).
- Dispatch deep dives in the SAME parallel waves as the personas (they are independent of them).

Deep dives are the sanctioned exception to the no-crawl rule: their briefs require using facts.json to *target* their reads, then reading the actual source files in their domain — per-component usage maps and per-endpoint audits cannot come from compact facts. Their outputs must cite repo `file:line` for every claim, and they NEVER modify the target repo (investigation only).

Each deep-dive agent returns ONLY a markdown section (starting with its `##` heading). Write each returned section verbatim to `<target>/.xray/deep-dives/<slug>.md` — the renderer merges them into the report automatically.

### Step 4 — Synthesis (Opus)
Spawn ONE `Agent` with the resolved `synthesis` model (Opus by default). Give it the facts + all persona JSON. Instruct it to return ONLY a JSON object with:
`verdict, executive_summary, scorecard[{dimension,status,note}], recommendations[{rank,severity,parallel,title,impact,effort,owners,evidence}], parallel_plan (markdown string with a wave plan of which recommendations can be worked in parallel), competitive[...]` (carry through the competitive persona's array).
Scoring: `priority = impact × cross-perspective agreement ÷ effort`. Weight `verified: true` findings above unverified ones; findings marked `refuted` MUST NOT drive any recommendation. Mark `parallel: true` for recommendations that touch independent file sets (dispatchable as parallel work streams).

### Step 5 — Assemble findings + render
Write the merged object (synthesis fields + `personas` array + a `models_used` array) to `<target>/.xray/findings.json`. If `core` was skipped, write just `{"models_used": [...]}` — the renderer defaults every synthesis field gracefully. Then:
```
python3 $XRAY/scripts/render_report.py <target>
```
This writes `<target>/XRAY-REPORT.md`, merging the deterministic fragments, the agent findings, and any `.xray/deep-dives/*.md` sections, and computing the real cost breakdown via `models.py`.

> **`models_used` row schema (exact — or the cost table renders $0).** `models.breakdown` reads these keys and NO others: each row is `{"phase": str, "model": "<alias|canonical id|deterministic>", "in": <input_tokens int>, "out": <output_tokens int>, "wall": "<e.g. 86s>"}`. Keys like `tokens`/`wall_s` are silently ignored and price to $0. Deterministic phases use `"model": "deterministic"`. **Claude Code subagents report a single combined `subagent_tokens` in their completion notification, not an input/output split** — record that figure in `out` (leave `in` at 0) so the phase is at least priced, and label the total "combined (input+output)" in your report-back. Sum the per-agent `subagent_tokens` across a wave for that wave's row. Parallel waves overlap, so `wall` is the wave's wall-clock, not the sum of per-agent durations.

### Step 6 — Report back
Tell the user the report path, the verdict, the top 3 recommendations, and the total cost. Show the model/cost breakdown table.

## Output

- `<target>/XRAY-REPORT.md` — the human report (scorecard, diagrams, UI/design system, libraries, competitive analysis, prioritized recs, parallelization plan, per-perspective detail, model/cost breakdown).
- `<target>/.xray/{xray-facts,findings,design,libs}.json` — machine-readable, for downstream tooling.

## API-fallback path (no Claude Code sub-agents)

If running outside an environment with the `Agent` tool, use:
```
python3 $XRAY/scripts/xray.py prep <target>
ANTHROPIC_API_KEY=… python3 $XRAY/scripts/analyze.py <target>   # parallel API calls + synthesis + render
```
Requires `pip install anthropic`. Same facts in, same report out.

## Rules
- **Investigation only.** The x-ray never modifies, creates, or deletes code in the target repo — the only writes are `<target>/.xray/**` and `<target>/XRAY-REPORT.md`. Pass this rule to every dispatched agent.
- Never let a *persona* agent skip the facts.json and crawl the repo — that defeats the cost design. (Exceptions: the orchestrator's own bounded Step 3.5 verification pass, and deep-dive agents, whose briefs sanction bounded in-domain source reading.)
- Always display the model used per phase, and the final breakdown. If a phase is deterministic, label it `$0`.
- Model aliases come only from `xray.config.json` (`modelAliases`, else the built-ins in `models.py`) — the displayed model names must reflect what actually ran.
- Degrade gracefully: if agents can't run, still produce the deterministic report (diagrams, design, libs, appendix) and say agent analysis was skipped.
- A red finding refuted in Step 3.5 must never appear in the top recommendations — report it as downgraded, with its `verification_note`.
- Facts honesty: `scan_coverage` in the facts declares what each extractor supports; personas and synthesis must treat empty lists for unsupported stacks as "not scanned", not "absent".
