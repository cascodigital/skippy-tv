#!/bin/bash
# Compila o app do canal "Skippy" (Java puro, sem Gradle) -> skippy-channel.apk
set -e
P=$(cd "$(dirname "$0")" && pwd); T=~/ai/tools/android-build
BT=$T/android-14; JAR=$T/android-34/android.jar; export JAVA_HOME=$(ls -d $T/jdk-*); export PATH=$JAVA_HOME/bin:$PATH
W=$P/../dist/channel-build; rm -rf $W; mkdir -p $W/res/drawable-nodpi $W/gen $W/classes $W/dex
cp $P/../dist/out/banner-skippy.png $W/res/drawable-nodpi/banner.png
mkdir -p $W/assets/banners
# tudo que é da casa sai do house.json (docs/HOUSE.md)
HJ=${HOUSE_JSON:-$P/../house.json}
read -r SERVER CAMTS WFIRE WTV < <(python3 - "$HJ" <<'PYH'
import json, sys
h = json.load(open(sys.argv[1])); c = h['camera']
fire = next((d for d in h['devices'] if d.get('fire_tv')), None); tv = next((d for d in h['devices'] if not d.get('fire_tv')), fire)
print(h['server']['public_url'].rstrip('/'), f"{c['go2rtc'].rstrip('/')}/api/stream.ts?src={c['stream']}&video=h264",
      (fire or tv)['wallpaper'], (tv or fire)['wallpaper'])
PYH
)
mkdir -p $W/gen/dev/skippy/channel
printf 'package dev.skippy.channel;\n// GERADO pelo build.sh a partir do house.json: não editar\nfinal class Config {\n    static final String SERVER = "%s";\n    static final String CAM_TS = "%s";\n}\n' "$SERVER" "$CAMTS" > $W/gen/dev/skippy/channel/Config.java
sed "s#__SERVER__#$SERVER#g" $P/assets/home.html > $W/assets/home.html
cp $P/../dist/out/banner-*.png $W/assets/banners/
cp $P/../fonts/*.ttf $W/assets/
cp $P/../$WFIRE $W/assets/wallpaper-fire.mp4
cp $P/../$WTV $W/assets/wallpaper-tv.mp4
sed "s/VC/$(date +%s | cut -c3-)/g" $P/AndroidManifest.xml > $W/AndroidManifest.xml
cd $W
$BT/aapt2 compile --dir res -o res.zip
$BT/aapt2 link -o un.apk -I $JAR --manifest AndroidManifest.xml --java gen -A assets -0 mp4 -0 png -0 ttf res.zip
javac -nowarn -source 8 -target 8 -bootclasspath $JAR:$BT/core-lambda-stubs.jar -cp $JAR -d classes $(find $P/src gen -name '*.java') 2>&1 | grep -v "^warning\|bootstrap\|^1 warning" || true
(cd classes && zip -q -r ../classes.jar .) && $BT/d8 --min-api 25 --lib $JAR --output dex classes.jar
cp un.apk wd.apk && (cd dex && zip -q ../wd.apk classes.dex)
$BT/zipalign -f 4 wd.apk al.apk
# assinatura: keystore e senha ficam FORA do repo (padrão ~/ai/keys; sobrescreve com KEYSTORE / KEYSTORE_PASS_FILE)
KS=${KEYSTORE:-$HOME/ai/keys/skippy.keystore}; KSP=${KEYSTORE_PASS_FILE:-$HOME/ai/keys/skippy-keystore.pass}
[ -f "$KS" ] || { echo "keystore ausente: $KS (crie com: keytool -genkeypair -keystore $KS -alias skippy -keyalg RSA -keysize 2048 -validity 20000)"; exit 1; }
$BT/apksigner sign --ks "$KS" --ks-pass file:"$KSP" --out $P/../dist/skippy-channel.apk al.apk
echo "ok $P/../dist/skippy-channel.apk"
