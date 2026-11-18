#!/usr/bin/env node
/**
 * @file tv-preview.js
 * @date 2026-11-18
 * @license MIT
 *
 * @description
 * Builds a tiny Android viewer APK that shows one self-contained HTML page full screen on Fire TV, Android TV,
 * Google TV and Fire / Android tablets, driven by the remote, and optionally installs it over adb.
 * No Gradle: javac + d8 + aapt2 + zipalign + apksigner from the Android SDK, jar from the JDK.
 *
 * @notes
 * - Cross-platform Node (macOS, Windows, Linux). Run --help for usage.
 * - Package com.tvpreview.<slug of label>, so several previews install side by side.
 * - Signed with tv-preview.keystore next to this script (created once) so rebuilds install over old ones.
 */
"use strict";
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const zlib = require("node:zlib");

const HELP = `tv-preview: show one HTML page full screen on Fire TV / Android TV / Google TV / Fire HD, driven by the remote.

Usage:
  node tv-preview.js <page.html> [--name "App label"] [--install <target> ...] [--serve [port]] [--out <dir>]

  <page.html>        Self-contained page (inline CSS/JS/images). Built in as assets/index.html.
  --name LABEL       Launcher label (default "TV Preview"). Package = com.tvpreview.<slug>; a different label
                     installs a separate app alongside.
  --install TARGET   Repeatable. IP (port 5555 assumed), ip:port, "usb" (the one USB device), or an adb serial.
                     IP targets: adb connect -> install -r -> launch -> adb disconnect.
  --serve [PORT]     Serve the page's folder over HTTP (default 8765) on this computer's LAN IP and bake that URL
                     into the app: on every launch/resume it loads the live copy when reachable, else the built-in
                     one. Keeps running (Ctrl+C to stop). Edit the page, press Home then reopen the app to refresh.
  --out DIR          Where the APK goes (default: current directory).

Page contract (all optional):
  ?tv in location.search            the device is a TV (leanback / TV UI mode): use the 10-foot layout.
  Arrows / Enter                    normal keydown events (ArrowUp..., Enter). Give focusable items tabindex
                                    and a visible :focus ring; focus something on load.
  Back                              keydown Escape with e.rcBack === true, sent to document.activeElement.
                                    Call e.preventDefault() to stay in the app (you handled it, e.g. closed a
                                    panel). Not prevented, or window.rcExitRequested = true -> the app exits.
  Menu key                          calls window.rcToggleControls() if defined.
  Debug                             chrome://inspect on the computer (WebView debugging is on).

Device setup: Fire TV: Settings > My Fire TV > Developer options > ADB debugging ON (tap About > name 7x to
reveal). Android/Google TV (Sony): Settings > System > About > tap Build 7x, then Developer options > USB
debugging ON; accept the "Allow debugging" prompt on the TV the first time. Fire HD: Developer options >
USB debugging, then --install usb. Apple TV is not supported (tvOS has no WebView).
Needs: JDK (javac, jar, keytool), Android SDK build-tools + a platform (ANDROID_HOME / ANDROID_SDK_ROOT), adb.
`;

function fail(msg) { console.error(`tv-preview: ${msg}`); process.exit(1); }

// ---------- args ----------
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("--help") || argv.includes("-h")) { console.log(HELP); process.exit(argv.length ? 0 : 1); }
let page = null, label = "TV Preview", serve = null, outDir = process.cwd();
const installs = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--name") label = argv[++i];
  else if (a === "--install") installs.push(argv[++i]);
  else if (a === "--out") outDir = path.resolve(argv[++i]);
  else if (a === "--serve") serve = /^\d+$/.test(argv[i + 1] || "") ? Number(argv[++i]) : 8765;
  else if (a.startsWith("--")) fail(`unknown option ${a} (see --help)`);
  else page = path.resolve(a);
}
if (!page || !fs.existsSync(page)) fail(`page not found: ${page || "(none)"}`);
if (!label || installs.some((t) => !t)) fail("missing value for --name / --install");
const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "p$1") || "app";
const pkg = `com.tvpreview.${slug}`;

// ---------- page check: warn on local relative references ----------
const html = fs.readFileSync(page, "utf8");
const refs = new Set();
for (const m of html.matchAll(/\b(?:src|href)\s*=\s*["']([^"'#][^"']*)["']/gi)) {
  const u = m[1].trim();
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(u)) continue; // http:, data:, javascript:, mailto:, //cdn
  if (fs.existsSync(path.resolve(path.dirname(page), u.split(/[?#]/)[0]))) refs.add(u);
}
if (refs.size) console.warn(`tv-preview: WARNING the page references local files that are NOT built in: ${[...refs].join(", ")}\n  Inline them, or use --serve (files inside the page folder load live while this computer is reachable).`);

// ---------- SDK ----------
const sdkCandidates = [process.env.ANDROID_HOME, process.env.ANDROID_SDK_ROOT,
  path.join(os.homedir(), "Library", "Android", "sdk"),
  process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, "Android", "Sdk"),
  path.join(os.homedir(), "Android", "Sdk")].filter(Boolean);
const sdk = sdkCandidates.find((d) => fs.existsSync(path.join(d, "build-tools")) && fs.existsSync(path.join(d, "platforms")));
if (!sdk) fail(`Android SDK not found (looked in: ${sdkCandidates.join(", ")}). Install Android Studio or the command-line tools with build-tools and a platform, then set ANDROID_HOME.`);
const newest = (dir, ok) => fs.readdirSync(dir).filter(ok).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).pop();
const btName = newest(path.join(sdk, "build-tools"), (d) => fs.existsSync(path.join(sdk, "build-tools", d, process.platform === "win32" ? "aapt2.exe" : "aapt2")));
const platName = newest(path.join(sdk, "platforms"), (d) => fs.existsSync(path.join(sdk, "platforms", d, "android.jar")));
if (!btName || !platName) fail(`no build-tools or platform with android.jar under ${sdk}`);
const bt = path.join(sdk, "build-tools", btName);
const androidJar = path.join(sdk, "platforms", platName, "android.jar");
const tool = (n) => { for (const ext of process.platform === "win32" ? [".exe", ".bat", ""] : [""]) { const p = path.join(bt, n + ext); if (fs.existsSync(p)) return p; } fail(`${n} missing in ${bt}`); };
const adbPath = (() => { const p = path.join(sdk, "platform-tools", process.platform === "win32" ? "adb.exe" : "adb"); return fs.existsSync(p) ? p : "adb"; })();
const jdk = (n) => process.env.JAVA_HOME ? path.join(process.env.JAVA_HOME, "bin", n + (process.platform === "win32" ? ".exe" : "")) : n;
const run = (cmd, args, opts = {}) => {
  try { return execFileSync(cmd, args, { stdio: "inherit", shell: process.platform === "win32" && /\.bat$/i.test(cmd), ...opts }); }
  catch (e) { if (e.code === "ENOENT") fail(`${cmd} not found (install a JDK / Android SDK, or set JAVA_HOME / ANDROID_HOME)`); throw e; }
};

// ---------- LAN IP ----------
function lanIp() {
  const all = [];
  for (const [name, list] of Object.entries(os.networkInterfaces())) for (const a of list || []) {
    if ((a.family === "IPv4" || a.family === 4) && !a.internal && !a.address.startsWith("169.254.")) all.push({ name, ip: a.address });
  }
  const rank = (x) => (/^(192\.168|10)\./.test(x.ip) ? 0 : /^172\.(1[6-9]|2\d|3[01])\./.test(x.ip) ? 1 : 2) + (/vbox|vmnet|docker|utun|bridge|veth/i.test(x.name) ? 5 : 0);
  return all.sort((a, b) => rank(a) - rank(b))[0]?.ip || null;
}
let liveUrl = "";
if (serve !== null) {
  const ip = lanIp();
  if (!ip) fail("--serve: no LAN IPv4 address found");
  liveUrl = `http://${ip}:${serve}/${encodeURIComponent(path.basename(page))}`;
}

// ---------- icons (generated, neutral: a TV outline with a play triangle) ----------
function png(w, h, pixel) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const o = y * (w * 4 + 1) + 1 + x * 4; const c = pixel(x, y); raw[o] = c[0]; raw[o + 1] = c[1]; raw[o + 2] = c[2]; raw[o + 3] = 255; }
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (b) => { let c = ~0; for (const x of b) c = crcT[(c ^ x) & 0xff] ^ (c >>> 8); return (~c) >>> 0; };
  const chunk = (t, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
function art(w, h) {
  const bg = [38, 50, 72], fg = [235, 240, 248], s = Math.min(w, h);
  const cx = w / 2, cy = h / 2, sw = s * 0.62, sh = s * 0.42, t = Math.max(2, s * 0.045);
  return png(w, h, (x, y) => {
    const dx = Math.abs(x - cx), dy = Math.abs(y - (cy - s * 0.04));
    const frame = dx <= sw / 2 && dy <= sh / 2 && (dx >= sw / 2 - t || dy >= sh / 2 - t);
    const stand = Math.abs(x - cx) <= s * 0.14 && y >= cy + sh / 2 + s * 0.04 && y <= cy + sh / 2 + s * 0.04 + t;
    const px = x - (cx - s * 0.07), py = y - (cy - s * 0.04);
    const play = px >= 0 && px <= s * 0.16 && Math.abs(py) <= (s * 0.1) * (1 - px / (s * 0.16));
    return frame || stand || play ? fg : bg;
  });
}

// ---------- build ----------
const work = fs.mkdtempSync(path.join(os.tmpdir(), "tv-preview-"));
const assets = path.join(work, "assets"), classes = path.join(work, "classes"), res = path.join(work, "res");
for (const d of [assets, classes, path.join(res, "mipmap-xxxhdpi"), path.join(res, "drawable-xhdpi")]) fs.mkdirSync(d, { recursive: true });
fs.copyFileSync(page, path.join(assets, "index.html"));
fs.writeFileSync(path.join(assets, "tvpreview.properties"), `live=${liveUrl.replace(/:/g, "\\:")}\n`);
fs.writeFileSync(path.join(res, "mipmap-xxxhdpi", "ic_launcher.png"), art(192, 192));
fs.writeFileSync(path.join(res, "drawable-xhdpi", "banner.png"), art(320, 180));
const xmlEsc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
fs.writeFileSync(path.join(work, "AndroidManifest.xml"), `<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="${pkg}" android:versionCode="${Math.floor(Date.now() / 60000) % 2000000000}" android:versionName="1.0">
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-sdk android:minSdkVersion="22" android:targetSdkVersion="34"/>
  <uses-feature android:name="android.software.leanback" android:required="false"/>
  <uses-feature android:name="android.hardware.touchscreen" android:required="false"/>
  <application android:label="${xmlEsc(label)}" android:icon="@mipmap/ic_launcher" android:banner="@drawable/banner" android:theme="@android:style/Theme.NoTitleBar.Fullscreen" android:hardwareAccelerated="true" android:usesCleartextTraffic="true">
    <activity android:name="com.tvpreview.viewer.MainActivity" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden|keyboard|navigation">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
        <category android:name="android.intent.category.LEANBACK_LAUNCHER"/>
      </intent-filter>
    </activity>
  </application>
</manifest>
`);

run(jdk("javac"), ["--release", "8", "-nowarn", "-classpath", androidJar, "-d", classes, path.join(__dirname, "java", "MainActivity.java")], { stdio: ["inherit", "inherit", "pipe"] });
const classFiles = [];
(function walk(d) { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); fs.statSync(p).isDirectory() ? walk(p) : p.endsWith(".class") && classFiles.push(p); } })(classes);
run(tool("d8"), ["--min-api", "22", "--lib", androidJar, "--output", work, ...classFiles]);
const resZip = path.join(work, "res.zip"), base = path.join(work, "base.apk"), aligned = path.join(work, "aligned.apk");
run(tool("aapt2"), ["compile", "--dir", res, "-o", resZip]);
run(tool("aapt2"), ["link", "-o", base, "-I", androidJar, "--manifest", path.join(work, "AndroidManifest.xml"), "-A", assets, "-R", resZip, "--auto-add-overlay"]);
run(jdk("jar"), ["--update", "--no-manifest", "--file", base, "-C", work, "classes.dex"]);
run(tool("zipalign"), ["-f", "4", base, aligned]);

const ks = path.join(__dirname, "tv-preview.keystore");
if (!fs.existsSync(ks)) run(jdk("keytool"), ["-genkeypair", "-keystore", ks, "-storepass", "tvpreview", "-keypass", "tvpreview", "-alias", "tvpreview", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-dname", "CN=TV Preview"]);
fs.mkdirSync(outDir, { recursive: true });
const apk = path.join(outDir, `tv-preview-${slug}.apk`);
run(tool("apksigner"), ["sign", "--ks", ks, "--ks-pass", "pass:tvpreview", "--key-pass", "pass:tvpreview", "--out", apk, aligned]);
try { fs.rmSync(apk + ".idsig", { force: true }); fs.rmSync(work, { recursive: true, force: true }); } catch { /* temp cleanup only */ }
console.log(`Built ${apk} (${Math.round(fs.statSync(apk).size / 1024)} KB)  label "${label}"  package ${pkg}${liveUrl ? `  live ${liveUrl}` : ""}`);

// ---------- install ----------
const component = `${pkg}/com.tvpreview.viewer.MainActivity`;
let failed = 0;
for (const t of installs) {
  const isIp = /^\d{1,3}(\.\d{1,3}){3}(:\d+)?$/.test(t);
  const sel = t === "usb" ? ["-d"] : ["-s", isIp && !t.includes(":") ? `${t}:5555` : t];
  try {
    if (isIp) {
      const out = execFileSync(adbPath, ["connect", sel[1]], { encoding: "utf8" });
      process.stdout.write(out);
      if (/unable|failed|refused|cannot/i.test(out)) throw new Error(`adb connect ${sel[1]} failed (ADB debugging on? same network?)`);
    }
    run(adbPath, [...sel, "install", "-r", apk]);
    run(adbPath, [...sel, "shell", "am", "start", "-S", "-n", component]);
    console.log(`Installed and launched on ${t}`);
  } catch (e) { failed++; console.error(`tv-preview: install on ${t} failed: ${e.message}`); }
  finally { if (isIp) { try { execFileSync(adbPath, ["disconnect", sel[1]], { stdio: "ignore" }); } catch { /* already gone */ } } }
}

// ---------- serve ----------
if (serve !== null) {
  const root = path.dirname(page);
  const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp", ".gif": "image/gif", ".mp4": "video/mp4", ".woff2": "font/woff2" };
  http.createServer((req, resp) => {
    const rel = decodeURIComponent((req.url || "/").split("?")[0]);
    const file = path.join(root, path.normalize(rel).replace(/^([/\\])+/, ""));
    if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { resp.writeHead(404); return resp.end(); }
    resp.writeHead(200, { "Content-Type": types[path.extname(file).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-store" });
    if (req.method === "HEAD") return resp.end();
    fs.createReadStream(file).pipe(resp);
  }).on("error", (e) => fail(`--serve: ${e.message}`))
    .listen(serve, "0.0.0.0", () => console.log(`Serving ${root} at ${liveUrl.replace(/[^/]*$/, "")} (Ctrl+C to stop; allow incoming connections if the firewall asks)`));
} else if (failed) process.exit(1);
