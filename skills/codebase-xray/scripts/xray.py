#!/usr/bin/env python3
"""
xray.py — single deterministic entrypoint for codebase-xray.

Runs the $0 toolchain (scan → diagram → design_system → libs) into
<target>/.xray, then optionally renders. The SKILL.md orchestrator calls
`xray.py prep <target>` once, dispatches its persona sub-agents (which write
.xray/findings.json), then calls `xray.py render <target>`.

stdlib only.

Usage:
    python xray.py prep   <target>     # deterministic bundle ($0)
    python xray.py render <target>     # assemble XRAY-REPORT.md
    python xray.py all    <target>     # prep + render (no agents → degraded report)
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(script, *args):
    cmd = [sys.executable, str(HERE / script), *map(str, args)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)


def prep(target):
    target = Path(target).resolve()
    facts = target / ".xray" / "xray-facts.json"
    run("scan.py", target)
    run("diagram.py", facts)
    run("design_system.py", target)
    run("libs.py", facts)
    print(f"prep: deterministic bundle ready in {target/'.xray'} ($0 tokens)")


def main():
    ap = argparse.ArgumentParser(description="codebase-xray deterministic entrypoint.")
    ap.add_argument("cmd", choices=["prep", "render", "all"])
    ap.add_argument("target")
    args = ap.parse_args()
    if args.cmd in ("prep", "all"):
        prep(args.target)
    if args.cmd in ("render", "all"):
        run("render_report.py", args.target)


if __name__ == "__main__":
    main()
