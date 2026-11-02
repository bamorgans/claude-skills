#!/usr/bin/env python3
"""
render_report.py — assemble the final XRAY-REPORT.md.

Merges the deterministic fragments (facts, diagrams, design, libs — all $0)
with the agents' findings.json (persona analyses + synthesis). Degrades
gracefully: if findings.json is absent, it renders the deterministic sections
plus a note that agent analysis has not run.

NO LLM calls. stdlib only (+ local models.py for cost/pretty).

Usage:
    python render_report.py <target_dir> [--out XRAY-REPORT.md]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import models as M  # noqa: E402

STATUS = {"green": "🟢", "yellow": "🟡", "red": "🔴", "": "⚪"}
SEV = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴", "": ""}


def _read(path, default=""):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else default


def _read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def banner(facts, findings, target):
    rows = (findings or {}).get("models_used") or [
        {"phase": "scan.py", "model": "deterministic"},
        {"phase": "diagram.py", "model": "deterministic"},
        {"phase": "design_system.py", "model": "deterministic"},
        {"phase": "libs.py", "model": "deterministic"},
    ]
    lines = ["```"]
    for r in rows:
        m = r.get("model", "deterministic")
        label = "deterministic" if m in ("deterministic", "", None) else M.pretty(M.resolve(m))
        lines.append(f" {r['phase']:<18} {label}")
    lines.append("```")
    return "\n".join(lines)


def scorecard(findings):
    sc = (findings or {}).get("scorecard")
    if not sc:
        return "_Scorecard pending agent analysis._"
    lines = ["| Dimension | Status | Note |", "|---|:--:|---|"]
    for row in sc:
        emoji = STATUS.get(row.get("status", ""), "⚪")
        lines.append(f"| {row['dimension']} | {emoji} | {row.get('note','')} |")
    return "\n".join(lines)


def recommendations(findings):
    recs = (findings or {}).get("recommendations")
    if not recs:
        return "_Recommendations pending agent analysis._"
    lines = ["| # | Rec | Impact | Effort | Owners | Evidence |",
             "|:--:|---|:--:|:--:|---|---|"]
    for r in recs:
        sev = SEV.get(r.get("severity", ""), "")
        par = " ⚡" if r.get("parallel") else ""
        owners = ", ".join(r.get("owners", []))
        lines.append(f"| **{r.get('rank','')}** {sev}{par} | {r['title']} | "
                     f"{r.get('impact','')} | {r.get('effort','')} | {owners} | "
                     f"{r.get('evidence','')} |")
    return "\n".join(lines)


def competitive(findings):
    comp = (findings or {}).get("competitive")
    if not comp:
        return ""
    lines = ["## Competitive Tech-Stack Analysis", "",
             "| Layer | Current | Alternatives | Pros | Cons | Recommendation |",
             "|---|---|---|---|---|---|"]
    for c in comp:
        lines.append(f"| {c.get('layer','')} | {c.get('current','')} | "
                     f"{c.get('alternatives','')} | {c.get('pros','')} | "
                     f"{c.get('cons','')} | {c.get('recommendation','')} |")
    return "\n".join(lines) + "\n"


def per_perspective(findings):
    personas = (findings or {}).get("personas")
    if not personas:
        return "_Per-perspective findings pending agent analysis._"
    out = []
    for p in personas:
        model = M.pretty(M.resolve(p.get("model", "sonnet")))
        out.append(f"<details><summary><b>{p['name']}</b> ({model})</summary>\n")
        for f in p.get("findings", []):
            sev = SEV.get(f.get("severity", ""), "")
            cites = f.get("citations") or ([f["evidence"]] if f.get("evidence") else [])
            flag = ""
            if f.get("verified") == "refuted":
                flag = " — **REFUTED** (downgraded)"
            elif f.get("verified") is True:
                flag = " ✓verified"
            elif f.get("needs_verification"):
                flag = " ⚠︎unverified"
            note = f" _{f['verification_note']}_" if f.get("verification_note") else ""
            out.append(f"- {sev} **{f.get('title','')}**{flag} — {f.get('detail','')} "
                       f"`{'; '.join(str(c) for c in cites)}`{note}")
        out.append("\n</details>\n")
    return "\n".join(out)


def cost_section(findings, target):
    rows = (findings or {}).get("models_used")
    if not rows:
        return ("_Cost breakdown available after an agent run. Deterministic "
                "phases (scan, diagram, design, libs, render) are always $0._")
    md, total = M.breakdown(rows)
    return md + f"\n\n**Total: ${total}** · deterministic phases cost $0."


def appendix(facts):
    inv = facts["inventory"]
    sec = facts["security"]
    port = facts["portability"]
    eh = facts["error_handling"]
    tests = facts.get("tests", {})
    lines = ["```",
             f"files            : {inv['file_count']}",
             f"total LOC        : {inv['total_loc']:,}",
             f"languages        : {', '.join(f'{k}×{v}' for k,v in list(inv['by_ext'].items())[:6])}",
             f"routes           : {len(facts['routes'])}",
             f"import edges      : {len(facts['import_graph'])}",
             f"test files       : {tests.get('count', len(tests.get('files', [])))} "
             f"({', '.join(tests.get('frameworks', [])) or 'no framework detected'})",
             f"vector db        : {', '.join(facts['data_access']['vector_db']) or '—'}",
             f"cloud sdks       : {', '.join(sec['cloud_sdks']) or '—'}",
             f"local ai         : {', '.join(sec['local_ai']) or '—'}",
             f"committed secrets: {', '.join(sec['committed_sensitive'][:6]) or 'none'}",
             f"network binds    : {', '.join(sec['network_binds']) or 'none'}",
             f"committed venv   : {port['committed_venv']}",
             f"committed bins   : {', '.join(port['committed_binaries']) or 'none'}",
             f"shell scripts    : {', '.join(port['shell_scripts']) or 'none'}",
             f"bat scripts      : {', '.join(port['bat_scripts']) or 'none'}",
             f"bare except      : {eh['bare_except']}",
             f"todo/fixme       : {eh['todo_fixme']}",
             "```"]
    return "\n".join(lines)


def deep_dives(base):
    """Merge any deep-dive component sections written by the orchestrator ($0)."""
    dd_dir = base / "deep-dives"
    if not dd_dir.is_dir():
        return ""
    parts = [_read(p).strip() for p in sorted(dd_dir.glob("*.md"))]
    return "\n\n".join(p for p in parts if p)


def build(target):
    base = Path(target) / ".xray"
    facts = _read_json(base / "xray-facts.json")
    if not facts:
        raise SystemExit(f"error: {base/'xray-facts.json'} not found — run scan first.")
    findings = _read_json(base / "findings.json")
    name = facts.get("name", "project")

    dd = deep_dives(base)
    verdict = (findings or {}).get("verdict", "_Verdict pending agent synthesis._")
    summary = (findings or {}).get("executive_summary",
                                   "_Executive summary pending agent synthesis. "
                                   "Deterministic structure below is complete._")

    doc = [
        f"# 🩻 Codebase X-Ray — {name}", "",
        f"> Generated by **codebase-xray** · target `{facts['target']}`", "",
        banner(facts, findings, target), "",
        f"**Verdict:** {verdict}", "",
        "---", "",
        "## 1. Executive Summary", "", summary, "",
        "## 2. Health Scorecard", "", scorecard(findings), "",
        "## 3. " + _read(base / "diagrams.md", "Architecture Diagrams\n\n_pending_").lstrip("# "), "",
        _read(base / "design.md", "## UI Design & Design System\n\n_no frontend_"), "",
        _read(base / "libs.md", "## Libraries & Dependency Inventory\n\n_none_"), "",
        competitive(findings),
        "## Prioritized Recommendations", "", recommendations(findings), "",
        "## Parallelization Plan", "",
        (findings or {}).get("parallel_plan", "_Pending agent synthesis._"), "",
        *(["## Deep-Dive Components", "", dd, ""] if dd else []),
        "## Per-Perspective Findings", "", per_perspective(findings), "",
        "## Model & Cost Breakdown", "", cost_section(findings, target), "",
        "## Appendix: Scan Facts", "", appendix(facts), "",
        "---", "_Generated by codebase-xray. Deterministic scripts (scan, diagram, "
        "design_system, libs, render) — $0 tokens._",
    ]
    return "\n".join(doc)


def main():
    ap = argparse.ArgumentParser(description="Assemble XRAY-REPORT.md ($0).")
    ap.add_argument("target")
    ap.add_argument("--out")
    args = ap.parse_args()
    md = build(args.target)
    out = Path(args.out) if args.out else Path(args.target) / "XRAY-REPORT.md"
    out.write_text(md, encoding="utf-8")
    print(f"render: wrote {out} ({len(md)} bytes)")


if __name__ == "__main__":
    main()
