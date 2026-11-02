# Site Map & Component/Class Atlas (Deep Dive)

Return a markdown section starting with `## 🗺️ Site Map & Component Atlas (Deep Dive)`.

You produce the **complete navigational and structural map** of the app. Use facts `routes`, `entry_points`, `import_graph` to enumerate, then read router/config/page source to confirm.

**Produce:**
1. **Site map** — every route/page/screen: a table (`route | page component | file | guards/auth | data it loads`) AND a Mermaid `flowchart TD` of the navigation flow (entry → auth → main areas → detail screens; label edges with the user action that triggers navigation).
2. **Class atlas** — a Mermaid `classDiagram` of all classes (UI classes, services, models, stores), with inheritance/implementation edges and one-line responsibility notes. If the codebase is mostly functions, map modules instead and say so.
3. **UI vs logic component map** — two lists: presentation components vs logic/state/service modules (hooks, stores, API clients, utils), each with file paths. Flag every file that mixes both concerns (`file:line` of the mixed responsibility).
4. **Wiring map** — which pages use which components use which services/queries/endpoints: a Mermaid `graph LR` with subgraphs `Pages | Components | Logic/Hooks | Server calls`.
5. **Flow gaps** — dead routes, unreachable pages, orphaned components (defined but never imported), duplicated flows. Cite each.

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
