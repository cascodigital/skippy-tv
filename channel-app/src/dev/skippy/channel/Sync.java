package dev.skippy.channel;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.tv.TvContract;
import android.net.Uri;
import android.os.SystemClock;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

// Publica o feed do skippy-cards (.46) como canal de pré-visualização "Skippy".
public class Sync extends BroadcastReceiver {
    static final String TAG = "SkippyChannel";
    static final String FEED = "http://192.168.2.46:8099/feed.json";
    static final long EVERY = 10 * 60 * 1000L;

    @Override public void onReceive(Context ctx, Intent i) {
        Watch.start(ctx, Intent.ACTION_BOOT_COMPLETED.equals(i.getAction()));   // Fire TV: vigia da home sobe no boot
        final PendingResult pr = goAsync();
        final Context app = ctx.getApplicationContext();
        new Thread(() -> { try { work(app); } finally { pr.finish(); } }).start();
    }

    static void run(Context ctx) {
        final Context app = ctx.getApplicationContext();
        new Thread(() -> work(app)).start();
    }

    static synchronized void work(Context ctx) {
        if (android.os.Build.VERSION.SDK_INT < 26) return;   // Fire OS 6: sem canais de TV; o Home busca o feed sozinho
        schedule(ctx);
        try {
            JSONObject feed = new JSONObject(get(FEED));
            long ch = channel(ctx, feed.optString("channel", "Skippy"));
            ctx.getContentResolver().delete(TvContract.buildPreviewProgramsUriForChannel(ch), null, null);
            JSONArray cards = feed.getJSONArray("cards");
            for (int n = 0; n < cards.length(); n++) {
                JSONObject c = cards.getJSONObject(n);
                ContentValues v = new ContentValues();
                v.put(TvContract.PreviewPrograms.COLUMN_CHANNEL_ID, ch);
                v.put(TvContract.PreviewPrograms.COLUMN_TYPE, TvContract.PreviewPrograms.TYPE_CLIP);
                v.put(TvContract.PreviewPrograms.COLUMN_TITLE, c.optString("title"));
                v.put(TvContract.PreviewPrograms.COLUMN_SHORT_DESCRIPTION, c.optString("desc"));
                v.put(TvContract.PreviewPrograms.COLUMN_POSTER_ART_URI, c.getString("img"));
                v.put(TvContract.PreviewPrograms.COLUMN_POSTER_ART_ASPECT_RATIO, TvContract.PreviewPrograms.ASPECT_RATIO_16_9);
                v.put(TvContract.PreviewPrograms.COLUMN_INTERNAL_PROVIDER_ID, c.optString("id", "c" + n));
                v.put(TvContract.PreviewPrograms.COLUMN_WEIGHT, cards.length() - n);
                String intent = c.optString("intent", "");
                if (!intent.isEmpty()) v.put(TvContract.PreviewPrograms.COLUMN_INTENT_URI, intent);
                ctx.getContentResolver().insert(TvContract.PreviewPrograms.CONTENT_URI, v);
            }
            watchNext(ctx, cards);
            Log.i(TAG, "ok " + cards.length() + " cards no canal " + ch);
        } catch (Exception e) {
            Log.e(TAG, "sync falhou", e);
        }
    }

    // Mesmos cards no "Ver a Seguir" (a única fileira que o Projectivy põe acima do dock).
    static void watchNext(Context ctx, JSONArray cards) throws Exception {
        ctx.getContentResolver().delete(TvContract.WatchNextPrograms.CONTENT_URI, null, null);
        long now = System.currentTimeMillis();
        for (int n = 0; n < cards.length(); n++) {
            JSONObject c = cards.getJSONObject(n);
            ContentValues v = new ContentValues();
            v.put(TvContract.WatchNextPrograms.COLUMN_TYPE, TvContract.PreviewPrograms.TYPE_CLIP);
            v.put(TvContract.WatchNextPrograms.COLUMN_WATCH_NEXT_TYPE, TvContract.WatchNextPrograms.WATCH_NEXT_TYPE_NEXT);
            v.put(TvContract.WatchNextPrograms.COLUMN_LAST_ENGAGEMENT_TIME_UTC_MILLIS, now - n * 1000L);
            v.put(TvContract.WatchNextPrograms.COLUMN_TITLE, c.optString("title"));
            v.put(TvContract.WatchNextPrograms.COLUMN_SHORT_DESCRIPTION, c.optString("desc"));
            v.put(TvContract.WatchNextPrograms.COLUMN_POSTER_ART_URI, c.getString("img"));
            v.put(TvContract.WatchNextPrograms.COLUMN_POSTER_ART_ASPECT_RATIO, TvContract.PreviewPrograms.ASPECT_RATIO_16_9);
            v.put(TvContract.WatchNextPrograms.COLUMN_INTERNAL_PROVIDER_ID, "wn-" + c.optString("id", "c" + n));
            String intent = c.optString("intent", "");
            if (!intent.isEmpty()) v.put(TvContract.WatchNextPrograms.COLUMN_INTENT_URI, intent);
            ctx.getContentResolver().insert(TvContract.WatchNextPrograms.CONTENT_URI, v);
        }
    }

    static long channel(Context ctx, String name) throws Exception {
        SharedPreferences p = ctx.getSharedPreferences("s", 0);
        long id = p.getLong("ch", -1);
        if (id >= 0) {
            try (Cursor cur = ctx.getContentResolver().query(TvContract.buildChannelUri(id), null, null, null, null)) {
                if (cur != null && cur.moveToFirst()) return id;
            }
        }
        ContentValues v = new ContentValues();
        v.put(TvContract.Channels.COLUMN_TYPE, TvContract.Channels.TYPE_PREVIEW);
        v.put(TvContract.Channels.COLUMN_DISPLAY_NAME, name);
        v.put(TvContract.Channels.COLUMN_APP_LINK_INTENT_URI,
              new Intent(ctx, Main.class).toUri(Intent.URI_INTENT_SCHEME));
        Uri u = ctx.getContentResolver().insert(TvContract.Channels.CONTENT_URI, v);
        id = ContentUris.parseId(u);
        p.edit().putLong("ch", id).apply();
        try {
            Bitmap logo = BitmapFactory.decodeResource(ctx.getResources(), R.drawable.banner);
            try (java.io.OutputStream os = ctx.getContentResolver().openOutputStream(TvContract.buildChannelLogoUri(id))) {
                logo.compress(Bitmap.CompressFormat.PNG, 100, os);
            }
        } catch (Exception e) { Log.w(TAG, "logo", e); }
        TvContract.requestChannelBrowsable(ctx, id);
        return id;
    }

    static void schedule(Context ctx) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        PendingIntent pi = PendingIntent.getBroadcast(ctx, 0,
            new Intent(ctx, Sync.class).setAction("dev.skippy.channel.SYNC"), PendingIntent.FLAG_IMMUTABLE);
        am.setInexactRepeating(AlarmManager.ELAPSED_REALTIME, SystemClock.elapsedRealtime() + EVERY, EVERY, pi);
    }

    static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000); c.setReadTimeout(60000);
        try (InputStream in = c.getInputStream(); ByteArrayOutputStream o = new ByteArrayOutputStream()) {
            byte[] b = new byte[8192]; int r;
            while ((r = in.read(b)) > 0) o.write(b, 0, r);
            return o.toString("UTF-8");
        } finally { c.disconnect(); }
    }
}
