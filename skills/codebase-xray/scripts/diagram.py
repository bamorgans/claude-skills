#!/usr/bin/env python3
"""
diagram.py — generate Mermaid architecture diagrams from xray-facts.json.

NO LLM calls, $0 tokens. Produces a markdown fragment with:
  - Layered flow (Frontend -> Middleware -> Backend -> Cloud)
  - Container view
  - Component / import graph
  - Request/workflow sequence
  - Data-access / local-first flow

Usage:
    python diagram.py <facts.json> [--out <diagrams.md>]
"""
import argparse
import json
import sys
from pathlib import Path

FRONTEND_EXT = {".html", ".css", ".scss", ".vue", ".svelte", ".jsx", ".tsx"}


def _has_frontend(facts):
    by = facts["inventory"]["by_ext"]
    return any(e in by for e in FRONTEND_EXT)


def _security_modules(facts):
    mods = []
    for e in facts["import_graph"]:
        if e["to"] == "security" and e["to"] not in mods:
            mods.append("security")
    # also infer from routes/file names
    return mods


def layered_flow(facts):
    binds = facts["security"]["network_binds"]
    bind_note = "  ⚠ binds 0.0.0.0" if binds else ""
    routes = facts["routes"]
    nroutes = len(routes)
    cloud = facts["security"]["cloud_sdks"]
    local = facts["security"]["local_ai"]
    vdb = facts["data_access"]["vector_db"]
    sql = facts["data_access"]["sql"]

    fe = '["dashboard / UI<br/>frontend"]' if _has_frontend(facts) else '["client / CLI"]'
    cloud_node = " · ".join(cloud) if cloud else "external API"
    local_node = " · ".join(local) if local else "local compute"
    stores = []
    if vdb: stores.append(f'VDB[("{" · ".join(vdb)}")]')
    if sql: stores.append(f'SQL[("{" · ".join(sql)}")]')

    lines = [
        "```mermaid",
        "flowchart TB",
        f'  subgraph L1["① FRONTEND"]',
        f"    FE{fe}",
        "  end",
        f'  subgraph L2["② MIDDLEWARE — API{bind_note}"]',
        f'    API["{nroutes} routes"]',
        "  end",
        '  subgraph L3["③ BACKEND — services + stores"]',
        '    SVC["services / agents"]',
    ]
    lines += [f"    {s}" for s in stores]
    lines += [
        "  end",
        '  subgraph L4["④ AI / EXTERNAL COMPUTE"]',
    ]
    if local:
        lines.append(f'    LOCAL["{local_node}<br/>LOCAL"]')
    if cloud:
        lines.append(f'    CLOUD["{cloud_node}<br/>CLOUD"]')
    lines += [
        "  end",
        "  FE -->|REST| API",
        "  API --> SVC",
    ]
    for s in stores:
        lines.append(f"  SVC --> {s.split('[')[0]}")
    if local:
        lines.append("  SVC --> LOCAL")
    if cloud:
        lines.append("  SVC -. fallback / external .-> CLOUD")
    lines.append("```")
    return "\n".join(lines)


def component_graph(facts):
    edges = facts["import_graph"]
    if not edges:
        return "_No internal module edges detected._"
    lines = ["```mermaid", "flowchart LR"]
    seen = set()
    for e in edges[:40]:
        a, b = e["from"], e["to"]
        key = (a, b)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'  {_id(a)}["{a}"] --> {_id(b)}["{b}"]')
    lines.append("```")
    return "\n".join(lines)


def _id(name):
    return "n_" + "".join(c if c.isalnum() else "_" for c in name)


def workflow_sequence(facts):
    routes = [r for r in facts["routes"] if r["method"] in ("POST", "ANY")]
    entry = routes[0]["path"] if routes else "/run"
    cloud = facts["security"]["cloud_sdks"]
    local = facts["security"]["local_ai"]
    compute = (local[0] if local else "") + ((" → " + cloud[0]) if cloud else "")
    compute = compute or "compute"
    return "\n".join([
        "```mermaid",
        "sequenceDiagram",
        "  actor U as User",
        "  participant FE as Frontend",
        "  participant API as API",
        "  participant SVC as Service/Agent",
        f"  participant M as {compute}",
        "  U->>FE: request",
        f"  FE->>API: {entry}",
        "  API->>SVC: dispatch",
        "  SVC->>M: invoke",
        "  M-->>SVC: result",
        "  SVC-->>FE: response",
        "```",
    ])


def data_flow(facts):
    vdb = facts["data_access"]["vector_db"]
    sql = facts["data_access"]["sql"]
    remote = facts["data_access"]["remote_endpoints"]
    lines = ["```mermaid", "flowchart LR", "  SVC[services]"]
    if vdb:
        lines.append(f'  SVC --> V[("{" · ".join(vdb)}")]')
    if sql:
        lines.append(f'  SVC --> S[("{" · ".join(sql)}")]')
    if not vdb and not sql:
        lines.append("  SVC -. no local store detected .- SVC")
    note = "direct client calls — no local↔cloud abstraction" if (vdb or sql) else ""
    if note:
        lines.append(f'  SVC -. "{note}" .- SVC')
    lines.append("```")
    return "\n".join(lines)


def build(facts):
    out = ["## Architecture Diagrams", "",
           "> Auto-generated from the import graph + route table — **$0 tokens**.", "",
           "### Layered Flow — Frontend → Middleware → Backend → Cloud", "",
           layered_flow(facts), "",
           "### Component / Import Graph", "",
           component_graph(facts), "",
           "### Request Workflow (Sequence)", "",
           workflow_sequence(facts), "",
           "### Data-Access / Local-First Flow", "",
           data_flow(facts), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Generate Mermaid diagrams from facts.json ($0).")
    ap.add_argument("facts", help="path to xray-facts.json")
    ap.add_argument("--out", help="output markdown path (default: alongside facts as diagrams.md)")
    args = ap.parse_args()
    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    md = build(facts)
    out = Path(args.out) if args.out else Path(args.facts).parent / "diagrams.md"
    out.write_text(md, encoding="utf-8")
    print(f"diagram: wrote {out}")


if __name__ == "__main__":
    main()
