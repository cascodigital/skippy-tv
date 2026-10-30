#!/bin/bash
# Baixa o que a ponte VIDAA usa e NAO vai pro git: Sidee (MIT, versao fixada) e paho-mqtt.
# O Sidee traz o certificado de cliente do app oficial da Hisense; por isso ele nao e copiado pra este repo.
set -e
cd "$(dirname "$0")"
SIDEE_REPO=https://github.com/Empi9245/Sidee.git
SIDEE_REV=ed2193496b41d5cc0a1aa6c868c2d96014bbe576   # 2026-10-29, testado na Hisense 55A60QUV (perfil modern)
if [ ! -d sidee ]; then
  git clone -q "$SIDEE_REPO" sidee && git -C sidee checkout -q "$SIDEE_REV" && rm -rf sidee/.git sidee/tests sidee/docs
fi
[ -d py/paho ] || pip install -q --target py 'paho-mqtt>=2,<3'
echo "ok: agora TV_HOST=<ip> SKIPPY_URL=<url> python3 -I pair.py"
