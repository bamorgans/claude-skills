---
name: device-install
description: Use when a user wants to build or deploy a React Native or Expo app to any target — iOS device, iPhone Simulator, Apple TV, tvOS Simulator, Android phone, Android TV, Fire TV, Google TV, Android Emulator, or web. Triggered by phrases like "install on my phone", "build for device", "deploy to TV", "test on simulator", "web export", "put this on my iPad".
---

# Device Install — RN/Expo on Any Platform

Builds a standalone app (JS bundled in binary, no Metro server) and installs on a connected device, simulator, emulator, or web host. Always run from **project root**.

Works with both **Expo-managed** and **bare React Native** projects.

## Which path — local or EAS cloud?

| Situation | Command |
|-----------|---------|
| USB cable, fast iteration | `rn-device-install ios\|android` |
| No local SDK / first deploy | `rn-device-install ios\|android --eas` |
| Specific EAS build profile | `... --eas --profile production` |
| CI / automated | `eas build` directly |
| iOS device registration | `--eas` — EAS handles UDID enrollment automatically |
| Android first install | `--eas` — open link on device, allow "Install from unknown sources" |

## Quick start

```bash
# EAS cloud builds (no local SDK needed — recommended for first deploy or team sharing)
~/.claude/scripts/rn-device-install ios --eas              # iPhone/iPad via EAS
~/.claude/scripts/rn-device-install android --eas          # Android phone via EAS
~/.claude/scripts/rn-device-install ios --eas --profile production

# Local builds (USB cable, local SDK required)
~/.claude/scripts/rn-device-install ios                    # iPhone (physical)
~/.claude/scripts/rn-device-install ios --simulator        # iOS Simulator
~/.claude/scripts/rn-device-install ios --tvos             # Apple TV
~/.claude/scripts/rn-device-install android               # Android phone
~/.claude/scripts/rn-device-install android --emulator    # Android Emulator
~/.claude/scripts/rn-device-install android --flavor fireTV  # Fire TV / Android TV

# Web
~/.claude/scripts/rn-device-install web                   # Expo web export
~/.claude/scripts/rn-device-install web --serve           # Export + local preview
~/.claude/scripts/rn-device-install web --deploy vercel   # Export + Vercel deploy
```

## Platform routing

| Target | Skill | Script |
|--------|-------|--------|
| iOS device, iPhone Simulator | `ios-device-install` | `platform/rn-ios.sh` |
| tvOS / Apple TV / tvOS Simulator | `ios-device-install` | `platform/rn-ios.sh --tvos` |
| Android phone/tablet, Android Emulator | `android-device-install` | `platform/rn-android.sh` |
| Android TV, Fire TV, Google TV | `android-device-install` | `platform/rn-android.sh --flavor` |
| Web (Expo export, Vercel, Netlify, EAS) | `web-deploy` | `platform/rn-web.sh` |

Load the platform-specific skill for detailed gotchas and options.

## Composable scripts

```bash
# Source individual modules for scripted pipelines
source ~/.claude/scripts/lib/rn-common.sh       # shared helpers
source ~/.claude/scripts/platform/rn-ios.sh     # defines rn_ios_run
source ~/.claude/scripts/platform/rn-android.sh # defines rn_android_run
source ~/.claude/scripts/platform/rn-web.sh     # defines rn_web_run

# Set env vars, then call the function directly
RN_IOS_PLATFORM=tvos RN_IOS_TARGET=simulator rn_ios_build_and_install
RN_ANDROID_FLAVOR=fireTV rn_android_build_and_install
```

## Project integration (package.json)

Add these once per project — no per-project deploy scripts needed:

```json
{
  "scripts": {
    "deploy:ios":     "~/.claude/scripts/rn-device-install ios --eas",
    "deploy:android": "~/.claude/scripts/rn-device-install android --eas"
  }
}
```
