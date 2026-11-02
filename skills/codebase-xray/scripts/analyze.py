#!/usr/bin/env python3
"""
analyze.py — API-fallback orchestration path for codebase-xray.

For environments WITHOUT Claude Code sub-agents. Fans out the persona analyses
to the Anthropic API in parallel (threads), then runs a synthesis pass, writes
.xray/findings.json, and renders the report. Shares the same facts.json and
persona briefs as the Claude Code path — single source of truth.

Requires: `pip install anthropic` and ANTHROPIC_API_KEY in the environment.
The deterministic prep (scan/diagram/design/libs) must have run first
(`python xray.py prep <target>`).

Model tiers resolved via models.py (aliases from xray.config.json / built-ins).

Usage:
    python analyze.py <target> [--config xray.config.json]
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import models as M  # noqa: E402

PERSONA_DIR = HERE.parent / "personas"


def load_config(target, path=None):
    cfg = {"policy": dict(M.DEFAULT_POLICY), "personas": None, "top_n": 12}
    cfg_path = Path(path) if path else HERE.parent / "xray.config.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
            cfg["policy"].update(data.get("policy", {}))
            cfg["personas"] = data.get("personas")
            cfg["top_n"] = data.get("top_n", 12)
        except json.JSONDecodeError:
            pass
    return cfg


def load_personas(selected=None):
    briefs = []
    for p in sorted(PERSONA_DIR.glob("*.md")):
        slug = p.stem.split("-", 1)[-1]
        if selected and slug not in selected:
            continue
        briefs.append({"slug": slug, "name": p.stem, "brief": p.read_text(encoding="utf-8")})
    return briefs


def call(client, model_id, system, user, max_tokens=2000):
    msg = client.messages.create(
        model=model_id, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return text, msg.usage.input_tokens, msg.usage.output_tokens


def run_persona(client, model_id, brief, facts_str):
    system = (brief + "\n\nReturn ONLY a JSON object: "
              '{"name": "<persona>", "findings": [{"severity":"red|orange|yellow|green",'
              '"title":"...","detail":"...","citations":["<repo file:line or file>"],'
              '"confidence":0.0,"needs_verification":false}]}'
              "\nCitations are locations IN THE TARGET REPO taken from the facts' "
              "location-bearing fields — never line numbers of the facts JSON. If a fact "
              "is count-only, cite the facts key and set needs_verification true. Consult "
              "scan_coverage before claiming absence: empty routes/import_graph/tests may "
              "mean the extractor does not support the stack; such claims must set "
              "needs_verification true and lower confidence.")
    user = f"Analyze this codebase from your perspective. FACTS:\n{facts_str}"
    text, ti, to = call(client, model_id, system, user)
    try:
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        data = {"name": brief.split("\n")[0][:40], "findings": []}
    data["model"] = "sonnet"
    return data, ti, to


def main():
    ap = argparse.ArgumentParser(description="API-fallback analysis path.")
    ap.add_argument("target")
    ap.add_argument("--config")
    args = ap.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.exit("error: pip install anthropic (API fallback path requires it)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("error: set ANTHROPIC_API_KEY")

    target = Path(args.target).resolve()
    facts_path = target / ".xray" / "xray-facts.json"
    if not facts_path.exists():
        sys.exit(f"error: run `python xray.py prep {target}` first")
    facts_str = facts_path.read_text(encoding="utf-8")

    cfg = load_config(target, args.config)
    personas = load_personas(cfg["personas"])
    client = anthropic.Anthropic()
    persona_model = M.policy_for("persona", cfg["policy"])
    synth_model = M.policy_for("synthesis", cfg["policy"])

    print(f"analyze: {len(personas)} personas on {M.pretty(persona_model)}, "
          f"synthesis on {M.pretty(synth_model)}")

    t0 = time.time()
    results, ptin, ptout = [], 0, 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(run_persona, client, persona_model, p["brief"], facts_str): p
                for p in personas}
        for fut in cf.as_completed(futs):
            data, ti, to = fut.result()
            results.append(data); ptin += ti; ptout += to
            print(f"  ✓ {data.get('name','?')}")
    persona_wall = f"{time.time()-t0:.0f}s"

    # synthesis
    synth_system = (
        "You are the SYNTHESIS agent for codebase-xray. Merge the persona findings "
        "into a prioritized report. Return ONLY JSON with keys: verdict, "
        "executive_summary, scorecard[{dimension,status,note}], "
        "recommendations[{rank,severity,parallel,title,impact,effort,owners,evidence}], "
        "parallel_plan (markdown string), competitive[{layer,current,alternatives,pros,cons,recommendation}]. "
        "Findings carry confidence and needs_verification flags; no verification pass "
        "exists on this path, so DOWNWEIGHT red findings with needs_verification=true "
        "and say so in the recommendation evidence. Cross-check absence claims against "
        "the facts' scan_coverage before letting them drive a recommendation."
    )
    synth_user = (f"FACTS:\n{facts_str}\n\nPERSONA FINDINGS:\n"
                  f"{json.dumps(results, indent=2)}")
    t1 = time.time()
    stext, sti, sto = call(client, synth_model, synth_system, synth_user, max_tokens=4000)
    try:
        synth = json.loads(stext[stext.find("{"):stext.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        synth = {"verdict": "synthesis parse failed", "executive_summary": stext[:500]}
    synth_wall = f"{time.time()-t1:.0f}s"

    findings = dict(synth)
    findings["personas"] = results
    findings["models_used"] = [
        {"phase": "scan.py", "model": "deterministic"},
        {"phase": "diagram.py", "model": "deterministic"},
        {"phase": "design_system.py", "model": "deterministic"},
        {"phase": "libs.py", "model": "deterministic"},
        {"phase": f"{len(personas)} personas", "model": "sonnet", "in": ptin,
         "out": ptout, "wall": persona_wall},
        {"phase": "synthesis", "model": "opus", "in": sti, "out": sto, "wall": synth_wall},
        {"phase": "render_report.py", "model": "deterministic"},
    ]
    out = target / ".xray" / "findings.json"
    out.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"analyze: wrote {out}")

    import subprocess
    subprocess.run([sys.executable, str(HERE / "render_report.py"), str(target)])


if __name__ == "__main__":
    main()
