package com.tvpreview.viewer;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Properties;

/**
 * TV Preview viewer: shows one HTML page full screen, driven by the remote.
 * Built-in copy: assets/index.html. Optional live URL (assets/tvpreview.properties, key "live"): loaded on every resume
 * when reachable (1.5 s HEAD), else the built-in copy. Adds ?tv on TV devices.
 * Back contract: dispatches keydown Escape with e.rcBack = true on document. The app stays if the page calls
 * e.preventDefault() and does not set window.rcExitRequested = true; otherwise it exits.
 * Menu key: calls window.rcToggleControls() if defined.
 */
public class MainActivity extends Activity {
  private static final String BUILT_IN = "file:///android_asset/index.html";
  private String live;
  private WebView web;
  private TextView loading;

  @Override protected void onCreate(Bundle saved) {
    super.onCreate(saved);
    try (InputStream in = getAssets().open("tvpreview.properties")) {
      Properties p = new Properties(); p.load(in);
      String l = p.getProperty("live", "").trim(); live = l.isEmpty() ? null : l;
    } catch (Exception ignored) { live = null; }
    WebView.setWebContentsDebuggingEnabled(true);
    web = new WebView(this);
    WebSettings s = web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setAllowFileAccess(true);
    s.setMediaPlaybackRequiresUserGesture(false);
    s.setCacheMode(WebSettings.LOAD_NO_CACHE);
    web.setBackgroundColor(Color.BLACK);
    web.setWebViewClient(new WebViewClient() {
      @Override public void onPageFinished(WebView v, String url) { loading.setVisibility(View.GONE); web.requestFocus(); }
      @Override public void onReceivedError(WebView v, android.webkit.WebResourceRequest req, android.webkit.WebResourceError err) {
        if (req.isForMainFrame() && req.getUrl().toString().startsWith("http")) v.loadUrl(BUILT_IN + suffix());
      }
    });
    loading = new TextView(this);
    loading.setText("Loading…");
    loading.setTextColor(Color.LTGRAY);
    loading.setTextSize(22);
    loading.setGravity(Gravity.CENTER);
    loading.setBackgroundColor(Color.BLACK);
    FrameLayout root = new FrameLayout(this);
    root.addView(web);
    root.addView(loading);
    setContentView(root);
    web.requestFocus();
  }

  @Override protected void onResume() { super.onResume(); load(); }

  private void load() {
    if (live == null) { loading.setVisibility(View.VISIBLE); web.loadUrl(BUILT_IN + suffix()); return; }
    new Thread(() -> {
      boolean ok = false;
      try {
        HttpURLConnection c = (HttpURLConnection) new URL(live).openConnection();
        c.setRequestMethod("HEAD"); c.setConnectTimeout(1500); c.setReadTimeout(1500);
        ok = c.getResponseCode() == 200; c.disconnect();
      } catch (Exception ignored) { }
      final boolean fromLive = ok;
      runOnUiThread(() -> {
        loading.setVisibility(View.VISIBLE);
        web.loadUrl((fromLive ? live : BUILT_IN) + suffix());
        Toast.makeText(this, fromLive ? "Live copy" : "Built-in copy", Toast.LENGTH_SHORT).show();
      });
    }).start();
  }

  private String suffix() { return isTv() ? "?tv" : ""; }

  private boolean isTv() {
    android.app.UiModeManager ui = (android.app.UiModeManager) getSystemService(UI_MODE_SERVICE);
    return getPackageManager().hasSystemFeature("android.software.leanback")
        || (ui != null && ui.getCurrentModeType() == android.content.res.Configuration.UI_MODE_TYPE_TELEVISION);
  }

  @Override public boolean onKeyDown(int code, KeyEvent e) {
    if (code == KeyEvent.KEYCODE_MENU) { web.evaluateJavascript("window.rcToggleControls && rcToggleControls()", null); return true; }
    return super.onKeyDown(code, e);
  }

  @Override public void onBackPressed() {
    web.evaluateJavascript("(function(){window.rcExitRequested=false;"
        + "var e=new KeyboardEvent('keydown',{key:'Escape',code:'Escape',keyCode:27,bubbles:true,cancelable:true});e.rcBack=true;"
        + "var t=document.activeElement||document;t.dispatchEvent(e);"
        + "if(window.rcExitRequested||!e.defaultPrevented){window.rcExitRequested=false;return 'exit';}return '';})()",
        v -> { if (!"\"\"".equals(v)) finish(); });
  }
}
