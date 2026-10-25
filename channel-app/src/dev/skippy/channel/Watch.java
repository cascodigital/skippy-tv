package dev.skippy.channel;

import android.app.Notification;
import android.app.Service;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;

// Fire TV (Fire OS 6): a Amazon bloqueia serviço de acessibilidade de terceiros (testado 25/10/2026: o mesmo serviço
// liga no Shield e no Fire TV nunca é vinculado), ignora set-home-activity e recusa desativar a home dela (pacote protegido). Este vigia lê as estatísticas de uso a cada 400 ms e,
// quando a home da Amazon vai pra frente, reabre o launcher Skippy. Ajustes da Amazon (outra activity) não é tocado.
// Custo: o Android 7 segura start de app em segundo plano por 5 s depois do Home, então a home da Amazon aparece ~5 s.
// Permissão: adb shell appops set dev.skippy.channel GET_USAGE_STATS allow
public class Watch extends Service {
    static final String TAG = "SkippyWatch";
    static final String AMAZON = "com.amazon.tv.launcher";
    final Handler h = new Handler(Looper.getMainLooper());
    UsageStatsManager usm;
    long seen;
    static volatile long pausedUntil;
    static void pauseFor(long ms) { pausedUntil = SystemClock.elapsedRealtime() + ms; }
    long[] recent = new long[4];
    int ri;

    static void start(Context c) { start(c, false); }

    static void start(Context c, boolean boot) {
        if (!Build.MODEL.startsWith("AFT")) return;   // só no Fire TV
        c.getPackageManager().setComponentEnabledSetting(new android.content.ComponentName(c, c.getPackageName() + ".FireIcon"),
            android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED, android.content.pm.PackageManager.DONT_KILL_APP);
        try { c.startService(new Intent(c, Watch.class).putExtra("boot", boot)); } catch (Exception e) { Log.w(TAG, "start", e); }
    }

    @Override public void onCreate() {
        super.onCreate();
        usm = (UsageStatsManager) getSystemService(Context.USAGE_STATS_SERVICE);
        seen = System.currentTimeMillis();
        Notification n = new Notification.Builder(this).setContentTitle("Skippy Home").setSmallIcon(android.R.drawable.ic_menu_view).build();
        startForeground(1, n);   // prioridade alta: o Fire TV mata serviço de fundo com 1,8 GB de RAM
        h.post(this::loop);
    }

    volatile boolean alive = true;
    void loop() { if (!alive) return; check(); h.postDelayed(this::loop, 400); }   // lambda: o d8 34 quebra com classe anônima

    // o Fire OS publica o evento de troca de app com ~1-1,5 s de atraso (medido 25/10/2026):
    // janela larga de 5 s e só processa evento mais novo que o último já visto
    void check() {
        long now = System.currentTimeMillis();
        try {
            UsageEvents ev = usm.queryEvents(now - 5000, now);
            UsageEvents.Event e = new UsageEvents.Event();
            String fg = null, cls = null;
            long newest = seen;
            while (ev.hasNextEvent()) {
                ev.getNextEvent(e);
                if (e.getTimeStamp() <= seen || e.getEventType() != UsageEvents.Event.MOVE_TO_FOREGROUND) continue;
                if (e.getTimeStamp() >= newest) { newest = e.getTimeStamp(); fg = e.getPackageName(); cls = e.getClassName(); }
            }
            seen = newest;
            if (AMAZON.equals(fg) && cls != null && cls.contains("HomeActivity")) goHome();
        } catch (Exception ex) { Log.w(TAG, "check", ex); }
    }

    void goHome() {
        long t = SystemClock.elapsedRealtime();
        if (t < pausedUntil) return;            // "Tela da Amazon" escolhida no Skippy
        long oldest = recent[ri];
        if (oldest != 0 && t - oldest < 5000) {       // 4 em 5 s = laço (ex.: Home quebrado): desiste por 5 min
            Log.w(TAG, "laco detectado, pausando 5 min");
            pauseFor(5 * 60000);
            return;
        }
        recent[ri] = t; ri = (ri + 1) % recent.length;
        Log.i(TAG, "home da Amazon na frente, abrindo Skippy");
        startActivity(new Intent(this, Home.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
            | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_NO_ANIMATION));
    }

    // no boot o Fire OS não registra a entrada da home dele nas estatísticas de uso (medido 25/10/2026),
    // então o boot abre o Skippy direto depois de assentar
    @Override public int onStartCommand(Intent i, int f, int id) {
        if (i != null && i.getBooleanExtra("boot", false)) h.postDelayed(() -> {
            Log.i(TAG, "boot: abrindo Skippy");
            startActivity(new Intent(this, Home.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION));
        }, 8000);
        return START_STICKY;
    }
    @Override public IBinder onBind(Intent i) { return null; }
    @Override public void onDestroy() { alive = false; super.onDestroy(); }
}
