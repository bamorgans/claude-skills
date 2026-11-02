# UI Component Inventory & Composition Audit (Deep Dive)

Return a markdown section starting with `## 🧩 UI Component Inventory (Deep Dive)`.

You audit **every UI component** in the target repo. Use `design.json` `inventory` + facts `routes`/`import_graph` to enumerate them, then read the actual component source files.

**For each component produce a row in a master table:**

| Component | File | Kind | Libraries used | Composes | Used by | Mobile/responsive | State/hooks | Verdict |

- **Kind**: class vs function; presentation-only vs logic-mixed vs container.
- **Libraries used**: every external UI/lib import (MUI, styled-components, CSS modules, etc.).
- **Composes**: child components it aggregates/renders.
- **Used by**: every usage site (`file:line`) — grep imports to find them all.
- **Mobile/responsive**: media queries / responsive props / fixed px? mobile-first or desktop-only?
- **State/hooks**: hooks used, lifecycle methods, direct data fetching inside the component (an anti-pattern for presentational components).

**Then add:**
1. A Mermaid `graph TD` **composition graph** (pages → containers → leaf components; group with subgraphs per feature area).
2. **Design-system extraction candidates** — repeated visual patterns (buttons, cards, form fields, modals, tables) that should become shared presentational primitives; list every duplicate implementation with `file:line`.
3. **Per-component recommendation** where the implementation is weak: better way to implement it or better technology to use (e.g. convert class → function + hooks, split logic into a custom hook, replace hand-rolled table with a headless library, replace inline styles with tokens). State pros, cons, effort (S/M/L).
4. A short **libraries verdict**: which UI libraries the components collectively depend on, overlaps/conflicts, and what a consolidated stack should be.

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
