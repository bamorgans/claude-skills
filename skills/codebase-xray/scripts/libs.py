#!/usr/bin/env python3
"""
libs.py — derive a libraries & dependency inventory from xray-facts.json.

NO LLM calls, $0 tokens. Classifies detected libraries by layer and
local/cloud role using a known-library map, falling back to declared
dependencies. Emits libs.json + a markdown table.

Usage:
    python libs.py <facts.json> [--out-json libs.json] [--out-md libs.md]
"""
import argparse
import json
from pathlib import Path

# name -> (layer, role, note)
KNOWN = {
    "fastapi": ("Web framework", "local", "async, typed"),
    "flask": ("Web framework", "local", "lightweight WSGI"),
    "django": ("Web framework", "local", "batteries-included"),
    "litestar": ("Web framework", "local", "async"),
    "express": ("Web framework", "local", "node"),
    "uvicorn": ("ASGI server", "local", ""),
    "gunicorn": ("WSGI server", "local", ""),
    "starlette": ("ASGI core", "local", "transitive"),
    "pydantic": ("Validation", "local", ""),
    "httpx": ("HTTP client", "both", "async-capable"),
    "requests": ("HTTP client", "both", ""),
    "aiohttp": ("HTTP client", "both", "async"),
    "qdrant_client": ("Vector DB", "local", "native dep"),
    "qdrant": ("Vector DB", "local", "native dep"),
    "chromadb": ("Vector DB", "local", ""),
    "lancedb": ("Vector DB", "local", "pure-python"),
    "faiss": ("Vector DB", "local", ""),
    "sqlite3": ("Storage", "local", "stdlib"),
    "sqlalchemy": ("ORM", "local", ""),
    "psycopg2": ("Storage", "local/remote", "postgres"),
    "redis": ("Cache", "local/remote", ""),
    "anthropic": ("LLM (cloud)", "cloud", "Claude"),
    "openai": ("LLM (cloud)", "cloud", "GPT"),
    "cohere": ("LLM (cloud)", "cloud", ""),
    "ollama": ("Local LLM", "local", "via REST"),
    "llama_cpp": ("Local LLM", "local", ""),
    "transformers": ("ML", "local", "heavy"),
    "sentence_transformers": ("Embeddings", "local", ""),
    "boto3": ("Cloud SDK", "cloud", "AWS"),
    "logging": ("Observability", "local", "stdlib"),
    "prometheus_client": ("Observability", "local", "metrics"),
    "opentelemetry": ("Observability", "both", "tracing"),
    "react": ("Frontend", "local", ""),
    "vue": ("Frontend", "local", ""),
    "svelte": ("Frontend", "local", ""),
    "pyinstaller": ("Packaging", "—", "binary build"),
    "spacy": ("NLP", "local", ""),
    "yaml": ("Config", "local", "pyyaml"),
    "dotenv": ("Config", "local", "env vars"),
    "watchdog": ("Filesystem", "local", "file watch"),
    "yfinance": ("Data API", "cloud", "finance"),
    "trafilatura": ("Scraping", "cloud", "web extract"),
    "googleapiclient": ("Cloud SDK", "cloud", "Google APIs"),
    "google_auth_oauthlib": ("Auth", "cloud", "OAuth"),
    "google": ("Cloud SDK", "cloud", "Google"),
}


def build_inventory(facts):
    seen = {}

    def add(name):
        key = name.lower()
        if key in seen:
            return
        layer, role, note = KNOWN.get(key, ("Library", "?", ""))
        seen[key] = {"library": name, "layer": layer, "role": role, "note": note}

    for n in facts["security"]["cloud_sdks"]:
        add(n)
    for n in facts["security"]["local_ai"]:
        add(n)
    for n in facts["observability"]["libs"]:
        add(n)
    for n in facts["data_access"]["vector_db"]:
        add(n)
    for n in facts["data_access"]["sql"]:
        add(n)
    for n in facts["data_access"]["orm"]:
        add(n)
    for n in facts["dependencies"]:
        add(n)
    for entry in facts.get("third_party_imports", []):
        add(entry["name"])

    return sorted(seen.values(), key=lambda r: (r["layer"], r["library"]))


def render_md(inv):
    if not inv:
        return "## Libraries & Dependency Inventory\n\n_No libraries detected._\n"
    lines = ["## Libraries & Dependency Inventory", "",
             "> Derived from imports + manifests — **$0 tokens**.", "",
             "| Library | Layer | Local/Cloud | Note |",
             "|---|---|:--:|---|"]
    for r in inv:
        lines.append(f"| **{r['library']}** | {r['layer']} | {r['role']} | {r['note']} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Library inventory from facts.json ($0).")
    ap.add_argument("facts")
    ap.add_argument("--out-json")
    ap.add_argument("--out-md")
    args = ap.parse_args()
    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    inv = build_inventory(facts)
    base = Path(args.facts).parent
    (Path(args.out_json) if args.out_json else base / "libs.json").write_text(
        json.dumps(inv, indent=2), encoding="utf-8")
    (Path(args.out_md) if args.out_md else base / "libs.md").write_text(
        render_md(inv), encoding="utf-8")
    print(f"libs: {len(inv)} libraries classified")


if __name__ == "__main__":
    main()
