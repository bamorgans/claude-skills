# AI Integration Deep Dive

Return a markdown section starting with `## 🤖 AI Integration Deep Dive`.

You map **exactly how AI is used** in this codebase — backend mechanics, frontend consumption, and precise code locations. Locate via `libs.json` (AI SDKs), facts `env vars`/`data_access`, and grep-style targeting of provider names/model ids; then read those files.

**Produce:**
1. **AI call inventory** — every place the code calls a model/provider: table (`purpose | provider+model | call site file:line | prompt source file:line | streaming? | error handling?`).
2. **Backend mechanics** — for each AI feature: how the request flows (trigger → prompt construction → provider call → post-processing → storage/response). What's in the prompts (templates, injected user data, system prompts — cite them). Retries, timeouts, token/cost controls, logging of AI calls, evals/tests of AI output (usually absent — say so).
3. **Frontend usage** — which components/hooks trigger AI features and render results; loading/streaming UX; how errors from the AI path surface to the user. Cite `file:line`.
4. **End-to-end Mermaid `sequenceDiagram`** — user action → frontend → backend → AI provider → response render, for the primary AI feature.
5. **Risk review** — prompt injection surfaces (user data concatenated into prompts), PII sent to providers, unbounded cost paths, missing fallbacks when the provider is down, stale model ids.
6. **Recommendations** — better patterns (centralize the AI client, structured outputs, caching identical calls, observability on tokens/cost/latency, guardrails), each with pros/cons/effort.

---
**Deep-dive grounding rules:**
- Start from `<target>/.xray/xray-facts.json` + `design.json` + `libs.json` to locate targets; then read the real source files in your domain. Do not crawl unrelated directories.
- Every claim cites `file:line` (or `file`) in the target repo. No uncited assertions.
- This is an investigation: NEVER modify, create, or delete any file in the target repo.
- Return ONLY the markdown section. Tables for inventories, Mermaid for structure, short prose for judgment. Every recommendation states pros, cons, and effort (S/M/L).
- If the repo has no AI integration, say so in three lines — do not invent findings.
