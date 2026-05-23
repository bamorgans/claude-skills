#!/usr/bin/env bash
# rn-common.sh — Shared helpers for RN/Expo build scripts.
# SOURCE this file — do not execute directly.
#
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/rn-common.sh"
#
# Works with both Expo-managed and bare React Native projects.

# ── Colour helpers ────────────────────────────────────────────────────────────
rn_red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
rn_green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
rn_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
rn_bold()   { printf '\033[1m%s\033[0m\n'    "$*"; }

rn_die() { rn_red "❌  $*" >&2; exit 1; }

# ── Project root detection ─────────────────────────────────────────────────────
rn_check_project_root() {
  [[ -f "package.json" ]] || rn_die "No package.json found. Run from the project root."
}

# Returns the app name from package.json, app.json (Expo), or build.gradle (Android).
rn_detect_app_name() {
  # 1. package.json "name"
  local name
  name=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('name',''))" 2>/dev/null || true)
  [[ -n "$name" ]] && echo "$name" && return

  # 2. app.json "expo.name" (Expo managed)
  if [[ -f "app.json" ]]; then
    name=$(python3 -c "import json; d=json.load(open('app.json')); print(d.get('expo',d).get('name',''))" 2>/dev/null || true)
    [[ -n "$name" ]] && echo "$name" && return
  fi

  # 3. android/app/build.gradle applicationId last segment
  if [[ -f "android/app/build.gradle" ]]; then
    name=$(grep -m1 'applicationId' android/app/build.gradle | grep -oE '"[^"]+"' | tr -d '"' | awk -F'.' '{print $NF}' || true)
    [[ -n "$name" ]] && echo "$name" && return
  fi

  echo "App"
}

# ── Framework detection ───────────────────────────────────────────────────────
# Returns "expo" or "bare" — callers may need different build commands.
rn_detect_framework() {
  if python3 -c "import json; d=json.load(open('package.json')); exit(0 if 'expo' in d.get('dependencies',{}) or 'expo' in d.get('devDependencies',{}) else 1)" 2>/dev/null; then
    echo "expo"
  else
    echo "bare"
  fi
}

# ── Build log management ──────────────────────────────────────────────────────
# Creates a temp log file, prints its path, and exports BUILD_LOG.
rn_start_build_log() {
  local platform="${1:-build}"
  BUILD_LOG=$(mktemp "/tmp/rn-${platform}-build-XXXXXX.log")
  export BUILD_LOG
  echo "$BUILD_LOG"
}

# ── External volume detection ─────────────────────────────────────────────────
# Returns 0 (true) if CWD is on a "noowners" APFS external volume.
# noowners volumes cause EPERM on unlink for files created in prior sessions.
rn_is_noowners_volume() {
  local mount_point
  mount_point=$(df -P . 2>/dev/null | tail -1 | awk '{print $NF}')
  mount 2>/dev/null | grep -E " on ${mount_point}( |,|\))" | grep -q "noowners"
}

# Warn + print permanent-fix advice when on a noowners volume.
rn_warn_noowners() {
  rn_yellow "⚠️   Project is on an external volume mounted with 'noowners'."
  rn_yellow "    Stale bundle artifacts will be pre-cleaned before each build."
  rn_yellow "    Permanent fix: Xcode → File → Project Settings → Build Location"
  rn_yellow "    → Custom → ~/Library/Developer/Xcode/DerivedData"
}

# ── iOS/tvOS stale artifact cleanup ──────────────────────────────────────────
# Removes main.jsbundle + resources-to-copy-*.txt from a prior build.
# Safe unconditionally — these are pure JS-bundle outputs, not incremental state.
# Never deletes ios/Build/ or ios/build/ — that breaks ReactCodegen.
rn_preclear_ios_bundle() {
  local products_dir="${1:?products_dir required}"
  [[ -d "$products_dir" ]] || return 0
  local cleaned=0
  for f in "$products_dir/main.jsbundle" "$products_dir/main.jsbundle.map"; do
    [[ -f "$f" ]] && { rm -f "$f"; cleaned=1; }
  done
  local stale_txt
  stale_txt=$(find "$products_dir" -name "resources-to-copy-*.txt" 2>/dev/null || true)
  if [[ -n "$stale_txt" ]]; then
    echo "$stale_txt" | xargs rm -f 2>/dev/null || true
    cleaned=1
  fi
  [[ $cleaned -eq 1 ]] && rn_yellow "⚠️   Pre-cleaned stale bundle artifacts from previous build."
  return 0
}

# ── Metro cleanup ─────────────────────────────────────────────────────────────
# Kills any Metro process on port 8081 to prevent bundle-phase conflicts.
rn_kill_metro() {
  local pids
  pids=$(lsof -ti tcp:8081 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    rn_yellow "⚠️   Killing Metro on port 8081 (may conflict with native bundle phase)…"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

# ── SWBBuildService cleanup ───────────────────────────────────────────────────
# Kills a stuck Xcode build service that can cause PIF/stall errors.
rn_kill_swb() {
  if pgrep -x "SWBBuildService" &>/dev/null; then
    rn_yellow "⚠️   Killing stale SWBBuildService…"
    pkill -x "SWBBuildService" 2>/dev/null || true
    sleep 1
  fi
}

# ── Preflight checks ──────────────────────────────────────────────────────────
# Verifies required platform tools are installed before attempting a build.
# Exits with a clear message if anything is missing.
rn_preflight_check() {
  local platform="${1:?platform required}"  # ios | android

  case "$platform" in
    ios)
      if ! xcode-select -p &>/dev/null; then
        rn_die "Xcode not found.\nInstall Xcode from the App Store, then run:\n  xcode-select --install"
      fi
      ;;
    android)
      if ! command -v adb &>/dev/null; then
        rn_die "adb not found. Install Android SDK platform-tools:\n  brew install android-platform-tools\n  or: https://developer.android.com/tools/releases/platform-tools"
      fi
      if ! command -v java &>/dev/null; then
        rn_die "java not found. Install a JDK:\n  brew install --cask temurin"
      fi
      if [[ -z "${ANDROID_HOME:-}" ]]; then
        rn_yellow "⚠️   ANDROID_HOME is not set. Add to your shell profile:\n    export ANDROID_HOME=\$HOME/Library/Android/sdk"
      fi
      ;;
    *)
      rn_die "rn_preflight_check: unknown platform '$platform'. Use ios or android."
      ;;
  esac
}

# ── Project configure check ───────────────────────────────────────────────────
# Checks that the native project exists before building. If it doesn't,
# prints instructions to generate it and exits 1. No-op when already configured.
rn_configure_project() {
  local platform="${1:?platform required}"  # ios | android

  case "$platform" in
    ios)
      local ws
      ws=$(find ios -maxdepth 1 -name "*.xcworkspace" 2>/dev/null | head -1 || true)
      if [[ -z "$ws" ]]; then
        rn_red "❌  No iOS native project found (ios/*.xcworkspace missing)."
        echo ""
        echo "   Generate it with:"
        echo "     npx expo prebuild --platform ios"
        echo "     cd ios && pod install && cd .."
        echo ""
        echo "   Then retry: ~/.claude/scripts/rn-device-install ios"
        exit 1
      fi
      ;;
    android)
      if [[ ! -f "android/gradlew" ]]; then
        rn_red "❌  No Android native project found (android/gradlew missing)."
        echo ""
        echo "   Generate it with:"
        echo "     npx expo prebuild --platform android"
        echo ""
        echo "   Then retry: ~/.claude/scripts/rn-device-install android"
        exit 1
      fi
      ;;
    *)
      rn_die "rn_configure_project: unknown platform '$platform'. Use ios or android."
      ;;
  esac
}

# ── EAS cloud deploy ──────────────────────────────────────────────────────────
# Triggers an EAS cloud build for any Expo project. Works from any project root
# that has an eas.json. No local SDK or signing config required.
#
# Usage: rn_eas_deploy <platform> [profile]
#   platform: ios | android
#   profile:  preview (default) | production | development | any eas.json profile
rn_eas_deploy() {
  local platform="${1:?platform required}"  # ios | android
  local profile="${2:-preview}"

  rn_check_project_root

  command -v npx &>/dev/null || rn_die "npx not found. Install Node.js: https://nodejs.org"

  if [[ ! -f "eas.json" ]]; then
    rn_die "eas.json not found.\nRun: npx eas init   to set up EAS for this project."
  fi

  rn_bold "☁️   EAS cloud build: $platform ($profile)…"
  echo "    Project: $(rn_detect_app_name)"
  echo ""

  # Login if not already authenticated
  npx eas whoami &>/dev/null || npx eas login

  npx eas build --platform "$platform" --profile "$profile"

  echo ""
  rn_green "✅  EAS build queued."
  echo "    Open the download link above on the target device to install."
  if [[ "$platform" == "android" ]]; then
    rn_yellow "    Android: you may need to allow 'Install from unknown sources' the first time."
    rn_yellow "             Settings → Security → Install unknown apps → allow for your browser."
  fi
  rn_yellow "    Preview builds expire after 30 days. Re-run to refresh."
}
