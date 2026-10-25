#!/bin/bash
# Gera o APK "Skippy Icon Pack" (banners 16:9 pro Projectivy) a partir de dist/out/banner-*.png (gerados pelo gen.py)
set -e
P=$(cd "$(dirname "$0")" && pwd); T=~/ai/tools/android-build
BT=$T/android-14; JAR=$T/android-34/android.jar; export JAVA_HOME=$(ls -d $T/jdk-*); export PATH=$JAVA_HOME/bin:$PATH
W=$P/dist/iconpack-build; rm -rf $W; mkdir -p $W/res/drawable-nodpi $W/res/xml $W/res/values $W/assets
declare -A C=(
 [plex]=com.plexapp.android/tv.plex.app.MainActivity
 [youtube]=com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity
 [globoplay]=com.globo.globotv/com.globo.globotv.splashtv.SplashActivity
 [youtubemusic]=com.google.android.youtube.tvmusic/com.google.android.apps.youtube.tvmusic.activity.MainActivity
 [kodi]=org.xbmc.kodi/org.xbmc.kodi.Splash
 [playstore]=com.android.vending/com.google.android.finsky.tvmainactivity.TvMainActivity
 [netflix]=com.netflix.ninja/com.netflix.ninja.MainActivity
 [primevideo]=com.amazon.amazonvideo.livingroom/com.amazon.ignition.IgnitionActivity
 [downloader]=com.esaba.downloader/com.esaba.downloader.ui.main.MainActivity
 [plexserver]=com.plexapp.mediaserver.smb/com.plexapp.mediaserver.ui.main.MainActivity
 [settings]=com.android.tv.settings/com.android.tv.settings.MainSettings
 [livechannels]=com.google.android.tv/com.android.tv.TvActivity
)
{ echo '<?xml version="1.0" encoding="utf-8"?>'; echo '<resources>'
  for k in "${!C[@]}"; do echo "  <item component=\"ComponentInfo{${C[$k]}}\" drawable=\"sk_$k\"/>"; done
  echo '</resources>'; } > $W/res/xml/appfilter.xml
cp $W/res/xml/appfilter.xml $W/assets/appfilter.xml
{ echo '<?xml version="1.0" encoding="utf-8"?><resources><version>1</version><category title="Skippy"/>'
  for k in "${!C[@]}"; do echo "<item drawable=\"sk_$k\"/>"; done; echo '</resources>'; } > $W/res/xml/drawable.xml
for k in "${!C[@]}"; do cp $P/dist/out/banner-$k.png $W/res/drawable-nodpi/sk_$k.png; done
cp $P/dist/out/banner-settings.png $W/res/drawable-nodpi/sk_icon.png
echo '<resources><string name="app_name">Skippy Icon Pack</string></resources>' > $W/res/values/strings.xml
cat > $W/AndroidManifest.xml <<'M'
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.skippy.iconpack" android:versionCode="VC" android:versionName="1.VC">
  <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="30"/>
  <uses-feature android:name="android.software.leanback" android:required="false"/>
  <uses-feature android:name="android.hardware.touchscreen" android:required="false"/>
  <application android:label="@string/app_name" android:icon="@drawable/sk_icon" android:banner="@drawable/sk_icon" android:hasCode="false">
    <activity android:name="android.app.Activity" android:exported="true">
      <intent-filter><action android:name="org.adw.launcher.THEMES"/><category android:name="android.intent.category.DEFAULT"/></intent-filter>
      <intent-filter><action android:name="com.novalauncher.THEME"/></intent-filter>
      <intent-filter><action android:name="org.adw.launcher.icons.ACTION_PICK_ICON"/><category android:name="android.intent.category.DEFAULT"/></intent-filter>
    </activity>
  </application>
</manifest>
M
sed -i "s/VC/$(date +%s | cut -c3-)/g" $W/AndroidManifest.xml; cd $W
$BT/aapt2 compile --dir res -o res.zip
$BT/aapt2 link -o un.apk -I $JAR --manifest AndroidManifest.xml -A assets res.zip -0 png
$BT/zipalign -f 4 un.apk al.apk
# assinatura: keystore e senha ficam FORA do repo (padrão ~/ai/keys; sobrescreve com KEYSTORE / KEYSTORE_PASS_FILE)
KS=${KEYSTORE:-$HOME/ai/keys/skippy.keystore}; KSP=${KEYSTORE_PASS_FILE:-$HOME/ai/keys/skippy-keystore.pass}
[ -f "$KS" ] || { echo "keystore ausente: $KS (crie com: keytool -genkeypair -keystore $KS -alias skippy -keyalg RSA -keysize 2048 -validity 20000)"; exit 1; }
$BT/apksigner sign --ks "$KS" --ks-pass file:"$KSP" --out $P/dist/skippy-iconpack.apk al.apk
echo "ok $P/dist/skippy-iconpack.apk"
