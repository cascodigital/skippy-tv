#!/usr/bin/env python3
"""Ponte Skippy <-> Hisense VIDAA (MQTT 36669, sessao pareada pelo Sidee).

- Vigia de Home: TV na home da VIDAA (statetype remote_launcher) -> abre o tile Skippy.
- API pro launcher web (CORS aberto): apps nativos, abrir app, tecla, entrada, pausa do vigia,
  e proxy do skippy-cards (.46:8099) pra frase e cards.
"""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "py"), os.path.join(HERE, "sidee")]
os.environ["HOME"] = os.environ.get("SIDEE_HOME", os.path.join(HERE, "sideehome"))
from core import client, protocol  # noqa: E402

HOST = os.environ["TV_HOST"]                 # IP da TV
PORT = int(os.environ.get("PORT", "8781"))
CARDS = os.environ["CARDS"]                  # skippy-cards (server.public_url do house.json)
SKIPPY = {"appId": "skippy_home", "name": "Skippy",
          "url": os.environ["SKIPPY_URL"]}      # pagina da home (o tile abre ela)
POLL = 3.0
COOLDOWN = 5.0
RECONNECT = 6 * 3600  # reconecta periodicamente pro _ensure_ready renovar o token

st = {"connected": False, "tv": None, "apps": [], "sources": [], "last_msg": 0.0,
      "last_launch": 0.0, "pause_until": 0.0, "takeovers": 0, "error": ""}
cur = None  # MqttSession ativa


def log(msg):
    print(time.strftime("%d/%m %H:%M:%S"), msg, flush=True)


def icon_of(app):
    raw = app.get("httpIcon") or ""
    i = raw.find("iconDownload")
    return raw[i + len("iconDownload"):] if i >= 0 else ""


def publish(service, action, payload=""):
    m = cur
    if not m:
        raise ConnectionError("TV desconectada")
    if not isinstance(payload, str):
        payload = json.dumps(payload)
    m.publish(f"/remoteapp/tv/{service}/{m.client_id}/actions/{action}", payload)


def launch(app_id, name, url):
    publish("ui_service", "launchapp", protocol.launch_payload(app_id, name, url))


def on_msg(_c, _u, msg):
    st["last_msg"] = time.time()
    try:
        data = json.loads(msg.payload.decode("utf-8", "replace"))
    except ValueError:
        return
    if msg.topic.endswith("data/applist") and isinstance(data, list):
        st["apps"] = [{"appId": a.get("appId"), "name": a.get("name"), "url": a.get("url"),
                       "icon": icon_of(a)} for a in data if isinstance(a, dict) and a.get("name")]
    elif msg.topic.endswith("data/sourcelist") and isinstance(data, list):
        st["sources"] = data
    elif msg.topic.endswith("ui_service/state") and isinstance(data, dict):
        st["tv"] = data
        now = time.time()
        if (data.get("statetype") == "remote_launcher" and now > st["pause_until"]
                and now - st["last_launch"] > COOLDOWN):
            st["last_launch"] = now
            st["takeovers"] += 1
            launch(SKIPPY["appId"], SKIPPY["name"], SKIPPY["url"])
            log("home da VIDAA -> Skippy")


def connect():
    with client._OP_LOCK:
        s = client.Session().load_or_none()
        if not s:
            raise client.AuthError("none", "sem pareamento")
        s.host = HOST
        s = client._ensure_ready(s)
        m = client._saved_connection(s, None if s.tokenless else s.access_token)
        rc = m.start()
        if rc != 0:
            m.stop()
            if rc in (4, 5) and not s.tokenless:
                client.refresh(s)
            raise ConnectionError(f"rc={rc}")
    return m


def run():
    global cur
    while True:
        m = None
        try:
            m = connect()
            m.client.on_message = on_msg
            t = m.topics
            m.subscribe([t["applist_reply"], t["mobile"] + "ui_service/data/sourcelist",
                         t["mobile"] + "ui_service/state", t["broadcast"] + "ui_service/state"])
            cur = m
            st.update(connected=True, error="", last_msg=time.time())
            log("conectado na TV")
            time.sleep(0.5)
            publish("ui_service", "applist", "0")
            publish("ui_service", "sourcelist", "")
            t0 = time.time()
            while time.time() - t0 < RECONNECT:
                publish("ui_service", "gettvstate", "")
                time.sleep(POLL)
                # com app aberto a TV nao responde o gettvstate: silencio nao e queda,
                # quem detecta TV desligada e o keepalive do MQTT
                if not m.client.is_connected():
                    raise ConnectionError("MQTT caiu")
        except Exception as e:  # TV desligada cai aqui a cada 10 s
            if st["connected"] or st["error"] != str(e):
                log(f"desconectado: {e.__class__.__name__}: {e}")
            st["error"] = str(e)
        finally:
            cur = None
            st["connected"] = False
            if m:
                m.stop()
        time.sleep(10)


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/state":
                return self.send(200, {k: st[k] for k in
                                       ("connected", "tv", "takeovers", "pause_until", "error")})
            if u.path == "/api/apps":
                return self.send(200, [a for a in st["apps"] if a["appId"] != SKIPPY["appId"]])
            if u.path == "/api/sources":
                return self.send(200, st["sources"])
            if u.path == "/api/launch":
                a = next((x for x in st["apps"] if x["appId"] == q.get("appId")), None)
                if not a:
                    return self.send(404, {"erro": "app desconhecido"})
                launch(a["appId"], a["name"], a["url"])
                return self.send(200, {"ok": True})
            if u.path == "/api/key":
                publish("remote_service", "sendkey", q.get("k", ""))
                return self.send(200, {"ok": True})
            if u.path == "/api/source":
                publish("ui_service", "changesource", {"sourceid": q.get("id", ""),
                                                       "sourcename": q.get("name", q.get("id", ""))})
                return self.send(200, {"ok": True})
            if u.path == "/api/vidaa":  # pausa o vigia e vai pra home da TV
                st["pause_until"] = time.time() + 60 * float(q.get("min", "10"))
                publish("remote_service", "sendkey", "KEY_HOME")
                return self.send(200, {"ok": True, "pause_until": st["pause_until"]})
            if u.path == "/api/resume":
                st["pause_until"] = 0
                return self.send(200, {"ok": True})
            if u.path.startswith("/cards/"):  # proxy do skippy-cards (sem CORS la)
                with urllib.request.urlopen(CARDS + u.path[6:] + ("?" + u.query if u.query else ""),
                                            timeout=8) as r:
                    return self.send(200, r.read(), r.headers.get("Content-Type", "application/json"))
            return self.send(404, {"erro": "rota"})
        except Exception as e:
            return self.send(503, {"erro": f"{e.__class__.__name__}: {e}"})


if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    log(f"API em :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
