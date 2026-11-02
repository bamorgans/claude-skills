# GraphQL Implementation Audit (Deep Dive)

Return a markdown section starting with `## 🕸️ GraphQL Implementation Audit (Deep Dive)`.

You audit the **entire GraphQL implementation**, server and client. Locate schema/resolvers/client operations via facts `routes`, `data_access`, `libs.json`, then read them.

**Produce:**
1. **Operation inventory** — every query, mutation, and subscription: table (`operation | type | resolver file:line | what it does | callers (client file:line)`).
2. **Per-endpoint verdict** — for each operation: ✅ working / ⚠️ needs fix / 🔴 broken, with evidence. Check specifically: N+1 resolver patterns, missing pagination on list fields, missing/inconsistent error handling, auth checks per resolver (or absent), over-/under-fetching by clients, unused schema fields, breaking nullability, input validation.
3. **Server wiring** — which GraphQL server library, how it connects to data sources (ORM/DB/REST/external APIs), context construction, dataloaders/batching or their absence. Mermaid `sequenceDiagram` of one representative request: client → transport → resolver → data source → response.
4. **Client usage** — which client (Apollo/urql/fetch), cache policy and normalization, where operations are colocated vs centralized, generated types or hand-rolled.
5. **Fix list & improvement list** — ranked: what must be fixed (bugs/security), then what should be improved (performance, schema design, codegen, caching, persisted queries). Pros/cons/effort per item.

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
- If the repo has no GraphQL at all, say so in three lines and describe what the API layer actually is instead — do not invent findings.
