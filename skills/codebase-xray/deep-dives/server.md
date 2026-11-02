# Server-Side & API Audit (Deep Dive)

Return a markdown section starting with `## 🖥️ Server-Side & API Audit (Deep Dive)`.

You audit the **server/backend and every API it exposes or consumes**. Locate via facts `routes`, `network_binds`, `data_access`, `env vars`, then read the server source.

**Produce:**
1. **API surface** — every exposed endpoint (REST/GraphQL/WebSocket/RPC): table (`method+path | handler file:line | auth? | validates input? | purpose`).
2. **External data connections** — every outbound connection: databases, third-party APIs, SDKs, queues, file storage: table (`system | client/lib | connection config file:line | credentials source | failure handling`).
3. **Security review** — authn/authz model and gaps, secrets handling (hardcoded? env? vault?), injection surfaces, CORS, rate limiting, dependency risk. Severity-tagged findings with citations.
4. **Performance review** — hot paths, blocking I/O, missing caching layers (and where a cache would pay off), payload sizes, connection pooling.
5. **Scalability verdict** — does it scale **vertically** (CPU/memory-bound points) and **horizontally** (in-process state, sticky sessions, local file writes, singleton jobs, DB as bottleneck)? State plainly what blocks horizontal scaling, with `file:line`.
6. **Frontend/server separation** — where server concerns leak into the frontend or vice versa; what a clean boundary would look like.
7. **Architecture Mermaid** — `flowchart LR` of client → server layers → external systems, marking sync vs async edges and trust boundaries.
8. **Pros / cons / recommendations** — ranked, each with effort (S/M/L).

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
