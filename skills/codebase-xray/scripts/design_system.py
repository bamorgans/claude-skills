#!/usr/bin/env python3
"""
design_system.py — extract the frontend design system from a repo.

NO LLM calls, $0 tokens. Scrapes HTML/CSS/SCSS for color tokens, typography,
gradients, component class inventory, and framework/CDN detection. Emits a
design.json + a markdown fragment (component-layering note + token table).

Usage:
    python design_system.py <target_dir> [--out-json design.json] [--out-md design.md]
"""
import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

FE_EXT = {".html", ".css", ".scss", ".vue", ".svelte", ".jsx", ".tsx"}
IGNORE = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
          "site-packages"}

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
FONT_RE = re.compile(r"font-family\s*:\s*([^;{}]+)", re.I)
GRADIENT_RE = re.compile(r"(linear|radial)-gradient\([^;]+\)", re.I)
CLASS_RE = re.compile(r'class=["\']([^"\']+)["\']')
FETCH_RE = re.compile(r"""fetch\(\s*[`'"]([^`'"]+)""")
FRAMEWORK_HINTS = {
    "tailwind": re.compile(r"tailwind", re.I),
    "bootstrap": re.compile(r"bootstrap", re.I),
    "react": re.compile(r"react(-dom)?", re.I),
    "vue": re.compile(r"\bvue\b", re.I),
    "chart.js": re.compile(r"chart\.js|Chart\(", re.I),
    "cdn": re.compile(r"<script[^>]+src=|<link[^>]+href=", re.I),
}


def scan_frontend(root):
    root = Path(root)
    colors = Counter()
    fonts = Counter()
    gradients = Counter()
    classes = Counter()
    endpoints = set()
    frameworks = set()
    files = []
    for dp, dirs, fns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE and not d.startswith(".")
                   or d == ".github"]
        for fn in fns:
            p = Path(dp) / fn
            if p.suffix.lower() not in FE_EXT:
                continue
            try:
                if p.stat().st_size > 1_500_000:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            files.append(str(p.relative_to(root)))
            for m in HEX_RE.findall(text):
                colors[m.upper() if len(m) == 7 else m.lower()] += 1
            for m in FONT_RE.findall(text):
                fonts[m.strip()] += 1
            for m in GRADIENT_RE.findall(text):
                gradients[m if isinstance(m, str) else m[0]] += 1
            for m in CLASS_RE.findall(text):
                for c in m.split():
                    classes[c] += 1
            for m in FETCH_RE.findall(text):
                endpoints.add(m)
            for name, rx in FRAMEWORK_HINTS.items():
                if rx.search(text):
                    frameworks.add(name)
    return {
        "files": files,
        "colors": colors.most_common(16),
        "fonts": [f for f, _ in fonts.most_common(4)],
        "gradients": [g for g, _ in gradients.most_common(6)],
        "component_classes": [c for c, _ in classes.most_common(20)],
        "endpoints_called": sorted(endpoints)[:25],
        "frameworks": sorted(frameworks),
        "has_framework": bool(frameworks - {"cdn"}),
    }


def render_md(ds):
    if not ds["files"]:
        return "## UI Design & Design System\n\n_No frontend files detected._\n"
    fw = ", ".join(ds["frameworks"]) if ds["frameworks"] else "none (hand-rolled)"
    lines = ["## UI Design & Design System", "",
             "> Extracted from frontend files — **$0 tokens**.", "",
             f"**Detected framework:** {fw}  ",
             f"**Frontend files:** {len(ds['files'])}  ",
             f"**Typography:** `{ds['fonts'][0] if ds['fonts'] else 'n/a'}`", "",
             "### Color Tokens", "",
             "| Color | Uses |", "|---|--:|"]
    for c, n in ds["colors"][:12]:
        lines.append(f"| `{c}` | {n} |")
    lines += ["", "### Component Classes", "",
              "`" + "` · `".join(ds["component_classes"][:14]) + "`" if ds["component_classes"]
              else "_none_", ""]
    if ds["endpoints_called"]:
        lines += ["### UI → API wiring (fetch calls)", "",
                  "`" + "` · `".join(ds["endpoints_called"][:12]) + "`", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Extract design system from frontend ($0).")
    ap.add_argument("target")
    ap.add_argument("--out-json")
    ap.add_argument("--out-md")
    args = ap.parse_args()
    ds = scan_frontend(args.target)
    base = Path(args.target) / ".xray"
    base.mkdir(parents=True, exist_ok=True)
    (Path(args.out_json) if args.out_json else base / "design.json").write_text(
        json.dumps(ds, indent=2), encoding="utf-8")
    (Path(args.out_md) if args.out_md else base / "design.md").write_text(
        render_md(ds), encoding="utf-8")
    print(f"design: {len(ds['files'])} files, {len(ds['colors'])} colors, "
          f"frameworks={ds['frameworks'] or 'none'}")


if __name__ == "__main__":
    main()
