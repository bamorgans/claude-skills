#!/usr/bin/env bash
# rn-web.sh — Export + optionally deploy a React Native / Expo app for web.
#
# Works with Expo web (expo export) and bare RN + webpack/metro-bundler.
#
# Standalone (from project root):
#   platform/rn-web.sh [options]
#
# Composable (source + call):
#   source platform/rn-web.sh
#   rn_web_run [options]
#
# Options:
#   --output    DIR                  export destination (default: dist)
#   --serve                          start local preview server after export
#   --deploy    vercel|netlify|none  deploy after export (default: none)
#   --base-url  PATH                 base path for hosted deploys (e.g. /myapp)
#   --verbose                        set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/rn-common.sh"

# ── Build command detection ───────────────────────────────────────────────────

_rn_web_build_cmd() {
  local output_dir="${1:-dist}"
  local framework; framework=$(rn_detect_framework)

  if [[ "$framework" == "expo" ]]; then
    # Expo managed / Expo Router
    echo "npx expo export --platform web --output-dir ${output_dir}"
  elif [[ -f "webpack.config.js" ]]; then
    # Bare RN + react-native-web + webpack
    echo "npx react-native bundle --platform web --dev false --entry-file index.js --bundle-output ${output_dir}/index.bundle"
  else
    # Try expo export anyway (works for SDK 50+ projects even without full managed config)
    echo "npx expo export --platform web --output-dir ${output_dir}"
  fi
}

# ── Main export + deploy function ─────────────────────────────────────────────
# Env vars:
#   RN_WEB_OUTPUT     output directory    (default: dist)
#   RN_WEB_SERVE      1                   start local preview
#   RN_WEB_DEPLOY     vercel|netlify|none (default: none)
#   RN_WEB_BASE_URL   base path string

rn_web_build_and_deploy() {
  local output="${RN_WEB_OUTPUT:-dist}"
  local serve="${RN_WEB_SERVE:-0}"
  local deploy_target="${RN_WEB_DEPLOY:-none}"
  local base_url="${RN_WEB_BASE_URL:-}"

  rn_check_project_root
  local app_name; app_name=$(rn_detect_app_name)
  local framework; framework=$(rn_detect_framework)

  # ── Export ────────────────────────────────────────────────────────────────
  local build_cmd; build_cmd=$(_rn_web_build_cmd "$output")
  local build_log; build_log=$(rn_start_build_log "web")

  rn_bold "🌐  Exporting $app_name for web [$framework]…"
  echo "    Command: $build_cmd"
  echo "    Output:  $output/"
  echo "    Log:     $build_log"

  set +o pipefail
  eval "$build_cmd" 2>&1 | tee "$build_log" | grep --line-buffered -E "(error|warning|✓|done|Error)" || true
  local export_exit="${PIPESTATUS[0]}"
  set -o pipefail

  if [[ $export_exit -ne 0 ]]; then
    rn_red "Export failed. Last errors:"
    grep -i "error" "$build_log" | tail -20 || true
    echo "Full log: $build_log"
    exit 1
  fi

  [[ -d "$output" ]] || rn_die "Export completed but output directory '$output' not found."
  rn_green "✅  Web export complete: $output/"

  # ── Local preview ─────────────────────────────────────────────────────────
  if [[ "$serve" == "1" ]]; then
    rn_bold "🖥️   Starting local preview server…"
    if command -v npx &>/dev/null; then
      rn_green "    Opening http://localhost:8080"
      npx serve "$output" --listen 8080
    else
      rn_die "npx not found. Install Node.js or run: python3 -m http.server 8080 -d $output"
    fi
    return 0
  fi

  # ── Deploy ────────────────────────────────────────────────────────────────
  case "$deploy_target" in
    vercel)
      command -v vercel &>/dev/null || rn_die "vercel CLI not found. Install: npm i -g vercel"
      rn_bold "🚀  Deploying to Vercel…"
      local vercel_args=()
      [[ -n "$base_url" ]] && vercel_args+=(--public-path "$base_url")
      vercel "$output" --prod "${vercel_args[@]}" 2>&1
      ;;
    netlify)
      command -v netlify &>/dev/null || rn_die "netlify CLI not found. Install: npm i -g netlify-cli"
      rn_bold "🚀  Deploying to Netlify…"
      netlify deploy --dir="$output" --prod 2>&1
      ;;
    eas)
      command -v eas &>/dev/null || rn_die "eas CLI not found. Install: npm i -g eas-cli"
      rn_bold "🚀  Deploying via EAS Hosting…"
      eas deploy --platform web 2>&1
      ;;
    none)
      echo "    To deploy: rn-device-install web --deploy vercel|netlify|eas"
      ;;
    *)
      rn_die "Unknown deploy target: $deploy_target. Use vercel|netlify|eas|none."
      ;;
  esac
}

# ── Arg parser ────────────────────────────────────────────────────────────────

rn_web_run() {
  export RN_WEB_OUTPUT="dist"
  export RN_WEB_SERVE="0"
  export RN_WEB_DEPLOY="none"
  export RN_WEB_BASE_URL=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output)   export RN_WEB_OUTPUT="$2";   shift 2 ;;
      --serve)    export RN_WEB_SERVE="1";     shift   ;;
      --deploy)   export RN_WEB_DEPLOY="$2";  shift 2 ;;
      --base-url) export RN_WEB_BASE_URL="$2"; shift 2 ;;
      --verbose)  set -x;                      shift   ;;
      *) rn_die "Unknown option: $1\nValid: --output, --serve, --deploy, --base-url, --verbose" ;;
    esac
  done

  rn_web_build_and_deploy
}

# ── Standalone entry point ────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  rn_web_run "$@"
fi
