#!/usr/bin/env python3
"""
scan.py — deterministic codebase scanner for codebase-xray.

Walks a target repo and emits a compact xray-facts.json. NO LLM calls, $0 tokens.
This facts file is what every analysis agent reads instead of the raw repo —
that is the token-minimization mechanism of codebase-xray.

stdlib only. Python 3.8+.

Usage:
    python scan.py <target_dir> [--out <facts.json>]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---- configuration -------------------------------------------------------

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".pytest_cache", ".mypy_cache",
    "site-packages", ".idea", ".vscode", "coverage", "target", "vendor",
}
CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java",
    ".kt", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".html",
    ".css", ".scss", ".vue", ".svelte", ".sh", ".bat", ".ps1", ".yaml",
    ".yml", ".sql",
}
MAX_FILE_BYTES = 1_500_000  # skip files larger than this for content scans

# Sensitive-name detection, two tiers — deliberately narrow so slugs like
# "feat-design-token-quickref.md" are NOT flagged (the sensitive word must BE
# the filename stem, not a substring of a longer slug):
#   INHERENT  — extension/name alone implies credential material
#   NAME_HINT — whole-stem sensitive word + config-ish extension (token.json, secrets.yaml)
INHERENT_SENSITIVE_RE = re.compile(
    r"(^|/)(\.env(\.[A-Za-z0-9._-]+)?|\.netrc|\.pgpass|id_rsa[^/]*|id_ed25519[^/]*)$"
    r"|\.(pem|p12|pfx|keystore|jks)$",
    re.I,
)
# committed-on-purpose templates are not secrets
SENSITIVE_EXEMPT_RE = re.compile(r"\.(example|sample|template|dist)$|\.example\.", re.I)
NAME_HINT_SENSITIVE_RE = re.compile(
    r"^(secrets?|credentials?|tokens?|passwords?|api[-_]?keys?)"
    r"\.(json|ya?ml|toml|ini|cfg|txt|env|properties)$",
    re.I,
)
SECRET_CONTENT_RE = re.compile(
    r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|api[_-]?key\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,})",
    re.I,
)
BIND_RE = re.compile(r"0\.0\.0\.0|host\s*=\s*['\"]0\.0\.0\.0")
ROUTE_RE = re.compile(r"@(?:app|router|api)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)")
FLASK_ROUTE_RE = re.compile(r"@(?:app|bp)\.route\(\s*['\"]([^'\"]+)")
# express/koa/fastify-style: app.get('/path'), router.post("/x"), server.put(`/y`)
NODE_ROUTE_RE = re.compile(
    r"\b(?:app|router|server|api)\.(get|post|put|delete|patch|all)\(\s*['\"`](/[^'\"`\s]*)"
)
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}
# test files across ecosystems: test_x.py, x_test.py/go, x.test.ts(x), x.spec.js,
# __tests__/ dirs, tests/ dirs, conftest.py
TEST_FILE_RE = re.compile(
    r"(^|/)__tests__/"
    r"|(^|/)tests?/"
    r"|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|(^|/)test_[^/]+\.\w+$"
    r"|_test\.(py|go|js|ts|rb)$"
    r"|(^|/)conftest\.py$"
)
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
BARE_EXCEPT_RE = re.compile(r"except\s*:")
EXCEPT_RE = re.compile(r"\bexcept\b")
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+))", re.M)

# paths we never treat as project-owned (committed third-party / build output)
VENDOR_PATH_RE = re.compile(r"(^|/)(site-packages|node_modules|dist-packages|vendor)/|/pyvenv\.cfg$|(^|/)ai/Lib/")

STDLIB = {
    "os", "sys", "json", "re", "datetime", "pathlib", "typing", "logging", "time",
    "subprocess", "asyncio", "collections", "functools", "io", "sqlite3", "hashlib",
    "base64", "uuid", "random", "math", "shutil", "tempfile", "glob", "argparse",
    "__future__", "dataclasses", "enum", "abc", "contextlib", "itertools", "socket",
    "threading", "copy", "textwrap", "warnings", "inspect", "importlib", "urllib",
    "email", "ctypes", "platform", "operator", "string", "struct", "csv", "html",
    "http", "unittest", "traceback", "signal", "queue", "secrets", "decimal",
    "xml", "tkinter", "getpass", "concurrent", "multiprocessing", "smtplib",
}


CLOUD_SDKS = {"openai", "anthropic", "boto3", "google.cloud", "azure", "cohere", "replicate"}
LOCAL_AI = {"ollama", "llama_cpp", "transformers", "sentence_transformers", "qdrant_client",
            "chromadb", "lancedb", "faiss"}
OBS_LIBS = {"logging", "prometheus_client", "opentelemetry", "sentry_sdk", "structlog"}

MANIFESTS = {
    "requirements.txt": "python", "pyproject.toml": "python", "setup.py": "python",
    "Pipfile": "python", "package.json": "node", "go.mod": "go",
    "Cargo.toml": "rust", "Gemfile": "ruby", "pom.xml": "java", "build.gradle": "java",
}
ONE_BUTTON = ["start.sh", "start.bat", "startup.bat", "run.sh", "Makefile", "makefile",
              "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "launcher.py",
              "main.py", "manage.py", "index.js"]


# ---- helpers -------------------------------------------------------------

def is_venv(path):
    return (path / "pyvenv.cfg").exists()


def walk_files(root):
    """Yield (relpath, abspath) for non-ignored files, skipping detected venvs."""
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # prune ignored + venv dirs in place
        dirnames[:] = [
            n for n in dirnames
            if n not in IGNORE_DIRS and not is_venv(d / n) and not n.startswith(".")
            or n in (".github",)
        ]
        for fn in filenames:
            ap = d / fn
            try:
                yield str(ap.relative_to(root)), ap
            except ValueError:
                continue


def read_text(path):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeError):
        return None


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---- analysis passes -----------------------------------------------------

def analyze(root):
    root = Path(root).resolve()
    facts = {
        "target": str(root),
        "name": root.name,
        "inventory": {"by_ext": {}, "loc_by_ext": {}, "total_loc": 0,
                      "file_count": 0, "largest_files": []},
        "manifests": [],
        "dependencies": [],
        "entry_points": [],
        "routes": [],
        "import_graph": [],
        "security": {"committed_sensitive": [], "secret_patterns": [],
                     "network_binds": [], "cloud_sdks": [], "local_ai": []},
        "portability": {"shell_scripts": [], "bat_scripts": [], "platform_specific": [],
                        "committed_binaries": [], "committed_venv": False},
        "error_handling": {"except_total": 0, "bare_except": 0, "todo_fixme": 0,
                           "bare_except_locations": [], "todo_fixme_locations": []},
        "observability": {"logging": False, "health_endpoint": False, "metrics": False,
                          "libs": []},
        "tests": {"files": [], "count": 0, "frameworks": []},
        "data_access": {"vector_db": [], "sql": [], "orm": [], "remote_endpoints": []},
        "git": {"is_repo": False, "recent_commits": [], "tracked_count": 0,
                "churn_hotspots": []},
        "docs_excerpt": {},
        # What each extractor actually covers. Personas MUST consult this before
        # claiming absence: an empty list can mean "stack not supported", not "none".
        "scan_coverage": {
            "routes": "python decorators (flask/fastapi-style) + node express-style "
                      "(app|router|server|api).METHOD('/path'). Other stacks NOT scanned.",
            "import_graph": "python top-level modules only. JS/TS imports NOT scanned.",
            "tests": "filename conventions: test_*, *_test.*, *.test.*, *.spec.*, "
                     "__tests__/, tests/ dirs, conftest.py. Frameworks also inferred "
                     "from declared dependencies.",
            "dependencies": "requirements.txt, pyproject.toml ([project]/poetry dep "
                            "sections only), package.json, setup.py, go.mod, Cargo.toml, "
                            "Pipfile (dep sections only).",
            "semantics": "[] = none found by the supported extractors above; consult "
                         "this map before reporting something as absent.",
        },
    }

    ext_counter = Counter()
    loc_counter = Counter()
    sizes = []
    imports_internal = defaultdict(set)
    internal_modules = set()
    total_loc = 0
    file_count = 0
    obs_libs = set()
    cloud = set()
    local = set()
    third_party = Counter()

    # discover python package roots for import-graph internal detection
    all_files = list(walk_files(root))
    py_modules = set()
    for rel, _ in all_files:
        if rel.endswith(".py"):
            mod = rel[:-3].replace(os.sep, ".")
            py_modules.add(mod)
            py_modules.add(rel.split(os.sep)[0])  # top package

    for rel, ap in all_files:
        ext = ap.suffix.lower()
        file_count += 1
        if ext in CODE_EXT:
            ext_counter[ext] += 1
        text = None
        if ext in CODE_EXT or ap.name in MANIFESTS or ap.name in ONE_BUTTON:
            text = read_text(ap)
        if text is not None and ext in CODE_EXT:
            lines = text.count("\n") + 1
            loc_counter[ext] += lines
            total_loc += lines if ext in (".py", ".js", ".ts", ".tsx", ".go",
                                          ".rs", ".rb", ".java") else 0
            sizes.append((lines, rel))

        # --- one-button / entry points ---
        if ap.name in ONE_BUTTON or ext == ".spec":
            facts["entry_points"].append(rel)

        # --- manifests + deps ---
        if ap.name in MANIFESTS:
            facts["manifests"].append({"file": rel, "lang": MANIFESTS[ap.name]})
            if text:
                facts["dependencies"] += parse_deps(ap.name, text)
            # package.json bin/main are real entry points — record them
            if ap.name == "package.json" and text:
                try:
                    pj = json.loads(text)
                    pdir = str(Path(rel).parent)
                    pdir = "" if pdir == "." else pdir + "/"
                    bins = pj.get("bin")
                    if isinstance(bins, str):
                        facts["entry_points"].append(pdir + bins.lstrip("./"))
                    elif isinstance(bins, dict):
                        for v in bins.values():
                            facts["entry_points"].append(pdir + str(v).lstrip("./"))
                    if pj.get("main"):
                        facts["entry_points"].append(pdir + str(pj["main"]).lstrip("./"))
                except json.JSONDecodeError:
                    pass

        # --- portability ---
        if ext == ".sh":
            facts["portability"]["shell_scripts"].append(rel)
        if ext in (".bat", ".ps1"):
            facts["portability"]["bat_scripts"].append(rel)
        if ext in (".exe", ".dll", ".dylib") or ap.suffix.lower() in (".exe",):
            facts["portability"]["committed_binaries"].append(rel)

        if text is None:
            continue

        # --- content-based passes (code files) ---
        if ext == ".py":
            # imports → graph
            for m in PY_IMPORT_RE.finditer(text):
                name = (m.group(1) or m.group(2) or "").split(".")[0]
                if not name:
                    continue
                top = name
                src_mod = rel.split(os.sep)[0]
                if top in py_modules and top != src_mod:
                    imports_internal[src_mod].add(top)
                if top in CLOUD_SDKS or name in CLOUD_SDKS:
                    cloud.add(top)
                if top in LOCAL_AI:
                    local.add(top)
                if top in OBS_LIBS:
                    obs_libs.add(top)
                if top == "logging":
                    facts["observability"]["logging"] = True
                if (top and top not in py_modules and top not in STDLIB
                        and not top.startswith("_")):
                    third_party[top] += 1

            # data access
            if "qdrant" in text or "QdrantClient" in text:
                facts["data_access"]["vector_db"].append("qdrant")
            if "chromadb" in text:
                facts["data_access"]["vector_db"].append("chroma")
            if "import sqlite3" in text or "sqlite3.connect" in text:
                facts["data_access"]["sql"].append("sqlite3")
            if re.search(r"\b(SQLAlchemy|sqlalchemy|Base\.metadata)\b", text):
                facts["data_access"]["orm"].append("sqlalchemy")

        # error handling (all code) — counts AND repo file:line provenance
        facts["error_handling"]["except_total"] += len(EXCEPT_RE.findall(text))
        for ln, line in enumerate(text.splitlines(), 1):
            if BARE_EXCEPT_RE.search(line):
                facts["error_handling"]["bare_except"] += 1
                if len(facts["error_handling"]["bare_except_locations"]) < 20:
                    facts["error_handling"]["bare_except_locations"].append(f"{rel}:{ln}")
            if TODO_RE.search(line):
                facts["error_handling"]["todo_fixme"] += 1
                if len(facts["error_handling"]["todo_fixme_locations"]) < 20:
                    facts["error_handling"]["todo_fixme_locations"].append(f"{rel}:{ln}")

        # routes
        for m in ROUTE_RE.finditer(text):
            facts["routes"].append({"method": m.group(1).upper(), "path": m.group(2),
                                    "file": rel})
        for m in FLASK_ROUTE_RE.finditer(text):
            facts["routes"].append({"method": "ANY", "path": m.group(1), "file": rel})
        if ext in JS_EXTS:
            for m in NODE_ROUTE_RE.finditer(text):
                facts["routes"].append({"method": m.group(1).upper(),
                                        "path": m.group(2), "file": rel})
        if "/health" in text:
            facts["observability"]["health_endpoint"] = True
        if "prometheus" in text or "/metrics" in text:
            facts["observability"]["metrics"] = True

        # security
        for m in SECRET_CONTENT_RE.finditer(text):
            loc = f"{rel}"
            if loc not in facts["security"]["secret_patterns"]:
                facts["security"]["secret_patterns"].append(loc)
        for ln, line in enumerate(text.splitlines(), 1):
            if BIND_RE.search(line):
                facts["security"]["network_binds"].append(f"{rel}:{ln}")

        # remote endpoints (data access)
        for m in re.finditer(r"https?://[A-Za-z0-9.\-:]+", text):
            url = m.group(0)
            if "localhost" not in url and "127.0.0.1" not in url:
                if len(facts["data_access"]["remote_endpoints"]) < 15:
                    facts["data_access"]["remote_endpoints"].append(url)

        # tests
        relp = rel.replace(os.sep, "/")
        if ext in CODE_EXT and TEST_FILE_RE.search(relp):
            facts["tests"]["files"].append(rel)
            if "pytest" in text:
                facts["tests"]["frameworks"].append("pytest")
            if "unittest" in text:
                facts["tests"]["frameworks"].append("unittest")
            if "vitest" in text:
                facts["tests"]["frameworks"].append("vitest")
            if "@playwright/test" in text:
                facts["tests"]["frameworks"].append("playwright")
            elif re.search(r"\bjest\b|\bdescribe\(|\bit\(|\btest\(", text):
                facts["tests"]["frameworks"].append("jest/vitest-style")

    # finalize inventory
    sizes.sort(reverse=True)
    facts["inventory"]["by_ext"] = dict(ext_counter.most_common())
    facts["inventory"]["loc_by_ext"] = dict(loc_counter.most_common())
    facts["inventory"]["total_loc"] = total_loc
    facts["inventory"]["file_count"] = file_count
    facts["inventory"]["largest_files"] = [
        {"file": f, "loc": n} for n, f in sizes[:12]
    ]

    # import graph edges
    facts["import_graph"] = [
        {"from": src, "to": dst} for src, dsts in sorted(imports_internal.items())
        for dst in sorted(dsts)
    ]

    facts["security"]["cloud_sdks"] = sorted(cloud)
    facts["security"]["local_ai"] = sorted(local)
    facts["observability"]["libs"] = sorted(obs_libs)
    facts["portability"]["bat_scripts"] = sorted(set(facts["portability"]["bat_scripts"]))
    facts["portability"]["shell_scripts"] = sorted(set(facts["portability"]["shell_scripts"]))
    facts["data_access"]["vector_db"] = sorted(set(facts["data_access"]["vector_db"]))
    facts["data_access"]["sql"] = sorted(set(facts["data_access"]["sql"]))
    facts["data_access"]["orm"] = sorted(set(facts["data_access"]["orm"]))
    facts["routes"] = facts["routes"][:60]
    facts["dependencies"] = sorted(set(facts["dependencies"]))[:80]
    facts["entry_points"] = sorted(set(facts["entry_points"]))[:20]
    facts["third_party_imports"] = [
        {"name": n, "count": c} for n, c in third_party.most_common(40)
    ]

    # tests: infer frameworks from declared deps too (a repo with vitest in
    # devDependencies has a JS test suite even if content heuristics miss it)
    dep_set = {d.lower() for d in facts["dependencies"]}
    for fw in ("vitest", "jest", "playwright", "mocha", "pytest", "cypress"):
        if fw in dep_set:
            facts["tests"]["frameworks"].append(fw)
    if any(d.startswith("@testing-library/") for d in dep_set):
        facts["tests"]["frameworks"].append("testing-library")
    facts["tests"]["frameworks"] = sorted(set(facts["tests"]["frameworks"]))
    facts["tests"]["count"] = len(facts["tests"]["files"])
    facts["tests"]["files"] = sorted(facts["tests"]["files"])[:200]

    # docs excerpt — gives product/positioning personas real signal
    # (dedupe by upper-cased name: macOS/Windows filesystems are case-insensitive)
    for doc in ("README.md", "readme.md", "CLAUDE.md"):
        p = root / doc
        if p.exists() and doc.upper() not in {k.upper() for k in facts["docs_excerpt"]}:
            txt = read_text(p)
            if txt:
                facts["docs_excerpt"][doc] = txt[:3500]

    # git facts
    if (root / ".git").exists():
        facts["git"]["is_repo"] = True
        tracked = git(root, "ls-files").splitlines()
        facts["git"]["tracked_count"] = len(tracked)
        # venv roots = parent dirs of any tracked pyvenv.cfg → filter everything under them
        venv_prefixes = tuple(
            t.rsplit("/", 1)[0] + "/" if "/" in t else ""
            for t in tracked if t.endswith("pyvenv.cfg")
        )
        for t in tracked:
            vendored = bool(VENDOR_PATH_RE.search(t)) or (
                bool(venv_prefixes) and t.startswith(venv_prefixes))
            if vendored:
                facts["portability"]["committed_venv"] = True
            base = t.split("/")[-1]
            if (not vendored and not SENSITIVE_EXEMPT_RE.search(base)
                    and (INHERENT_SENSITIVE_RE.search("/" + t)
                         or NAME_HINT_SENSITIVE_RE.match(base)
                         or base.endswith(".db"))):
                facts["security"]["committed_sensitive"].append(t)
            if t.endswith((".exe", ".dll", ".dmg")) and not vendored:
                if t not in facts["portability"]["committed_binaries"]:
                    facts["portability"]["committed_binaries"].append(t)
        facts["security"]["committed_sensitive"] = facts["security"]["committed_sensitive"][:30]
        log = git(root, "log", "--oneline", "-8")
        facts["git"]["recent_commits"] = log.splitlines()
        churn = git(root, "log", "--name-only", "--pretty=format:", "-50")
        if churn:
            c = Counter(l for l in churn.splitlines() if l and not l.startswith(" "))
            facts["git"]["churn_hotspots"] = [
                {"file": f, "changes": n} for f, n in c.most_common(8)
            ]

    return facts


def parse_deps(name, text):
    deps = []
    if name == "requirements.txt":
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(re.split(r"[<>=!~ \[]", line)[0])
    elif name == "package.json":
        try:
            data = json.loads(text)
            for k in ("dependencies", "devDependencies"):
                deps += list(data.get(k, {}).keys())
        except json.JSONDecodeError:
            pass
    elif name == "pyproject.toml":
        deps += _pyproject_deps(text)
    elif name in ("Pipfile", "Cargo.toml"):
        # only take keys inside dependency sections — never metadata keys
        dep_sections = {"dependencies", "dev-dependencies", "build-dependencies",
                        "packages", "dev-packages"}
        section = ""
        for line in text.splitlines():
            hm = re.match(r"^\s*\[([^\]]+)\]", line)
            if hm:
                section = hm.group(1).strip().lower()
                continue
            if section.split(".")[-1] in dep_sections:
                km = re.match(r'^\s*["\']?([A-Za-z0-9_.\-]+)["\']?\s*=', line)
                if km:
                    deps.append(km.group(1))
    elif name == "setup.py":
        m = re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S)
        if m:
            for d in re.findall(r"['\"]([A-Za-z0-9_.\-]+)", m.group(1)):
                deps.append(d)
    elif name == "go.mod":
        for m in re.finditer(r"^\s+([a-zA-Z0-9./\-]+)\s+v", text, re.M):
            deps.append(m.group(1))
    return [d for d in deps if d and len(d) < 60]


def _pyproject_deps(text):
    """Extract real dependency names from pyproject.toml — never metadata keys."""
    names = []

    def _clean(spec):
        return re.split(r"[<>=!~;@ \[]", str(spec).strip().strip("'\""))[0]

    try:
        import tomllib
        data = tomllib.loads(text)
    except Exception:
        data = None
    if data is not None:
        proj = data.get("project", {})
        names += [_clean(d) for d in proj.get("dependencies", [])]
        for group in proj.get("optional-dependencies", {}).values():
            names += [_clean(d) for d in group]
        for group in data.get("dependency-groups", {}).values():
            names += [_clean(d) for d in group if isinstance(d, str)]
        poetry = data.get("tool", {}).get("poetry", {})
        for key in ("dependencies", "dev-dependencies"):
            names += [k for k in poetry.get(key, {}) if k.lower() != "python"]
        return [n for n in names if n]
    # fallback (py<3.11): only quoted entries inside dependencies = [...] arrays
    for m in re.finditer(r"(?:^|\n)\s*(?:dependencies|dev)\s*=\s*\[(.*?)\]", text, re.S):
        names += [_clean(d) for d in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))]
    return [n for n in names if n]


def main():
    ap = argparse.ArgumentParser(description="Deterministic codebase scanner ($0 tokens).")
    ap.add_argument("target", help="path to repo to scan")
    ap.add_argument("--out", help="output facts.json path (default: <target>/.xray/xray-facts.json)")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        sys.exit(2)

    facts = analyze(target)
    out = Path(args.out) if args.out else target / ".xray" / "xray-facts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, indent=2), encoding="utf-8")
    inv = facts["inventory"]
    print(f"scan: {inv['file_count']} files, {inv['total_loc']} LOC, "
          f"{len(facts['routes'])} routes, "
          f"{len(facts['security']['committed_sensitive'])} committed-sensitive, "
          f"{facts['error_handling']['bare_except']} bare-except → {out}")


if __name__ == "__main__":
    main()
