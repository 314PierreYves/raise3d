#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
r3monitor - Monitoring en LECTURE SEULE d'une Raise3D Pro2 (Hyper Speed / Klipper).

  Klipper (/tmp/klippy_uds)  ->  HTTP JSON (port 8090)  +  MQTT (mosquitto local, optionnel)
  MXCCameraServer (30216)    ->  /snapshot.jpg (image unique, sans exposer le mot de passe)

Compatible Python 2.7 et 3.x, bibliotheque standard uniquement.
Aucune commande G-code n'est jamais envoyee a Klipper.

Points d'acces HTTP :
  /               petit tableau de bord (rafraichi automatiquement)
  /status         resume JSON (etat, progression, temperatures, ETA...)
  /raw            objets Klipper bruts
  /snapshot.jpg   derniere image de la camera
"""
from __future__ import print_function

import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time

try:  # Python 2
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    from SocketServer import ThreadingMixIn
except ImportError:  # Python 3
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

# --------------------------------------------------------------------------- config
KLIPPY_SOCK = "/tmp/klippy_uds"
HTTP_BIND = "0.0.0.0"          # mettre "127.0.0.1" pour ne rien exposer sur le reseau
HTTP_PORT = 8090
POLL_INTERVAL = 2.0            # secondes entre deux lectures de Klipper
MQTT_ENABLED = True            # publie via mosquitto_pub s'il est present
MQTT_HOST = "127.0.0.1"
MQTT_TOPIC = "raise3d/pro2/status"
MQTT_EVERY = 5                 # publier 1 lecture sur N (5 x 2 s = toutes les 10 s)
CAMERA_PORT = 30216

WANTED_OBJECTS = [
    "print_stats", "virtual_sdcard", "idle_timeout", "toolhead", "system_stats",
    "extruder", "extruder1", "heater_bed", "fan",
    "fan_generic extruder_left",
    "filament_switch_sensor F0", "filament_switch_sensor F1",
    "gcode_macro SET_PERCENT", "save_variables",
]


def log(*args):
    sys.stderr.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(a) for a in args) + "\n")
    sys.stderr.flush()


# --------------------------------------------------------------------------- Klipper
def klippy_call(method, params=None, timeout=5.0):
    """Une requete JSON sur le socket Unix de Klipper (messages termines par 0x03)."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(KLIPPY_SOCK)
        req = json.dumps({"id": 1, "method": method, "params": params or {}}) + "\x03"
        s.sendall(req.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\x03"):
            chunk = s.recv(65536)
            if not chunk:
                raise IOError("connexion fermee par Klipper")
            buf += chunk
    finally:
        s.close()
    resp = json.loads(buf[:-1].decode("utf-8"))
    if "error" in resp:
        raise IOError("erreur Klipper: %s" % resp["error"])
    return resp["result"]


def rnd(x, n=1):
    return None if x is None else round(x, n)


def find_macro_percent(st):
    """Raise3D definit une macro SET_PERCENT : on cherche une variable de pourcentage."""
    macro = st.get("gcode_macro SET_PERCENT") or {}
    for k, v in macro.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if any(w in k.lower() for w in ("percent", "progress")):
                return float(v)
    return None


def summarize(st):
    ps = st.get("print_stats") or {}
    sd = st.get("virtual_sdcard") or {}

    progress, source = None, None
    if sd.get("is_active") or sd.get("file_path"):
        progress, source = (sd.get("progress") or 0.0) * 100.0, "virtual_sdcard"
    else:
        p = find_macro_percent(st)
        if p is not None:
            progress, source = (p * 100.0 if p <= 1.0 else p), "SET_PERCENT"

    duration = ps.get("print_duration") or 0.0
    eta = None
    if progress and 0.5 < progress < 100.0 and duration > 0:
        eta = int(duration * (100.0 / progress - 1.0))

    heaters = {}
    for name in ("extruder", "extruder1", "heater_bed"):
        h = st.get(name)
        if h:
            heaters[name] = {"temp": rnd(h.get("temperature")),
                             "target": rnd(h.get("target")),
                             "power": rnd(h.get("power"), 2)}

    sensors = {}
    for key, val in st.items():
        if key.startswith("filament_switch_sensor "):
            sensors[key.split(" ", 1)[1]] = {"detected": val.get("filament_detected"),
                                             "enabled": val.get("enabled")}

    th = st.get("toolhead") or {}
    return {
        "state": ps.get("state"),               # standby / printing / paused / complete / error
        "message": ps.get("message") or None,
        "filename": ps.get("filename") or None,
        "progress_pct": rnd(progress),
        "progress_source": source,
        "print_duration_s": int(duration),
        "total_duration_s": int(ps.get("total_duration") or 0),
        "eta_s": eta,
        "filament_used_mm": rnd(ps.get("filament_used")),
        "heaters": heaters,
        "fan": rnd((st.get("fan") or {}).get("speed"), 2),
        "filament_sensors": sensors,
        "idle_state": (st.get("idle_timeout") or {}).get("state"),
        "homed_axes": th.get("homed_axes"),
        "position": [rnd(v, 2) for v in (th.get("position") or [])][:3],
        "sysload": (st.get("system_stats") or {}).get("sysload"),
    }


# --------------------------------------------------------------------------- etat partage
class State(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.raw = {}
        self.summary = {"state": "starting"}
        self.updated = 0.0
        self.error = None


STATE = State()


def poller():
    objects, n = None, 0
    mqtt_bin = find_mosquitto_pub() if MQTT_ENABLED else None
    if MQTT_ENABLED and not mqtt_bin:
        log("mosquitto_pub introuvable, MQTT desactive")
    while True:
        try:
            if objects is None:
                avail = set(klippy_call("objects/list")["objects"])
                objects = dict((o, None) for o in WANTED_OBJECTS if o in avail)
                log("Objets suivis:", ", ".join(sorted(objects)))
            st = klippy_call("objects/query", {"objects": objects})["status"]
            summary = summarize(st)
            with STATE.lock:
                STATE.raw, STATE.summary = st, summary
                STATE.updated, STATE.error = time.time(), None
        except Exception as e:  # Klipper redemarre, socket absent, etc.
            objects = None
            with STATE.lock:
                STATE.error = str(e)
                STATE.summary = {"state": "klipper_unreachable", "error": str(e)}
            log("Lecture Klipper impossible:", e)
        n += 1
        if mqtt_bin and n % MQTT_EVERY == 0:
            mqtt_publish(mqtt_bin, current_status())
        time.sleep(POLL_INTERVAL)


def current_status():
    with STATE.lock:
        out = dict(STATE.summary)
        out["updated"] = int(STATE.updated) or None
    return out


# --------------------------------------------------------------------------- MQTT
def find_mosquitto_pub():
    for d in ("/usr/bin", "/usr/local/bin", "/bin"):
        p = os.path.join(d, "mosquitto_pub")
        if os.path.exists(p):
            return p
    return None


def mqtt_publish(binary, payload):
    try:
        subprocess.call([binary, "-h", MQTT_HOST, "-t", MQTT_TOPIC, "-r",
                         "-m", json.dumps(payload)])
    except Exception as e:
        log("Publication MQTT impossible:", e)


# --------------------------------------------------------------------------- camera
def camera_auth():
    """Recupere 'user:motdepasse' depuis la ligne de commande de MXCCameraServer."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                args = f.read().split(b"\0")
        except (IOError, OSError):
            continue
        if args and args[0].endswith(b"MXCCameraServer") and b"-auth" in args:
            i = args.index(b"-auth")
            if i + 1 < len(args):
                return args[i + 1]
    return None


def camera_snapshot(timeout=8.0):
    """Lit le flux MJPEG et renvoie la premiere image JPEG complete."""
    auth = camera_auth()
    s = socket.create_connection(("127.0.0.1", CAMERA_PORT), timeout=timeout)
    try:
        req = "GET /api/v1/camera/stream HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        if auth:
            req += "Authorization: Basic %s\r\n" % base64.b64encode(auth).decode("ascii")
        s.sendall((req + "\r\n").encode("ascii"))
        buf = b""
        while len(buf) < 4 * 1024 * 1024:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            i = buf.find(b"Content-Length:")
            if i < 0:
                continue
            j = buf.find(b"\r\n\r\n", i)
            if j < 0:
                continue
            length = int(buf[i + 15:buf.find(b"\r\n", i)].strip())
            start = j + 4
            if len(buf) >= start + length:
                return buf[start:start + length]
        raise IOError("aucune image recue de la camera")
    finally:
        s.close()


# --------------------------------------------------------------------------- HTTP
DASHBOARD = u"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raise3D Pro2</title><style>
:root{--bg:#f4f4f2;--fg:#1d1d1b;--card:#fff;--mut:#6b6b66;--acc:#d9480f}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--card:#22221f;--mut:#9a9a94;--acc:#ff7a3d}}
body{margin:0;font:15px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:960px;margin:auto;padding:16px;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
section{background:var(--card);border-radius:10px;padding:14px}
h2{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.big{font-size:28px;font-weight:600}.mut{color:var(--mut)}
.bar{height:8px;background:var(--bg);border-radius:4px;overflow:hidden;margin:8px 0}
.bar div{height:100%;background:var(--acc);width:0}
img{width:100%;border-radius:6px;display:block}table{width:100%;border-collapse:collapse}
td{padding:3px 0}td:last-child{text-align:right;font-variant-numeric:tabular-nums}
</style></head><body><main>
<section><h2>Etat</h2><div class="big" id="state">...</div><div class="mut" id="file"></div>
<div class="bar"><div id="bar"></div></div><div id="prog" class="mut"></div></section>
<section><h2>Temperatures</h2><table id="temps"></table></section>
<section style="grid-column:1/-1"><h2>Camera</h2><img id="cam" alt="camera"></section>
</main><script>
function hms(s){if(s==null)return"-";var h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+"h"+("0"+m).slice(-2)}
var names={extruder:"Buse gauche",extruder1:"Buse droite",heater_bed:"Plateau"};
function tick(){fetch("status").then(function(r){return r.json()}).then(function(d){
 document.getElementById("state").textContent=d.state||"?";
 document.getElementById("file").textContent=d.filename||d.message||"";
 var p=d.progress_pct;document.getElementById("bar").style.width=(p||0)+"%";
 document.getElementById("prog").textContent=(p!=null?p+" %":"progression inconnue")+
  "  -  ecoule "+hms(d.print_duration_s)+"  -  reste ~"+hms(d.eta_s);
 var t="";for(var k in d.heaters||{}){var h=d.heaters[k];
  t+="<tr><td>"+(names[k]||k)+"</td><td>"+h.temp+" / "+h.target+" &deg;C</td></tr>"}
 document.getElementById("temps").innerHTML=t;}).catch(function(){})}
function cam(){document.getElementById("cam").src="snapshot.jpg?"+Date.now()}
tick();cam();setInterval(tick,2000);setInterval(cam,5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silencieux

    def send(self, code, ctype, body):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/status":
            self.send(200, "application/json", json.dumps(current_status(), indent=1))
        elif path == "/raw":
            with STATE.lock:
                raw = STATE.raw
            self.send(200, "application/json", json.dumps(raw, indent=1))
        elif path == "/snapshot.jpg":
            try:
                self.send(200, "image/jpeg", camera_snapshot())
            except Exception as e:
                self.send(503, "text/plain", "camera indisponible: %s" % e)
        elif path == "/":
            self.send(200, "text/html; charset=utf-8", DASHBOARD)
        else:
            self.send(404, "text/plain", "not found")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    t = threading.Thread(target=poller)
    t.daemon = True
    t.start()
    srv = ThreadedHTTPServer((HTTP_BIND, HTTP_PORT), Handler)
    log("r3monitor en ecoute sur http://%s:%d/" % (HTTP_BIND, HTTP_PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
