---
name: tv-preview
description: Use when the owner wants to see, try or demo an HTML mockup, prototype or page on a TV, Fire TV, Android TV, Google TV, Sony TV or Fire HD / Android tablet, driven by the remote, in any project. Also /tv-preview.
---

# TV Preview

## Overview
`scripts/tv-preview.js` wraps ONE self-contained HTML page in a tiny full-screen WebView APK (no Gradle, no project changes) and installs it over adb. Use it instead of editing a project's own app or sideloading a browser.

## Quick reference
```bash
S=~/.claude/skills/tv-preview/scripts/tv-preview.js
node $S page.html --name "Checkout v2"                  # build only -> ./tv-preview-checkout_v2.apk
node $S page.html --name "Checkout v2" --install 10.0.0.89 --install usb
node $S page.html --serve                               # + live reload from this computer (keeps running)
node $S --help                                          # all options, page contract, device setup
```
- Package is `com.tvpreview.<slug of --name>`: different names install side by side; the same name reinstalls over itself (keystore lives in `scripts/`).
- `--install`: IP (port 5555), `ip:port`, `usb`, or an adb serial. IPs get `adb connect` → `install -r` → launch → `adb disconnect`.
- `--serve`: bakes this computer's LAN IP into the app; on each open it loads the live page if reachable, else the built-in copy. Edit, press Home, reopen.
- The script warns when the page references local files (they are not built in): inline them.

## Safety: ask first
Installing on a TV wakes it, and HDMI-CEC can turn on the TVs in the house. **Ask the owner before every `--install` to a TV.** Building without `--install` needs no ask. Project rules (e.g. "ask before any TV install") still apply.

## Page contract (all optional)
| Signal | Meaning |
|---|---|
| `?tv` in `location.search` | Device is a TV: use the 10-foot layout. Tablets get no `?tv`. |
| Arrows / Enter | Normal `keydown` events. Give items `tabindex`, a visible `:focus` ring, focus something on load. Never leave a state with nothing focused. |
| Back | `keydown` `Escape` with `e.rcBack === true`. `e.preventDefault()` = handled, stay. Not prevented, or `window.rcExitRequested = true` → app exits. |
| Menu key | Calls `window.rcToggleControls()` if defined. |

Debug with `chrome://inspect` (WebView debugging is on).

## Device setup
- Fire TV: Settings → My Fire TV → Developer options → ADB debugging ON (About → tap the name 7× to reveal).
- Android / Google TV (Sony): About → tap Build 7×; Developer options → USB debugging ON; accept "Allow debugging" on the TV once.
- Fire HD / tablets: USB debugging, then `--install usb`.
- **Apple TV: not possible** (tvOS has no WebView). Say so; do not try.
- Needs a JDK and the Android SDK (`ANDROID_HOME`); the script says what is missing. In a sandboxed shell, adb to a network TV may need the sandbox off.
