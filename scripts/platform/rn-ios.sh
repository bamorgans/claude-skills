#!/usr/bin/env bash
# rn-ios.sh — Build + install a React Native / Expo app on iOS or tvOS.
#
# Works with Expo-managed and bare React Native projects.
#
# Standalone (from project root):
#   platform/rn-ios.sh [options]
#
# Composable (source + call):
#   source platform/rn-ios.sh
#   rn_ios_run [options]
#
# Options:
#   --platform    ios|tvos           (default: ios)
#   --target      device|simulator   (default: device)
#   --scheme      NAME               (default: workspace filename)
#   --config      Release|Debug      (default: Release)
#   --sim-name    "iPhone 16"        (simulator only; default: first booted)
#   --no-install                     build only, skip install
#   --verbose                        set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/rn-common.sh"

# ── UDID helpers ──────────────────────────────────────────────────────────────

_rn_ios_find_device_udid() {
  local apple_platform="${1:-iphone}" # iphone | appletv
  local device_raw udid device_name device_model

  # devicectl (iOS 17+ / tvOS 17+)
  if command -v xcrun &>/dev/null && xcrun devicectl --version &>/dev/null 2>&1; then
    local pattern
    [[ "$apple_platform" == "appletv" ]] && pattern="apple tv" || pattern="iphone|ipad|ipod"
    device_raw=$(xcrun devicectl list devices 2>/dev/null \
      | grep -iE "(connected|available)" \
      | grep -iv "simulator" \
      | grep -iE "$pattern" \
      | head -1 || true)
    if [[ -n "$device_raw" ]]; then
      udid=$(echo "$device_raw" | awk '{print $3}')
      device_name=$(echo "$device_raw" | awk '{print $1}')
      device_model=$(echo "$device_raw" | awk '{for(i=5;i<=NF;i++) printf $i" "; print ""}' | xargs 2>/dev/null || echo "")
      echo "${udid}|${device_name}|${device_model}"
      return 0
    fi
  fi

  # Fallback: xctrace (Xcode 12+, older iOS)
  device_raw=$(xcrun xctrace list devices 2>/dev/null \
    | grep -v "Simulator\|==" | grep "(" | head -1 || true)
  if [[ -n "$device_raw" ]]; then
    udid=$(echo "$device_raw" | grep -oE '\([0-9A-Fa-f-]{36,}\)' | tr -d '()' | head -1)
    device_name=$(echo "$device_raw" | awk -F'(' '{print $1}' | xargs)
    echo "${udid}|${device_name}|"
    return 0
  fi

  return 1
}

_rn_ios_find_simulator_udid() {
  local apple_platform="${1:-ios}"  # ios | tvos
  local sim_name="${2:-}"           # optional: "iPhone 16", "Apple TV 4K"

  local os_filter
  [[ "$apple_platform" == "tvos" ]] && os_filter="tvOS" || os_filter="iOS"

  if [[ -n "$sim_name" ]]; then
    # Find specific simulator by name
    xcrun simctl list devices available 2>/dev/null \
      | grep -A200 "-- $os_filter" | grep -B200 "^-- " \
      | grep "$sim_name" | grep -oE '[0-9A-F-]{36}' | head -1 || true
  else
    # First booted simulator of the right OS
    local booted
    booted=$(xcrun simctl list devices booted 2>/dev/null \
      | grep -A200 "-- $os_filter" | grep -B200 "^-- " \
      | grep -oE '[0-9A-F-]{36}' | head -1 || true)
    if [[ -n "$booted" ]]; then
      echo "$booted"; return 0
    fi
    # No booted sim: return first available
    xcrun simctl list devices available 2>/dev/null \
      | grep -A200 "-- $os_filter" | grep -B200 "^-- " \
      | grep -oE '[0-9A-F-]{36}' | head -1 || true
  fi
}

# ── Workspace detection ───────────────────────────────────────────────────────

_rn_ios_find_workspace() {
  local ws
  ws=$(find ios -maxdepth 1 -name "*.xcworkspace" 2>/dev/null | head -1)
  if [[ -z "$ws" ]]; then
    rn_die "No .xcworkspace in ios/.\nRun: npx expo prebuild --platform ios\n  or: cd ios && pod install"
  fi
  echo "$ws"
}

# ── Main build + install function ─────────────────────────────────────────────
# All state passed as env vars so callers can compose without argument parsing.
# Required env (with defaults):
#   RN_IOS_PLATFORM  ios|tvos            (default: ios)
#   RN_IOS_TARGET    device|simulator    (default: device)
#   RN_IOS_CONFIG    Release|Debug       (default: Release)
#   RN_IOS_SCHEME    xcworkspace name    (auto-detected)
#   RN_IOS_SIM_NAME  simulator name      (simulator target only)
#   RN_IOS_NO_INSTALL  1                 (skip install step)

rn_ios_build_and_install() {
  local apple_platform="${RN_IOS_PLATFORM:-ios}"
  local target="${RN_IOS_TARGET:-device}"
  local configuration="${RN_IOS_CONFIG:-Release}"
  local scheme="${RN_IOS_SCHEME:-}"
  local sim_name="${RN_IOS_SIM_NAME:-}"
  local no_install="${RN_IOS_NO_INSTALL:-0}"

  rn_check_project_root
  rn_preflight_check ios
  rn_configure_project ios
  local app_name; app_name=$(rn_detect_app_name)
  local framework; framework=$(rn_detect_framework)

  # ── Workspace + scheme ──────────────────────────────────────────────────────
  local workspace; workspace=$(_rn_ios_find_workspace)
  [[ -z "$scheme" ]] && scheme=$(basename "$workspace" .xcworkspace)

  # ── Destination ─────────────────────────────────────────────────────────────
  local destination udid display_name

  if [[ "$target" == "simulator" ]]; then
    udid=$(_rn_ios_find_simulator_udid "$apple_platform" "$sim_name")
    if [[ -z "$udid" ]]; then
      local os_hint; [[ "$apple_platform" == "tvos" ]] && os_hint="tvOS" || os_hint="iOS"
      rn_die "No ${os_hint} simulator found.\nRun: xcrun simctl list devices available | grep -A20 '${os_hint}'"
    fi
    display_name=$(xcrun simctl list devices 2>/dev/null | grep "$udid" | awk -F'(' '{print $1}' | xargs)
    destination="id=${udid}"
    rn_bold "📱  Simulator: ${display_name:-$udid}"
  else
    local device_info
    local apple_hw; [[ "$apple_platform" == "tvos" ]] && apple_hw="appletv" || apple_hw="iphone"
    device_info=$(_rn_ios_find_device_udid "$apple_hw") || \
      rn_die "No ${apple_platform} device found.\n• Plug in via USB\n• Unlock the device\n• Tap 'Trust This Computer' if prompted"
    udid="${device_info%%|*}"
    local rest="${device_info#*|}"
    local dname="${rest%%|*}"
    local dmodel="${rest##*|}"
    display_name="$dname"
    destination="id=${udid}"
    rn_bold "📱  Device: ${dname}${dmodel:+ — $dmodel} ($udid)"
  fi

  # ── Close Xcode (physical device builds only — releases ios/Build/ locks) ───
  if [[ "$target" == "device" ]] && pgrep -qx "Xcode" 2>/dev/null; then
    rn_yellow "⚠️   Xcode is open — closing it to release build-directory locks…"
    osascript -e 'quit app "Xcode"' 2>/dev/null || killall Xcode 2>/dev/null || true
    sleep 3
  fi

  # ── Kill stale SWBBuildService ───────────────────────────────────────────────
  rn_kill_swb

  # ── Kill Metro (conflicts with Xcode bundle phase) ───────────────────────────
  rn_kill_metro

  # ── noowners volume check + stale artifact cleanup ───────────────────────────
  if rn_is_noowners_volume; then
    rn_warn_noowners
  fi
  local products_dir="ios/Build/Products/${configuration}-iphoneos"
  [[ "$apple_platform" == "tvos" ]] && products_dir="ios/Build/Products/${configuration}-appletvos"
  rn_preclear_ios_bundle "$products_dir"

  # ── Build ────────────────────────────────────────────────────────────────────
  local build_log; build_log=$(rn_start_build_log "ios")
  rn_bold "🔨  Building $scheme ($configuration / $apple_platform / $target) [$framework]…"
  echo "    Full log → $build_log"

  # ENABLE_USER_SCRIPT_SANDBOXING=NO: prevents Xcode sandbox from blocking
  # Expo/Metro's bundle-phase script from writing main.jsbundle → EPERM.
  set +o pipefail
  xcodebuild \
    -workspace "$workspace" \
    -scheme     "$scheme" \
    -configuration "$configuration" \
    -destination "$destination" \
    ENABLE_USER_SCRIPT_SANDBOXING=NO \
    -allowProvisioningUpdates \
    2>&1 | tee "$build_log" | grep --line-buffered -E "^(›|❌|error:)" || true
  local build_exit="${PIPESTATUS[0]}"
  set -o pipefail

  if [[ $build_exit -ne 0 ]] || ! grep -q "\*\* BUILD SUCCEEDED \*\*" "$build_log"; then
    echo ""
    rn_red "Build failed. Last errors:"
    grep -E "^[[:space:]]*(error:|❌)" "$build_log" | grep -v "^note:" | head -20 || true
    echo "Full log: $build_log"
    exit 1
  fi

  # ── Locate .app ──────────────────────────────────────────────────────────────
  local app
  app=$(find "$products_dir" -maxdepth 1 -name "*.app" 2>/dev/null | head -1)

  # Simulator builds may land under Build/Products/<Config>-iphonesimulator
  if [[ -z "$app" && "$target" == "simulator" ]]; then
    local sim_products_dir="ios/Build/Products/${configuration}-iphonesimulator"
    [[ "$apple_platform" == "tvos" ]] && sim_products_dir="ios/Build/Products/${configuration}-appletvsimulator"
    app=$(find "$sim_products_dir" -maxdepth 1 -name "*.app" 2>/dev/null | head -1)
  fi

  [[ -n "$app" ]] || rn_die "Cannot find .app after build.\nCheck $build_log"
  rn_green "✅  Build succeeded: $app"

  [[ "$no_install" == "1" ]] && return 0

  # ── Install ──────────────────────────────────────────────────────────────────
  if [[ "$target" == "simulator" ]]; then
    rn_bold "📲  Installing on simulator ${display_name}…"
    # Boot the simulator if needed
    xcrun simctl boot "$udid" 2>/dev/null || true
    xcrun simctl install "$udid" "$app" 2>&1
    # Launch the app (get bundle ID from Info.plist)
    local bundle_id
    bundle_id=$(defaults read "$(realpath "$app")/Info" CFBundleIdentifier 2>/dev/null || true)
    if [[ -n "$bundle_id" ]]; then
      xcrun simctl launch "$udid" "$bundle_id" 2>&1 || true
    fi
    rn_green "✅  $app_name installed + launched on simulator $display_name."
    echo "    Open Simulator.app to interact."
  else
    rn_bold "📲  Installing on ${display_name}…"
    xcrun devicectl device install app --device "$udid" "$app" 2>&1
    rn_green "✅  $app_name installed on $display_name."
    echo "    Launch from the Home Screen. No dev server needed — JS is embedded."
  fi
}

# ── Arg parser (standalone execution) ────────────────────────────────────────

rn_ios_run() {
  export RN_IOS_PLATFORM="ios"
  export RN_IOS_TARGET="device"
  export RN_IOS_CONFIG="Release"
  export RN_IOS_SCHEME=""
  export RN_IOS_SIM_NAME=""
  export RN_IOS_NO_INSTALL="0"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform)   export RN_IOS_PLATFORM="$2";   shift 2 ;;
      --target)     export RN_IOS_TARGET="$2";     shift 2 ;;
      --config)     export RN_IOS_CONFIG="$2";     shift 2 ;;
      --scheme)     export RN_IOS_SCHEME="$2";     shift 2 ;;
      --sim-name)   export RN_IOS_SIM_NAME="$2";   shift 2 ;;
      --no-install) export RN_IOS_NO_INSTALL="1";  shift   ;;
      --tvos)       export RN_IOS_PLATFORM="tvos"; shift   ;;
      --simulator)  export RN_IOS_TARGET="simulator"; shift ;;
      --verbose)    set -x;                        shift   ;;
      *) rn_die "Unknown option: $1\nValid: --platform, --target, --config, --scheme, --sim-name, --tvos, --simulator, --no-install, --verbose" ;;
    esac
  done

  rn_ios_build_and_install
}

# ── Standalone entry point ────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  rn_ios_run "$@"
fi
