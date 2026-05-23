# claude-skills

Claude Code skills and scripts for React Native / Expo development.
Platform-generic — works with any Expo or bare RN project.

## Install

```bash
git clone git@github.com:bamorgans/claude-skills.git
cd claude-skills && ./install.sh
```

Updates: `git pull` (symlinks pick up changes automatically).

## What's included

| Skill | Trigger phrases |
|-------|----------------|
| `device-install` | "install on my phone", "build for device", "deploy to TV" |
| `ios-device-install` | iPhone, iPad, Apple TV, tvOS Simulator, EPERM errors |
| `android-device-install` | Android phone, Android TV, Fire TV, Google TV, adb errors |
| `web-deploy` | web export, Vercel, Netlify, EAS Hosting |

## Quick-start

```bash
# EAS cloud builds (no local SDK needed)
~/.claude/scripts/rn-device-install ios --eas
~/.claude/scripts/rn-device-install android --eas
~/.claude/scripts/rn-device-install android --eas --profile production

# Local builds (USB cable)
~/.claude/scripts/rn-device-install ios
~/.claude/scripts/rn-device-install ios --simulator
~/.claude/scripts/rn-device-install ios --tvos
~/.claude/scripts/rn-device-install android
~/.claude/scripts/rn-device-install android --emulator
~/.claude/scripts/rn-device-install android --flavor fireTV

# Web
~/.claude/scripts/rn-device-install web
~/.claude/scripts/rn-device-install web --deploy vercel
```

## Project integration

Add to your project's `package.json`:

```json
{
  "scripts": {
    "deploy:ios":     "~/.claude/scripts/rn-device-install ios --eas",
    "deploy:android": "~/.claude/scripts/rn-device-install android --eas"
  }
}
```

Add to your project's `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(~/.claude/scripts/rn-device-install ios *)",
      "Bash(~/.claude/scripts/rn-device-install android *)",
      "Bash(adb devices)",
      "Bash(adb -s * install -r *)"
    ]
  }
}
```

## Platforms

| Target | Command |
|--------|---------|
| iPhone / iPad (USB) | `rn-device-install ios` |
| iOS Simulator | `rn-device-install ios --simulator` |
| Apple TV (USB) | `rn-device-install ios --tvos` |
| tvOS Simulator | `rn-device-install ios --tvos --simulator` |
| Android phone (USB) | `rn-device-install android` |
| Android Emulator | `rn-device-install android --emulator` |
| Android TV | `rn-device-install android --flavor androidTv` |
| Fire TV | `rn-device-install android --flavor fireTV` |
| Google TV | `rn-device-install android --flavor googleTv` |
| Web (export) | `rn-device-install web` |
| iOS EAS cloud | `rn-device-install ios --eas` |
| Android EAS cloud | `rn-device-install android --eas` |
