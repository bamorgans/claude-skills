# tv-preview testing (2026-11-18)

## Builds (macOS, build-tools 36, JDK 17; no device installs)
- Tiny sample page: exit 0, `aapt2 dump badging` -> package com.tvpreview.tv_preview, label "TV Preview", leanback launchable. Warned about local `x.png` reference (correct).
- storm-chaser-all-screens.html `--name "All Screens"`: exit 0, 49 KB, package com.tvpreview.all_screens, label "All Screens". Warned about two `../road-conditions/*.html` links (correct).
- `--serve 8799`: live URL http://<LAN IP>:8799/sample.html baked into assets/tvpreview.properties; HEAD returned 200.
- Not tested: real install/launch, remote keys, Back/Menu bridge on a device, Windows.

## RED (no skill)
Agent wanted to edit the project's own research app (build.js + page switcher) to add the page, reuse its hard-coded server IP, and install. It did ask before installing.

## GREEN (with SKILL.md)
Agent ran the script build-only with `--name` (exit 0), said it would ask before adding `--install 10.0.0.89`, noted the sandbox may need to be off, and reported the relative-link warning. It also saw that `--serve` serves only the page's own folder. No project files were touched.
