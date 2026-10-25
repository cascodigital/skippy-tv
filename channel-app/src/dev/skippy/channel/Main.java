package dev.skippy.channel;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

// Destino de todo card: o Projectivy força o pacote do intent para o app dono do card,
// então o card abre aqui e daqui repassamos para o app real (extra "go" + "pkg").
public class Main extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent in = getIntent();
        String go = in.getStringExtra("go");
        if (go != null && !go.isEmpty()) {
            try {
                Intent v = new Intent(Intent.ACTION_VIEW, Uri.parse(go)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                String pkg = in.getStringExtra("pkg");
                if (pkg != null && !pkg.isEmpty()) v.setPackage(pkg);
                startActivity(v);
            } catch (Exception e) {
                Log.e(Sync.TAG, "abrir " + go, e);
                String pkg = in.getStringExtra("pkg");
                Intent l = pkg == null ? null : getPackageManager().getLeanbackLaunchIntentForPackage(pkg);
                if (l != null) startActivity(l.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            }
        } else {
            Sync.run(getApplicationContext());
        }
        finish();
    }
}
