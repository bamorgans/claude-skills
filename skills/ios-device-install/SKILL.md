---
name: ios-device-install
description: Use when building or installing a React Native or Expo app on an iOS device, iPhone Simulator, Apple TV, or tvOS Simulator. Also use when diagnosing EPERM on main.jsbundle, ReactCodegen failures, provisioning errors, UDID not found, or Xcode sandbox issues.
---

# iOS / tvOS Device Install

Builds with Xcode and installs on a physical device or simulator. Covers iPhone, iPad, Apple TV, and their simulators.

## Full process (first time on a new device)

1. **Register device** — use EAS; it handles UDID enrollment automatically:
   `~/.claude/scripts/rn-device-install ios --eas`
2. **Prerequisites** — Xcode + CocoaPods must be installed:
   `brew install cocoapods`
3. **Configure** — generate the native project if needed:
   `npx expo prebuild --platform ios && cd ios && pod install && cd ..`
   The script detects a missing workspace and prints these instructions automatically.
4. **Deploy (EAS cloud, no cable):** `~/.claude/scripts/rn-device-install ios --eas`
   **OR local USB build:** `~/.claude/scripts/rn-device-install ios`

Steps 2–3 are one-time per machine. Steps 1 + 4 repeat when you want to push an update.

## Script

```bash
~/.claude/scripts/platform/rn-ios.sh [options]
# or via entry point:
~/.claude/scripts/rn-device-install ios [options]
```

## Options

| Flag | Default | Notes |
|------|---------|-------|
| `--platform ios\|tvos` | `ios` | `tvos` targets Apple TV |
| `--target device\|simulator` | `device` | |
| `--scheme NAME` | workspace filename | Xcode scheme |
| `--config Release\|Debug` | `Release` | |
| `--sim-name "iPhone 16 Pro"` | first booted | Simulator name |
| `--no-install` | off | Build only |
| `--verbose` | off | `set -x` |
| `--tvos` | — | Shorthand for `--platform tvos` |
| `--simulator` | — | Shorthand for `--target simulator` |
| `--apple-team TEAM_ID` | see below | EAS only: override Apple Developer Team ID |
| `--profile NAME` | `preview` | EAS only: build profile from `eas.json` |

### Apple Team selection (EAS builds only)

Resolution order — first non-empty value wins:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `--apple-team` flag | `rn-device-install ios --eas --apple-team A1B2C3D4` |
| 2 | `EXPO_APPLE_TEAM_ID` env var | Official EAS var — already used by CI / power users |
| 3 | `APPLE_TEAM_ID` env var | Shorter convenience alias |
| 4 | `~/.claude/apple-team` file | Machine-wide default (one-time setup) |

**Set a machine-wide default** (avoids passing the flag every time):

```bash
echo "YOUR_TEAM_ID" > ~/.claude/apple-team
```

**Find your Team ID** — sign in at developer.apple.com → Account → Membership → Team ID.
Or run `npx eas credentials --platform ios` and EAS will list all teams tied to your Apple ID.

**One-off override** without changing the default:

```bash
# via flag
~/.claude/scripts/rn-device-install ios --eas --apple-team A1B2C3D4E5
# via EAS's native env var (also works in CI)
EXPO_APPLE_TEAM_ID=A1B2C3D4E5 npm run deploy:ios
# via short alias
APPLE_TEAM_ID=A1B2C3D4E5 npm run deploy:ios
```

## What the script does

1. Auto-detects `ios/*.xcworkspace` and scheme
2. Finds device UDID via `xcrun devicectl` (iOS 17+) or `xcrun xctrace` (older)
3. Closes Xcode if open — releases `ios/Build/` file locks
4. Kills stale `SWBBuildService` (PIF/stall errors)
5. Kills Metro on port 8081
6. Detects `noowners` APFS external volumes — warns + prints permanent fix
7. **Pre-cleans** stale `main.jsbundle` + `resources-to-copy-*.txt` before build
8. Runs `xcodebuild` with `ENABLE_USER_SCRIPT_SANDBOXING=NO` + `-allowProvisioningUpdates`
9. Physical device → `xcrun devicectl device install app`  
   Simulator → `xcrun simctl install` + auto-launch

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| `EPERM` on `main.jsbundle` | Xcode script sandbox blocks Metro bundle write | `ENABLE_USER_SCRIPT_SANDBOXING=NO` — the key flag |
| `EPERM` persists after above | Project on external APFS volume with `noowners` mount — kernel denies `unlink` of file from prior session | Script pre-cleans stale bundle. Permanent fix: Xcode → File → Project Settings → Build Location → Custom → `~/Library/Developer/Xcode/DerivedData` |
| `EPERM` on `resources-to-copy-*.txt` | Same sandbox / `noowners` issue, resources phase | Script pre-cleans these too |
| ReactCodegen files not found | Entire `ios/Build/` or `ios/build/` deleted between builds | **Never** `rm -rf ios/build/` — script only removes specific JS output files |
| Build stalls / PIF error | `SWBBuildService` stuck from old Xcode session | Script kills it automatically; manual: `pkill -x SWBBuildService` |
| UDID not found | Phone locked or hasn't trusted computer | Unlock phone, tap "Trust This Computer" |
| Provisioning fails | Device not in Apple Developer portal | Script uses `-allowProvisioningUpdates` (auto-registers with Automatic signing) |
| Simulator not found | No matching simulator name | `xcrun simctl list devices available` to browse names |
| tvOS build uses iOS scheme | Wrong scheme auto-detected | Pass `--scheme MyApp-tvOS` explicitly |

## Framework detection

Script auto-detects Expo vs bare RN via `package.json` and adjusts the build log label. Both use `xcodebuild` identically — the JS bundler (Metro/Expo CLI) is invoked by the Xcode build phase script.

## Composable usage

```bash
source ~/.claude/scripts/platform/rn-ios.sh

# Physical Apple TV
RN_IOS_PLATFORM=tvos RN_IOS_TARGET=device rn_ios_build_and_install

# Simulator with specific device
RN_IOS_TARGET=simulator RN_IOS_SIM_NAME="iPhone 16 Pro" rn_ios_build_and_install

# Build only, no install (CI)
RN_IOS_NO_INSTALL=1 rn_ios_build_and_install
```

## Manual build (bypass script)

```bash
UDID=$(xcrun devicectl list devices 2>/dev/null | grep -iE "iphone|ipad" | grep -iE "connected|available" | head -1 | awk '{print $3}')

xcodebuild \
  -workspace ios/MyApp.xcworkspace \
  -scheme MyApp \
  -configuration Release \
  -destination "id=$UDID" \
  ENABLE_USER_SCRIPT_SANDBOXING=NO \
  -allowProvisioningUpdates

xcrun devicectl device install app --device "$UDID" \
  "ios/Build/Products/Release-iphoneos/MyApp.app"
```
