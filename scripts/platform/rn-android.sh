#!/usr/bin/env bash
# rn-android.sh — Build + install a React Native / Expo app on Android.
#
# Covers: Android phones, Android TV, Fire TV, Google TV.
# All are standard Android targets reachable via adb — only Gradle flavor differs.
#
# Works with Expo-managed and bare React Native projects.
#
# Standalone (from project root):
#   platform/rn-android.sh [options]
#
# Composable (source + call):
#   source platform/rn-android.sh
#   rn_android_run [options]
#
# Options:
#   --config    release|debug           (default: release)
#   --flavor    NAME                    Gradle product flavor (e.g. fireTV, androidTv)
#   --target    device|emulator|auto    (default: auto — prefers real device)
#   --device    SERIAL                  specific adb serial (skips auto-detect)
#   --avd       NAME                    emulator AVD name (target=emulator)
#   --no-install                        build only, skip adb install
#   --verbose                           set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/rn-common.sh"

# ── ADB device detection ──────────────────────────────────────────────────────

_rn_android_find_device() {
  local prefer_target="${1:-auto}"  # device | emulator | auto

  command -v adb &>/dev/null || rn_die "adb not found.\nInstall Android SDK platform-tools and add to PATH."

  local all_devices
  all_devices=$(adb devices 2>/dev/null \
    | grep -v "List of\|offline\|unauthorized\|^$" \
    | grep "[[:space:]]device$" \
    | awk '{print $1}' || true)

  [[ -z "$all_devices" ]] && return 1

  if [[ "$prefer_target" == "emulator" ]]; then
    echo "$all_devices" | grep "^emulator-" | head -1 || echo "$all_devices" | head -1
  elif [[ "$prefer_target" == "device" ]]; then
    echo "$all_devices" | grep -v "^emulator-" | head -1 || echo "$all_devices" | head -1
  else
    # auto: prefer real device over emulator
    echo "$all_devices" | grep -v "^emulator-" | head -1 || echo "$all_devices" | head -1
  fi
}

_rn_android_start_emulator() {
  local avd_name="${1:?avd_name required}"
  command -v emulator &>/dev/null || rn_die "emulator not found in PATH. Ensure Android SDK emulator is installed."
  rn_bold "🚀  Starting emulator: $avd_name…"
  emulator -avd "$avd_name" -no-snapshot-load &>/dev/null &
  # Wait up to 60s for the device to come online
  local waited=0
  while [[ $waited -lt 60 ]]; do
    local serial
    serial=$(adb devices 2>/dev/null | grep "^emulator-" | grep "[[:space:]]device$" | head -1 | awk '{print $1}' || true)
    if [[ -n "$serial" ]]; then
      # Wait for boot_completed
      if adb -s "$serial" shell getprop sys.boot_completed 2>/dev/null | grep -q "^1"; then
        echo "$serial"
        return 0
      fi
    fi
    sleep 3; ((waited+=3))
  done
  rn_die "Emulator $avd_name did not boot within 60s."
}

_rn_android_list_avds() {
  emulator -list-avds 2>/dev/null || avdmanager list avd --compact 2>/dev/null | grep "Name:" | awk '{print $2}' || true
}

# ── APK location helper ───────────────────────────────────────────────────────

_rn_android_find_apk() {
  local config_lower="${1:-release}"
  local flavor="${2:-}"

  local search_root="android/app/build/outputs/apk"
  local apk

  if [[ -n "$flavor" ]]; then
    # Flavor builds: app/build/outputs/apk/<flavor>/<config>/*.apk
    apk=$(find "$search_root/${flavor}/${config_lower}" -name "*.apk" 2>/dev/null \
      | grep -iv "unsigned\|unaligned" | head -1 || true)
  fi

  # Standard: app/build/outputs/apk/<config>/*.apk
  [[ -z "$apk" ]] && apk=$(find "$search_root/${config_lower}" -name "*.apk" 2>/dev/null \
    | grep -iv "unsigned\|unaligned" | head -1 || true)

  # Fallback: any non-unsigned APK anywhere in apk/ tree
  [[ -z "$apk" ]] && apk=$(find "$search_root" -name "*.apk" 2>/dev/null \
    | grep -iv "unsigned\|unaligned" | head -1 || true)

  echo "$apk"
}

# ── Main build + install function ─────────────────────────────────────────────
# All state via env vars:
#   RN_ANDROID_CONFIG     release|debug      (default: release)
#   RN_ANDROID_FLAVOR     Gradle flavor      (default: empty = no flavor)
#   RN_ANDROID_TARGET     device|emulator|auto
#   RN_ANDROID_DEVICE     specific serial
#   RN_ANDROID_AVD        AVD name for emulator target
#   RN_ANDROID_NO_INSTALL 1                  (skip install)

rn_android_build_and_install() {
  local configuration="${RN_ANDROID_CONFIG:-release}"
  local flavor="${RN_ANDROID_FLAVOR:-}"
  local target="${RN_ANDROID_TARGET:-auto}"
  local explicit_device="${RN_ANDROID_DEVICE:-}"
  local avd_name="${RN_ANDROID_AVD:-}"
  local no_install="${RN_ANDROID_NO_INSTALL:-0}"

  rn_check_project_root
  rn_preflight_check android
  rn_configure_project android
  local app_name; app_name=$(rn_detect_app_name)
  local framework; framework=$(rn_detect_framework)

  # ── Gradle wrapper ────────────────────────────────────────────────────────
  local gradlew="android/gradlew"
  [[ -f "$gradlew" ]] || rn_die "android/gradlew not found. Run from the project root."
  [[ -x "$gradlew" ]] || chmod +x "$gradlew"

  # ── Device / emulator ────────────────────────────────────────────────────
  local device

  if [[ -n "$explicit_device" ]]; then
    device="$explicit_device"
    rn_bold "📱  Target: $device (explicit)"
  elif [[ "$target" == "emulator" ]]; then
    # Start AVD if specified and not already running
    if [[ -n "$avd_name" ]]; then
      device=$(adb devices 2>/dev/null | grep "^emulator-" | grep "[[:space:]]device$" | head -1 | awk '{print $1}' || true)
      if [[ -z "$device" ]]; then
        device=$(_rn_android_start_emulator "$avd_name")
      fi
    else
      device=$(_rn_android_find_device "emulator")
      if [[ -z "$device" ]]; then
        rn_yellow "No running emulator. Available AVDs:"
        _rn_android_list_avds
        rn_die "Start an emulator first, or use --avd NAME."
      fi
    fi
    rn_bold "🖥️   Emulator: $device"
  elif [[ "$no_install" == "1" ]]; then
    # Build only — no device needed
    device=""
  else
    device=$(_rn_android_find_device "$target")
    if [[ -z "$device" ]]; then
      rn_die "No Android device or emulator found.\n• Enable USB debugging (Settings → Developer options → USB Debugging)\n• Plug in via USB and accept the 'Allow USB debugging' prompt\n• Or start an emulator and retry\n• Run: adb devices"
    fi
    rn_bold "📱  Target: $device"
  fi

  # ── Kill Metro (prevent port 8081 conflicts with RN packager) ────────────
  rn_kill_metro

  # ── Gradle task ──────────────────────────────────────────────────────────
  # Capitalize first letter of config and flavor for Gradle task name.
  local config_cap; config_cap="$(tr '[:lower:]' '[:upper:]' <<< "${configuration:0:1}")${configuration:1}"
  local gradle_task
  if [[ -n "$flavor" ]]; then
    local flavor_cap; flavor_cap="$(tr '[:lower:]' '[:upper:]' <<< "${flavor:0:1}")${flavor:1}"
    gradle_task="assemble${flavor_cap}${config_cap}"
  else
    gradle_task="assemble${config_cap}"
  fi

  local build_log; build_log=$(rn_start_build_log "android")
  rn_bold "🔨  Building Android $configuration${flavor:+ ($flavor)} [$framework]…"
  rn_bold "    Task: $gradle_task"
  echo "    Full log → $build_log"

  set +o pipefail
  (cd android && ./gradlew "$gradle_task" --no-daemon 2>&1) \
    | tee "$build_log" \
    | grep --line-buffered -E "^(> Task|BUILD|FAILED|error)" || true
  local gradle_exit="${PIPESTATUS[0]}"
  set -o pipefail

  if [[ $gradle_exit -ne 0 ]] || grep -q "BUILD FAILED" "$build_log"; then
    echo ""
    rn_red "Build failed. Last errors:"
    grep -E "error:" "$build_log" | head -20 || true
    echo "Full log: $build_log"
    exit 1
  fi

  # ── Locate APK ────────────────────────────────────────────────────────────
  local apk; apk=$(_rn_android_find_apk "$configuration" "$flavor")
  [[ -n "$apk" ]] || rn_die "Cannot find APK in android/app/build/outputs/apk/\nRun: ls android/app/build/outputs/apk/"
  rn_green "✅  Build succeeded: $apk"

  [[ "$no_install" == "1" ]] && return 0

  # ── Install ───────────────────────────────────────────────────────────────
  rn_bold "📲  Installing on $device…"
  adb -s "$device" install -r "$apk" 2>&1
  echo ""
  rn_green "✅  $app_name installed on $device."
  echo "    Launch from the app drawer. No dev server needed — JS is embedded."
}

# ── Arg parser ────────────────────────────────────────────────────────────────

rn_android_run() {
  export RN_ANDROID_CONFIG="release"
  export RN_ANDROID_FLAVOR=""
  export RN_ANDROID_TARGET="auto"
  export RN_ANDROID_DEVICE=""
  export RN_ANDROID_AVD=""
  export RN_ANDROID_NO_INSTALL="0"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --config)     export RN_ANDROID_CONFIG="$2";  shift 2 ;;
      --flavor)     export RN_ANDROID_FLAVOR="$2";  shift 2 ;;
      --target)     export RN_ANDROID_TARGET="$2";  shift 2 ;;
      --device)     export RN_ANDROID_DEVICE="$2";  shift 2 ;;
      --avd)        export RN_ANDROID_AVD="$2";     shift 2 ;;
      --no-install) export RN_ANDROID_NO_INSTALL="1"; shift ;;
      --emulator)   export RN_ANDROID_TARGET="emulator"; shift ;;
      --verbose)    set -x;                         shift   ;;
      *) rn_die "Unknown option: $1\nValid: --config, --flavor, --target, --device, --avd, --emulator, --no-install, --verbose" ;;
    esac
  done

  rn_android_build_and_install
}

# ── Standalone entry point ────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  rn_android_run "$@"
fi
