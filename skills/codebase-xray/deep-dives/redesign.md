# Re-architecture & Redesign Blueprint (Deep Dive)

Return a markdown section starting with `## 🏗️ Re-architecture & Redesign Blueprint (Deep Dive)`.

You design the **target architecture for a UI redesign + re-architecture**, grounded in what actually exists. Read the current entry points, a representative page, a representative component, and the API client layer before prescribing anything.

**The target state to design toward** (adjust only with evidence):
- A **common design system**: tokens (color/type/spacing) + shared **presentation-only components**, **mobile-first and responsive**.
- **Hooks-based logic**: data fetching, state, and side effects live in custom hooks / stores — never inside presentational components.
- **Common patterns across the app**: one way to fetch, one way to handle forms, one way to route, one way to style.
- **Error handling everywhere**: error boundaries per route/feature, graceful degradation and graceful exit (no white screens; failed sections render fallbacks).
- **Observability designed-in**: structured logging, error reporting, performance/user tracing hooks at the boundaries.
- **Caching for speed**: HTTP/query cache (e.g. normalized GraphQL cache or query library), memoization where measured, and server-side caching where it pays.
- **Clean server/frontend separation**: typed API contract, no server logic in components, no UI assumptions in the server.

**Produce:**
1. **Gap analysis** — table: `target property | current state (file:line evidence) | gap | severity`.
2. **Target architecture Mermaid** — `flowchart TD` of the redesigned layers (design system → presentational components → hooks/state → API layer → server), plus a small before/after code sketch of ONE real component from this repo refactored into the target pattern (presentational + hook).
3. **Technology recommendations** — for each layer where the current choice is weak: candidate technologies with pros/cons and a single recommendation. Do not recommend churn where the current choice is fine — say "keep".
4. **Migration plan** — phased (Phase 0 foundations → strangler-pattern feature migration → cleanup), each phase with entry/exit criteria, effort, and which phases can run in parallel.
5. **Reskin vs re-architect split** — what a pure reskin could achieve alone vs what requires the re-architecture, so the redesign can be staged.

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
