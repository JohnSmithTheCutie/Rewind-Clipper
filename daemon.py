"""
daemon.py — rewind background process.

Runs the recorder, serves the IPC socket, watches for crashes.
"""

import os
import sys
import json
import time
import signal
import socket
import logging
import threading
from pathlib import Path
from typing import Optional

SOCK_PATH = Path("/tmp/rewind.sock")
LOG_PATH  = Path.home() / ".local" / "share" / "rewind" / "rewind.log"


def setup_logging(verbose: bool = False):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    level  = logging.DEBUG if verbose else logging.INFO
    fmt    = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                               datefmt="%H:%M:%S")
    root   = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    for h in [logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)]:
        h.setFormatter(fmt)
        root.addHandler(h)


log = logging.getLogger("rewind.daemon")


# ── IPC helpers ───────────────────────────────────────────────────────────

def ipc_send(action: str, **kw) -> dict:
    if not SOCK_PATH.exists():
        return {"ok": False, "error": "rewind is not running"}
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(str(SOCK_PATH))
        s.sendall(json.dumps({"action": action, **kw}).encode())
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            try:
                json.loads(buf)
                break
            except json.JSONDecodeError:
                continue
        s.close()
        return json.loads(buf) if buf else {"ok": False, "error": "empty response"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class IPCServer:
    def __init__(self, recorder, cfg: dict):
        self.recorder = recorder
        self.cfg = cfg
        self._srv: Optional[socket.socket] = None
        self._running = False

    def start(self):
        if SOCK_PATH.exists():
            try: SOCK_PATH.unlink()
            except OSError: pass
        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._srv.bind(str(SOCK_PATH))
        self._srv.listen(8)
        self._srv.settimeout(1.0)
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="ipc").start()

    def stop(self):
        self._running = False
        try: self._srv.close()
        except Exception: pass

    def _loop(self):
        while self._running:
            try:
                conn, _ = self._srv.accept()
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle(self, conn):
        try:
            data = conn.recv(8192).decode()
            resp = self._dispatch(json.loads(data))
            conn.sendall(json.dumps(resp).encode())
        except Exception as e:
            try: conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode())
            except Exception: pass
        finally:
            conn.close()

    def _dispatch(self, cmd: dict) -> dict:
        action = cmd.get("action")

        if action == "clip":
            ok = self.recorder.save_clip()
            return {"ok": ok, "error": None if ok else "Recorder not running"}

        elif action == "status":
            return {
                "ok":        True,
                "recording": self.recorder.is_running(),
                "backend":   self.recorder.backend,
                "config":    self.cfg,
            }

        elif action == "stop":
            threading.Thread(target=self._shutdown, daemon=True).start()
            return {"ok": True}

        elif action == "update_config":
            from config import save
            save(cmd.get("updates", {}))
            self.cfg.update(cmd.get("updates", {}))
            return {"ok": True}

        return {"ok": False, "error": f"unknown action: {action}"}

    def _shutdown(self):
        time.sleep(0.1)
        self._running = False
        os.kill(os.getpid(), signal.SIGTERM)


# ── Main daemon entry ─────────────────────────────────────────────────────

def run_daemon(verbose: bool = False):
    setup_logging(verbose)

    from config import load, ensure_defaults
    from recorder import Recorder
    from ui import start_ui

    ensure_defaults()
    cfg = load()

    log.info("rewind starting")
    log.info(f"  monitor : {cfg['display'] or 'auto'}")
    log.info(f"  fps     : {cfg['fps']}")
    log.info(f"  buffer  : {cfg['buffer_duration']}s")
    log.info(f"  output  : {cfg['output_dir']}")

    recorder = Recorder(cfg)
    try:
        recorder.start()
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(1)

    ipc = IPCServer(recorder, cfg)
    ipc.start()

    threading.Thread(
        target=start_ui,
        args=(cfg["ui_port"], recorder, cfg),
        daemon=True
    ).start()

    port = cfg["ui_port"]
    print(f"\n  rewind is running")
    print(f"  ui   →  http://localhost:{port}")
    print(f"  logs →  {LOG_PATH}")
    print(f"\n  Ctrl-C to stop\n")

    def _sigterm(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _sigterm)

    try:
        while True:
            if not recorder.is_running():
                log.warning("Recorder exited — restarting in 3s")
                time.sleep(3)
                try:
                    recorder.start()
                except Exception as e:
                    log.error(f"Restart failed: {e}")
            time.sleep(4)
    except (KeyboardInterrupt, SystemExit):
        print("\n  stopping rewind...")
    finally:
        ipc.stop()
        recorder.stop()
        if SOCK_PATH.exists():
            try: SOCK_PATH.unlink()
            except OSError: pass
        log.info("rewind stopped")


# ── CLI helpers ───────────────────────────────────────────────────────────

def cmd_stop():
    r = ipc_send("stop")
    print("rewind stopped." if r.get("ok") else "rewind is not running.")


def cmd_clip():
    r = ipc_send("clip")
    if r.get("ok"):
        print("clip saved.")
    else:
        print(f"error: {r.get('error')}")


def cmd_status():
    r = ipc_send("status")
    if not r.get("ok"):
        print("rewind is not running.")
        return
    c = r.get("config", {})
    b = r.get("backend", "?")
    print(f"rewind is running")
    print(f"  backend : {b}")
    print(f"  monitor : {c.get('display') or 'auto'}")
    print(f"  fps     : {c.get('fps')}")
    print(f"  buffer  : {c.get('buffer_duration')}s")
    print(f"  output  : {c.get('output_dir')}")
