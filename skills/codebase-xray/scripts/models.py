#!/usr/bin/env python3
"""
models.py — model alias resolution + cost accounting for codebase-xray.

Tier aliases (opus|sonnet|haiku) map to canonical Claude IDs. Built-in aliases
can be overridden by an optional "modelAliases" object in the skill's own
xray.config.json; nothing is read from the target repo.

Importable (resolve, pretty, cost_for, policy_for) and runnable as a CLI for a
quick cost breakdown.

stdlib only.
"""
import argparse
import json
import sys
from pathlib import Path

# Canonical IDs — kept in lockstep with COST below.
DEFAULT_ALIASES = {
    "opus": "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# USD per 1M tokens (input, output). Representative public Anthropic rates.
COST = {
    "claude-opus-4-8":            {"in": 15.00, "out": 75.00},
    "claude-sonnet-4-6":          {"in": 3.00,  "out": 15.00},
    "claude-haiku-4-5-20251001":  {"in": 1.00,  "out": 5.00},
}

# Default tier policy for the xray pipeline phases.
DEFAULT_POLICY = {
    "extract": "haiku",
    "persona": "sonnet",
    "synthesis": "opus",
}

PRETTY = {
    "claude-opus-4-8": "Opus 4.8",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
}


CONFIG_PATH = Path(__file__).resolve().parent.parent / "xray.config.json"


def load_aliases():
    """Merge built-in aliases with the optional modelAliases in xray.config.json."""
    aliases = dict(DEFAULT_ALIASES)
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            aliases.update(data.get("modelAliases") or {})
        except (OSError, json.JSONDecodeError):
            pass
    return aliases


def resolve(alias):
    """alias|canonical-id → canonical-id (passthrough for unknown)."""
    return load_aliases().get(alias, alias)


def pretty(model_id):
    if model_id in PRETTY:
        return PRETTY[model_id]
    # strip trailing date and prettify: claude-haiku-4-5-2025... -> Haiku 4.5
    parts = model_id.replace("claude-", "").split("-")
    if len(parts) >= 3 and parts[0]:
        return f"{parts[0].capitalize()} {parts[1]}.{parts[2]}"
    return model_id


def cost_for(model_id, in_tok, out_tok):
    rate = COST.get(model_id, {"in": 0.0, "out": 0.0})
    return round(in_tok / 1_000_000 * rate["in"] + out_tok / 1_000_000 * rate["out"], 4)


def policy_for(phase, overrides=None):
    """Return the canonical model id for a pipeline phase, honoring xray.config.json."""
    policy = dict(DEFAULT_POLICY)
    if overrides:
        policy.update(overrides)
    return resolve(policy.get(phase, "sonnet"))


def breakdown(rows):
    """rows: list of dicts {phase, model(alias|id|'deterministic'), in, out, wall}.
    Returns rendered markdown table + total."""
    lines = ["| Phase | Model | In | Out | Cost | Wall |",
             "|---|---|--:|--:|--:|--:|"]
    tot_in = tot_out = tot_cost = 0.0
    models_seen = set()
    for r in rows:
        m = r.get("model", "deterministic")
        if m in ("deterministic", "", None):
            lines.append(f"| {r['phase']} | deterministic | 0 | 0 | $0.0000 | "
                         f"{r.get('wall','')} |")
            continue
        mid = resolve(m)
        models_seen.add(mid)
        c = cost_for(mid, r.get("in", 0), r.get("out", 0))
        tot_in += r.get("in", 0); tot_out += r.get("out", 0); tot_cost += c
        lines.append(f"| {r['phase']} | {pretty(mid)} | {r.get('in',0):,} | "
                     f"{r.get('out',0):,} | ${c:.4f} | {r.get('wall','')} |")
    lines.append(f"| **TOTAL** | **{len(models_seen)} models** | **{int(tot_in):,}** | "
                 f"**{int(tot_out):,}** | **${tot_cost:.2f}** | |")
    return "\n".join(lines), round(tot_cost, 2)


def main():
    ap = argparse.ArgumentParser(description="Model resolution + cost helper.")
    ap.add_argument("--resolve", help="resolve an alias to canonical id")
    ap.add_argument("--breakdown", help="path to a JSON file of cost rows")
    args = ap.parse_args()
    if args.resolve:
        print(resolve(args.resolve))
    elif args.breakdown:
        rows = json.loads(Path(args.breakdown).read_text())
        md, total = breakdown(rows)
        print(md)
        print(f"\nTotal: ${total}")
    else:
        for a, c in load_aliases().items():
            print(f"{a:8} → {c}  ({pretty(c)})")


if __name__ == "__main__":
    main()
