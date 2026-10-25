#!/bin/bash
# Compila o app do canal "Skippy" (Java puro, sem Gradle) -> skippy-channel.apk
set -e
P=$(cd "$(dirname "$0")" && pwd); T=~/ai/tools/android-build
BT=$T/android-14; JAR=$T/android-34/android.jar; export JAVA_HOME=$(ls -d $T/jdk-*); export PATH=$JAVA_HOME/bin:$PATH
W=$P/../dist/channel-build; rm -rf $W; mkdir -p $W/res/drawable-nodpi $W/gen $W/classes $W/dex
cp $P/../dist/out/banner-skippy.png $W/res/drawable-nodpi/banner.png
mkdir -p $W/assets/banners
cp $P/assets/home.html $W/assets/
cp $P/../dist/out/banner-*.png $W/assets/banners/
cp $P/../fonts/*.ttf $W/assets/
cp $P/../dist/out/wallpaper-anim-quarto.mp4 $W/assets/wallpaper-quarto.mp4
cp $P/../dist/out/wallpaper-anim.mp4 $W/assets/wallpaper-sala.mp4
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
