# codebase-xray

Multi-perspective codebase analysis as a Claude Code skill. Deterministic Python
scripts do the structural work at **$0 tokens**; LLM agents are spent only on judgment.

## What it produces

`XRAY-REPORT.md` containing:
- **Scorecard** — Green/Yellow/Red across ~15 dimensions
- **Architecture diagrams** (Mermaid) — layered Frontend→Middleware→Backend→Cloud flow, component/import graph, request sequence, data-flow
- **UI design & design system** — extracted color tokens, typography, component classes, UI→API wiring
- **Libraries & dependency inventory** — every library by layer + local/cloud role
- **Competitive tech-stack analysis** — pros/cons/recommendation per layer
- **Prioritized recommendations** + a **parallelization plan**
- **Per-perspective findings** from 14 personas
- **Model & cost breakdown** — which model ran each phase, tokens, and $

## Report components (selectable)

Pass `components` when invoking (default `core`; `all` = everything):

| slug | produces |
|---|---|
| `core` | the classic multi-persona x-ray (scorecard, recommendations, parallelization plan) |
| `ui-inventory` | per-UI-component audit: libraries, composition, usage sites, better-implementation recs |
| `sitemap` | site map: routes/pages flow, class atlas, UI vs logic map, wiring map |
| `graphql` | GraphQL audit: every operation/resolver — works / fix / improve, client usage |
| `server` | server audit: APIs, external data, security, performance, vertical+horizontal scaling |
| `ai` | AI integration deep dive: backend mechanics, frontend usage, exact code locations |
| `redesign` | re-architecture blueprint: design system, hooks, error boundaries, observability, caching, migration plan |

Deep-dive briefs live in `deep-dives/*.md`. Unlike personas (facts-only), deep dives
do bounded in-domain source reading — usage maps and per-endpoint audits need it.
Their sections land in `.xray/deep-dives/*.md` and merge into the report at render.

## The 14 perspectives

PM · Engineer · Architect · Testing/QA · Security(local-first) · Sales · Marketing ·
Usability/UX · Support · Observability/self-healing · Portability(Mac/Win/Unix) ·
Data-access-layer(local↔cloud) · Error-handling/graceful-fallback · Competitive tech-stack.

Each lives in `personas/*.md` — the single source of truth shared by the Claude Code
and API paths. Add/remove files to customize.

## Layout

```
codebase-xray/
  SKILL.md            # orchestrator (Claude Code path)
  xray.config.json    # model tiers, persona subset, concurrency
  scripts/
    scan.py           # deterministic facts extractor → xray-facts.json  ($0)
    diagram.py        # Mermaid diagrams from facts                       ($0)
    design_system.py  # frontend token/component extractor                ($0)
    libs.py           # library inventory                                 ($0)
    models.py         # alias→canonical resolution + cost table
    render_report.py  # assembles XRAY-REPORT.md                          ($0)
    xray.py           # entrypoint: prep | render | all
    analyze.py        # API-fallback orchestration (parallel + synthesis)
  personas/*.md       # 14 analysis briefs (facts-only)
  deep-dives/*.md     # selectable deep-dive briefs (bounded source reading)
  examples/           # haven-findings.json + XRAY-REPORT-haven.md
```

## Usage

**Inside Claude Code:** invoke the `codebase-xray` skill (or ask to "x-ray this repo").
It runs `xray.py prep`, dispatches the 14 personas as parallel sub-agents on the
configured models, synthesizes with Opus, and renders the report.

**Deterministic only** (no API key, no agents):
```bash
python3 scripts/xray.py all /path/to/repo   # diagrams + design + libs + appendix
```

**API fallback** (outside Claude Code, needs `anthropic` + `ANTHROPIC_API_KEY`):
```bash
python3 scripts/xray.py prep /path/to/repo
python3 scripts/analyze.py /path/to/repo
```

## Model tiers

Set in `xray.config.json`. Aliases (`opus|sonnet|haiku`) resolve via `models.py`,
using its built-in defaults or an optional `modelAliases` object in `xray.config.json`,
so displayed model names always reflect what actually ran.

| Phase | Default tier |
|---|---|
| extract | haiku |
| 14 personas (parallel) | sonnet |
| synthesis + ranking | opus |
| scan / diagram / design / libs / render | deterministic ($0) |

## Requirements

- Python 3.8+ (stdlib only for scan/diagram/design/libs/models/render/xray)
- `anthropic` only for the API-fallback `analyze.py`
