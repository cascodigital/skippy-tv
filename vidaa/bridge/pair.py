#!/usr/bin/env python3
"""Pareia com a TV VIDAA (PIN de 4 digitos na tela) e cria o tile da home Skippy.

Uso (na pasta vidaa/bridge, depois do setup.sh):  TV_HOST=<ip> SKIPPY_URL=<url da home> python3 -I pair.py
O token fica em sideehome/.sidee/session.json — e ele que a tvbridge usa. Nunca vai pro git.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "py"), os.path.join(HERE, "sidee")]
os.environ["HOME"] = os.environ.get("SIDEE_HOME", os.path.join(HERE, "sideehome"))
from core import client  # noqa: E402

host, url = os.environ["TV_HOST"], os.environ["SKIPPY_URL"]
icon = url.rsplit("/", 1)[0] + "/sk/banners/banner-skippy.png"
s = client.Session().load_or_none()
if not s or s.host != host:
    print("TV vai mostrar um PIN de 4 digitos.")
    s = client.pair(host, lambda: input("PIN: ").strip())
    print("pareado, perfil", s.auth_profile)
apps = client.add_tile(s, "skippy_home", "Skippy", url, icon)
# a checagem do Sidee e estrita com a URL e ja respondeu "nao" com o tile instalado: confira na TV
print("tile na lista da TV" if any(client.tile_matches_request(a, "skippy_home", url) for a in apps)
      else "a TV nao confirmou o tile: olhe o fim da lista de apps antes de repetir")
