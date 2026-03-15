#!/usr/bin/env python3
"""
Tuya Pulsar consumer:
- Trigger Dreame clean when trigger code is reported.
- Optionally forward parsed payload to a Home Assistant webhook.
"""

import json
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pulsar
import requests

from config import (
    ACCESS_ID,
    ACCESS_KEY,
    ENABLE_VACUUM_CALL,
    ENABLE_WEIGHT_SAVE,
    HA_BASE_URL,
    HA_TOKEN,
    MQ_ENV,
    PULSAR_SERVER_URL,
    SUBSCRIPTION_NAME,
    TRIGGER_CODE,
    VACUUM_ENTITY_ID,
    VACUUM_SEGMENTS,
    WEBHOOK_PATH,
)
from message_util import decrypt_message, message_id
from mq_authentication import get_authentication

DEBUG_PORT = 8099
shutdown = False
SESSION_IDLE_TIMEOUT_SEC = 3.0
SESSION_MAX_DURATION_SEC = 15.0
REQUIRED_CODES = ("excretion_time_day", "cat_weight")

# Per-device aggregation window to handle out-of-order property reports.
_sessions = {}


def _on_signal(_sig, _frame):
    global shutdown
    shutdown = True


def _collect_code_values(obj: dict) -> dict:
    codes = {}
    biz_data = obj.get("bizData") or {}
    for item in biz_data.get("properties") or []:
        code = item.get("code")
        if code and code not in codes:
            codes[code] = item.get("value")
    for item in obj.get("status") or []:
        code = item.get("code")
        if code and code not in codes:
            codes[code] = item.get("value")
    return codes


def _has_trigger_code(obj: dict) -> bool:
    codes = _collect_code_values(obj)
    return TRIGGER_CODE in codes


def _extract_dev_id(obj: dict) -> str:
    biz_data = obj.get("bizData") or {}
    return str(biz_data.get("devId") or "")


def _normalize_weight_kg(raw_weight):
    if raw_weight is None:
        return None
    try:
        w = float(raw_weight)
    except (TypeError, ValueError):
        return None
    # Tuya cat_weight is commonly integer with scale=3 (e.g. 4220 => 4.220 kg).
    if w > 100:
        w = w / 1000.0
    return round(w, 3)


def _upsert_session(dev_id: str, msg_id: str, obj: dict, codes: dict) -> None:
    now = time.time()
    sess = _sessions.get(dev_id)
    if not sess:
        sess = {
            "start_at": now,
            "last_at": now,
            "codes": {},
            "msg_ids": [],
            "last_raw": None,
        }
        _sessions[dev_id] = sess
    sess["last_at"] = now
    sess["codes"].update(codes)
    sess["msg_ids"].append(msg_id)
    sess["last_raw"] = obj


def _should_flush_session(sess: dict) -> bool:
    now = time.time()
    idle = now - sess["last_at"]
    alive = now - sess["start_at"]
    return idle >= SESSION_IDLE_TIMEOUT_SEC or alive >= SESSION_MAX_DURATION_SEC


def _flush_session(dev_id: str, sess: dict) -> None:
    codes = sess.get("codes") or {}
    missing = [c for c in REQUIRED_CODES if c not in codes]
    if missing:
        print(f"[session] drop dev={dev_id}, missing required codes: {missing}")
        return

    weight_kg = _normalize_weight_kg(codes.get("cat_weight"))
    payload = {
        "dev_id": dev_id,
        "msg_ids": sess.get("msg_ids") or [],
        "trigger_code": "excretion_time_day",
        "codes": codes,
        "weight": weight_kg,
        "raw": sess.get("last_raw"),
    }
    print(
        f"[session] ready dev={dev_id} excretion_time_day={codes.get('excretion_time_day')} "
        f"cat_weight_raw={codes.get('cat_weight')} weight_kg={weight_kg}"
    )

    if ENABLE_VACUUM_CALL:
        call_dreame_vacuum()
    if ENABLE_WEIGHT_SAVE:
        call_ha_webhook(payload)


def _flush_ready_sessions() -> None:
    expired = []
    for dev_id, sess in _sessions.items():
        if _should_flush_session(sess):
            expired.append(dev_id)
    for dev_id in expired:
        sess = _sessions.pop(dev_id, None)
        if sess:
            _flush_session(dev_id, sess)


def _resolve_webhook_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not HA_BASE_URL:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return f"{HA_BASE_URL}{path}"


def call_dreame_vacuum():
    """Call HA Dreame segment cleaning. Returns (ok, message)."""
    if not HA_BASE_URL or not HA_TOKEN:
        msg = "[trigger] missing HA_BASE_URL/HA_TOKEN, skip vacuum call"
        print(msg)
        return False, msg

    url = f"{HA_BASE_URL}/api/services/dreame_vacuum/vacuum_clean_segment"
    payload = {"entity_id": VACUUM_ENTITY_ID, "segments": VACUUM_SEGMENTS}
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        msg = f"[trigger] called dreame clean: {VACUUM_ENTITY_ID} segments={VACUUM_SEGMENTS}"
        print(msg)
        return True, msg
    except requests.RequestException as e:
        msg = f"[trigger] HA call failed: {e}"
        print(msg, file=sys.stderr)
        return False, msg


def call_ha_webhook(payload: dict):
    """Optionally forward trigger payload to HA webhook. Returns (ok, message)."""
    url = _resolve_webhook_url(WEBHOOK_PATH)
    if not url:
        msg = "[webhook] skipped (webhook_path not configured)"
        print(msg)
        return False, msg

    headers = {"Content-Type": "application/json"}
    if HA_TOKEN:
        headers["Authorization"] = f"Bearer {HA_TOKEN}"
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        msg = f"[webhook] posted: {url}"
        print(msg)
        return True, msg
    except requests.RequestException as e:
        msg = f"[webhook] failed: {e}"
        print(msg, file=sys.stderr)
        return False, msg


class DebugHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DEBUG_HTML.encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/trigger":
            ok, msg = call_dreame_vacuum()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


DEBUG_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dreame Tuya Trigger - Debug</title>
<style>body{font-family:sans-serif;max-width:420px;margin:2em auto;padding:1em;background:#1c1c1e;color:#eee;}
h1{font-size:1.1em;color:#0a84ff;} button{width:100%;padding:12px;font-size:16px;background:#0a84ff;color:#fff;border:none;border-radius:8px;cursor:pointer;}
button:hover{background:#409cff;} button:disabled{opacity:0.6;cursor:not-allowed;} #result{margin-top:1em;padding:0.8em;border-radius:8px;font-size:14px;white-space:pre-wrap;}
#result.ok{background:#2d4a2d;color:#8ae08a;} #result.err{background:#4a2d2d;color:#e08a8a;}
</style></head><body>
<h1>Dreame Tuya Trigger</h1>
<p>Manual test to call Dreame segment clean.</p>
<button id="btn">Test Trigger</button>
<div id="result"></div>
<script>
var btn=document.getElementById('btn'), result=document.getElementById('result');
btn.onclick=function(){
  btn.disabled=true; result.textContent='Requesting...'; result.className='';
  fetch('/trigger',{method:'POST'}).then(function(r){return r.json();}).then(function(d){
    result.textContent=(d.ok?'Success: ':'Failed: ')+d.message; result.className=d.ok?'ok':'err';
  }).catch(function(e){ result.textContent='Request failed: '+e; result.className='err'; })
  .finally(function(){ btn.disabled=false; });
};
</script></body></html>
"""


def handle_message(pulsar_message, decrypt_msg: str, msg_id: str) -> None:
    print(f"[msg_id={msg_id}] decrypted:")
    try:
        obj = json.loads(decrypt_msg)
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        codes = _collect_code_values(obj)
        dev_id = _extract_dev_id(obj)
        if dev_id and codes:
            _upsert_session(dev_id, msg_id, obj, codes)
            if TRIGGER_CODE in codes:
                print(f"[trigger] detected code={TRIGGER_CODE} dev={dev_id}")
    except json.JSONDecodeError:
        print(decrypt_msg)


def _run_debug_server():
    server = HTTPServer(("0.0.0.0", DEBUG_PORT), DebugHandler)
    server.serve_forever()


def main() -> int:
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    if not ACCESS_ID or not ACCESS_KEY:
        print("Error: missing tuya_access_id / tuya_access_key", file=sys.stderr)
        return 1

    debug_thread = threading.Thread(target=_run_debug_server, daemon=True)
    debug_thread.start()
    print(f"Debug page: http://<host>:{DEBUG_PORT}/")

    topic = f"{ACCESS_ID}/out/{MQ_ENV}"
    print(f"Connecting Pulsar: {PULSAR_SERVER_URL}")
    print(f"Topic: {topic}, subscription: {SUBSCRIPTION_NAME}")
    print(f"Waiting messages (trigger code: {TRIGGER_CODE})...\n")

    client = pulsar.Client(
        PULSAR_SERVER_URL,
        authentication=get_authentication(ACCESS_ID, ACCESS_KEY),
        tls_allow_insecure_connection=True,
    )
    consumer = client.subscribe(
        topic, SUBSCRIPTION_NAME, consumer_type=pulsar.ConsumerType.Failover
    )

    try:
        while not shutdown:
            _flush_ready_sessions()
            try:
                pulsar_message = consumer.receive(timeout_millis=3000)
            except Exception as e:
                if "Timeout" in str(type(e).__name__) or "timeout" in str(e).lower():
                    continue
                raise

            msg_id = message_id(pulsar_message.message_id())
            print(f"--- received message_id: {msg_id}")
            try:
                decrypted = decrypt_message(pulsar_message, ACCESS_KEY)
                print(f"decrypted head: {decrypted[:200]}{'...' if len(decrypted) > 200 else ''}")
                handle_message(pulsar_message, decrypted, msg_id)
            except Exception as e:
                print(f"decrypt/handle failed: {e}", file=sys.stderr)
            consumer.acknowledge_cumulative(pulsar_message)
    except pulsar.Interrupted:
        print("Interrupted")
    finally:
        for dev_id in list(_sessions.keys()):
            sess = _sessions.pop(dev_id)
            _flush_session(dev_id, sess)
        consumer.close()
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
