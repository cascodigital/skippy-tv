package dev.skippy.channel;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

// Painel "Ponte de Comando". A interface é HTML (skippy-cards no .46); a câmera da rua toca no
// decodificador de hardware (LiveCam: TS do go2rtc -> MediaCodec) numa SurfaceView por baixo do WebView transparente.
// A página diz onde o vídeo fica via Skippy.video(x, y, w, h) em frações da tela.
public class Ponte extends Activity implements SurfaceHolder.Callback, LiveCam.Listener {
    static final String TAG = "SkippyPonte";
    static final String URL = Config.SERVER + "/ponte";
    // MPEG-TS contínuo do go2rtc, demux próprio. MediaPlayer no Shield: RTSP derruba o NuPlayer (crash nativo),
    // HLS fMP4 dá -1004 e TS funciona mas com ~7 s de atraso fixo (25/10/2026).
    static final String CAM = Config.CAM_TS;
    static final int MAX_FAIL = 3;
    int fails;
    final Handler ui = new Handler(Looper.getMainLooper());
    FrameLayout root;
    SurfaceView surface;
    WebView web;
    LiveCam cam;
    boolean alive, haveSurface;
    volatile boolean playing;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        surface = new SurfaceView(this);
        surface.getHolder().addCallback(this);
        root.addView(surface, new FrameLayout.LayoutParams(1, 1));

        web = new WebView(this);
        web.setBackgroundColor(Color.TRANSPARENT);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        // Shield: escala mínima + overview encaixa os 1920 px. WebView da Amazon (Fire OS 6) ignora o viewport e
        // usa a densidade (200%); lá o zoom é fixado em px de tela por px CSS (100% numa tela de 1920 px).
        if (android.os.Build.VERSION.SDK_INT >= 26) web.setInitialScale(1);
        else web.setInitialScale(Math.round(100f * getResources().getDisplayMetrics().widthPixels / 1920f));
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new Chrome());
        web.addJavascriptInterface(new Bridge(this), "Skippy");
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        root.setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        setContentView(root);

        String focus = getIntent().getStringExtra("focus");
        web.loadUrl(URL + "?native=1" + (focus != null ? "&focus=" + focus : ""));   // o servidor sabe o cômodo pelo IP
        web.requestFocus();
    }

    // estática de propósito: o d8 do build-tools 34 quebra com classe interna não-estática
    static class Bridge {
        final Ponte p;
        Bridge(Ponte p) { this.p = p; }
        @JavascriptInterface public void video(final float x, final float y, final float w, final float h) {
            p.ui.post(() -> p.place(x, y, w, h));
        }
        @JavascriptInterface public boolean playing() { return p.playing; }
    }

    void place(float x, float y, float w, float h) {
                int W = root.getWidth(), H = root.getHeight();
                FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(Math.max(1, Math.round(w * W)), Math.max(1, Math.round(h * H)));
                lp.leftMargin = Math.round(x * W); lp.topMargin = Math.round(y * H);
                surface.setLayoutParams(lp);
    }

    static class Chrome extends WebChromeClient {
        @Override public boolean onConsoleMessage(ConsoleMessage m) {
            Log.i(TAG, m.messageLevel() + " " + m.message() + " @" + m.lineNumber());
            return true;
        }
    }

    // ---------- player ----------
    @Override public void surfaceCreated(SurfaceHolder h) { haveSurface = true; start(); }
    @Override public void surfaceChanged(SurfaceHolder h, int f, int w, int hh) { }
    @Override public void surfaceDestroyed(SurfaceHolder h) { haveSurface = false; stop(); }

    void start() {
        if (!alive || !haveSurface || cam != null) return;
        cam = new LiveCam(CAM, surface.getHolder().getSurface(), this);
        cam.start();
    }

    @Override public void onFirstFrame() { fails = 0; playing = true; js("window.camReady && camReady()"); }

    @Override public void onFailed(String why) {
        Log.w(TAG, "camera: " + why);
        ui.post(this::retry);
    }

    void retry() {
        stop();
        if (!alive) return;
        if (++fails >= MAX_FAIL) {   // desiste do nativo e a página cai pro WebRTC do go2rtc
            Log.w(TAG, "player nativo falhou " + fails + "x, fallback WebRTC");
            js("window.camFallback && camFallback()");
            return;
        }
        js("window.camLost && camLost()");
        ui.postDelayed(this::start, 2000);
    }

    void stop() {
        playing = false;
        if (cam != null) { final LiveCam c = cam; cam = null; new Thread(c::stop).start(); }
    }

    void js(String code) { ui.post(() -> { if (web != null) web.evaluateJavascript(code, null); }); }

    @Override protected void onResume() { super.onResume(); alive = true; start(); }

    @Override public void onBackPressed() {
        web.evaluateJavascript("window.skippyBack ? window.skippyBack() : false", v -> {
            if (!"true".equals(v)) finish();
        });
    }

    @Override protected void onStop() {
        super.onStop();
        alive = false; stop();
        Sync.run(getApplicationContext());   // atualiza o card de luzes na home
        finish();                            // não deixa a câmera aberta em segundo plano
    }

    @Override protected void onDestroy() {
        ui.removeCallbacksAndMessages(null);
        if (web != null) { web.loadUrl("about:blank"); web.destroy(); web = null; }
        super.onDestroy();
    }
}
