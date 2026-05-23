---
name: web-deploy
description: Use when exporting, previewing, or deploying a React Native or Expo app to the web. Triggered by phrases like "deploy to web", "web export", "publish to Vercel", "host on Netlify", "preview in browser", "Expo web build", or "EAS deploy".
---

# Web Deploy — Expo / React Native Web

Exports a React Native / Expo project for web and optionally serves locally or deploys to a host.

## Script

```bash
~/.claude/scripts/platform/rn-web.sh [options]
# or via entry point:
~/.claude/scripts/rn-device-install web [options]
```

## Options

| Flag | Default | Notes |
|------|---------|-------|
| `--output DIR` | `dist` | Export destination directory |
| `--serve` | off | Start local preview server (port 8080) after export |
| `--deploy vercel\|netlify\|eas` | none | Deploy after export |
| `--base-url PATH` | — | Base path for subdirectory hosting |
| `--verbose` | off | `set -x` |

## Framework detection

| Project type | Build command used |
|---|---|
| Expo managed / Expo Router | `npx expo export --platform web` |
| Bare RN + webpack | `npx react-native bundle --platform web` |
| Fallback | `npx expo export --platform web` |

## Quickstart examples

```bash
# Export only
rn-device-install web

# Export + local preview
rn-device-install web --serve

# Export + deploy to Vercel
rn-device-install web --deploy vercel

# Export to custom dir + deploy to Netlify
rn-device-install web --output build --deploy netlify
```

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot use import statement` | Some RN-only modules aren't web-compatible | Add web-safe aliases in `metro.config.js` or use `Platform.select` |
| Maps don't render on web | `react-native-maps` is native-only | Use `MapSection.web.tsx` platform split (Metro resolver) |
| Camera errors on web | Camera requires native device | Guard with `Platform.OS !== 'web'` |
| SQLite errors on web | `expo-sqlite` needs wasm config | Add `metro.config.js` wasm stub or use AsyncStorage for web |
| Blank screen after deploy | Wrong `--base-url` | Match the subdirectory path on your host |
| `vercel` not found | CLI not installed | `npm i -g vercel` |
| `netlify` not found | CLI not installed | `npm i -g netlify-cli` |

## Composable usage

```bash
source ~/.claude/scripts/platform/rn-web.sh

# Export to custom dir
RN_WEB_OUTPUT=build rn_web_build_and_deploy

# Export + deploy to EAS
RN_WEB_DEPLOY=eas rn_web_build_and_deploy

# Export + local preview
RN_WEB_SERVE=1 rn_web_build_and_deploy
```

## EAS Hosting

For Expo-managed projects, EAS Hosting is the recommended production path:

```bash
# One-time setup
eas login
eas build:configure

# Deploy
rn-device-install web --deploy eas
# or directly:
npx expo export --platform web && eas deploy --platform web
```
