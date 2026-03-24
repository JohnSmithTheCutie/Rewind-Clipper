"""
recorder.py — screen recording backend for rewind.

Supports gpu-screen-recorder (best, NVIDIA/AMD/Intel) and wf-recorder (fallback).

The key quirk: gpu-screen-recorder --list-monitors emits "DP-2|1920x1080"
but its -w flag only accepts "DP-2". We strip the resolution suffix.
"""

import os
import shutil
import signal
import logging
import subprocess
import threading
from typing import Optional

log = logging.getLogger("rewind.recorder")


def detect_backend() -> str:
    for b in ("gpu-screen-recorder", "wf-recorder"):
        if shutil.which(b):
            return b
    raise RuntimeError(
        "No supported recording backend found.\n\n"
        "Install one:\n"
        "  gpu-screen-recorder (NVIDIA/AMD/Intel, best):\n"
        "    yay -S gpu-screen-recorder          # Arch/CachyOS\n"
        "    paru -S gpu-screen-recorder\n\n"
        "  wf-recorder (any Wayland compositor):\n"
        "    sudo pacman -S wf-recorder          # Arch\n"
        "    sudo apt install wf-recorder        # Debian/Ubuntu\n"
    )


def list_monitors(backend: Optional[str] = None) -> list[dict]:
    """
    Return [{id, label}] for available monitors.
    Handles the DP-2|1920x1080 → DP-2 parsing for gpu-screen-recorder.
    Falls back to xrandr if backend listing fails.
    """
    if backend is None:
        try:
            backend = detect_backend()
        except RuntimeError:
            backend = None

    monitors = []

    if backend == "gpu-screen-recorder":
        try:
            r = subprocess.run(
                ["gpu-screen-recorder", "--list-monitors"],
                capture_output=True, text=True, timeout=5
            )
            for line in (r.stdout + r.stderr).splitlines():
                line = line.strip()
                if not line or line.lower().startswith("monitor"):
                    continue
                parts = line.split("|", 1)
                ident = parts[0].split()[0]          # "DP-2"
                res   = parts[1].strip() if len(parts) > 1 else ""
                label = f"{ident}  {res}" if res else ident
                monitors.append({"id": ident, "label": label})
        except Exception as e:
            log.warning(f"GSR monitor list failed: {e}")

    elif backend == "wf-recorder":
        try:
            r = subprocess.run(
                ["wf-recorder", "--list-outputs"],
                capture_output=True, text=True, timeout=5
            )
            for line in (r.stdout + r.stderr).splitlines():
                line = line.strip()
                if line:
                    ident = line.split()[0]
                    monitors.append({"id": ident, "label": line})
        except Exception as e:
            log.warning(f"wf-recorder output list failed: {e}")

    if not monitors:
        try:
            r = subprocess.run(
                ["xrandr", "--listmonitors"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.splitlines():
                parts = line.strip().split()
                if parts and ":" in parts[0]:
                    name = parts[-1]
                    monitors.append({"id": name, "label": name})
        except Exception:
            pass

    return monitors


def resolve_monitor(preferred: Optional[str], backend: str) -> str:
    monitors = list_monitors(backend)
    ids = [m["id"] for m in monitors]
    if preferred and preferred in ids:
        return preferred
    if preferred and ids:
        log.warning(f"Monitor '{preferred}' not found in {ids}, using: {ids[0]}")
        return ids[0]
    return ids[0] if ids else "screen"


class Recorder:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.backend: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            backend = self.cfg.get("backend", "auto")
            self.backend = detect_backend() if backend == "auto" else backend

            monitor = resolve_monitor(self.cfg.get("display"), self.backend)
            out_dir = self.cfg.get("output_dir", os.path.expanduser("~/Videos"))
            os.makedirs(out_dir, exist_ok=True)

            if self.backend == "gpu-screen-recorder":
                cmd = self._gsr_cmd(monitor, out_dir)
            elif self.backend == "wf-recorder":
                cmd = self._wf_cmd(monitor, out_dir)
            else:
                raise RuntimeError(f"Unknown backend: {self.backend}")

            log.info(f"Starting {self.backend} on {monitor}")
            log.debug("CMD: " + " ".join(cmd))
            self._stop_evt.clear()
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            threading.Thread(target=self._watch, daemon=True).start()

    def _gsr_cmd(self, monitor: str, out_dir: str) -> list[str]:
        c = self.cfg
        cmd = [
            "gpu-screen-recorder",
            "-w", monitor,
            "-f", str(c.get("fps", 60)),
            "-r", str(c.get("buffer_duration", 120)),
            "-c", "mp4",
            "-o", out_dir,
        ]
        audio = []
        if c.get("capture_audio", True):
            audio.append("default_output")
        if c.get("capture_microphone", False):
            audio.append("default_input")
        if audio:
            cmd += ["-a", "|".join(audio)]
        enc = c.get("encoder", "auto")
        if enc != "auto":
            cmd += ["-k", enc]
        return cmd

    def _wf_cmd(self, monitor: str, out_dir: str) -> list[str]:
        c = self.cfg
        return [
            "wf-recorder",
            "-o", monitor,
            "--framerate", str(c.get("fps", 60)),
            "-f", os.path.join(out_dir, "rewind_%Y%m%d_%H%M%S.mp4"),
        ]

    def _watch(self):
        for line in self._proc.stdout:
            line = line.strip()
            if line:
                log.debug(f"[{self.backend}] {line}")
        self._proc.wait()
        if not self._stop_evt.is_set():
            log.warning(f"{self.backend} exited (code {self._proc.returncode})")

    def save_clip(self) -> bool:
        with self._lock:
            if not self.is_running():
                log.error("Recorder not running")
                return False
            if self.backend == "gpu-screen-recorder":
                try:
                    os.kill(self._proc.pid, signal.SIGUSR1)
                    log.info(f"Clip saved (SIGUSR1 → pid {self._proc.pid})")
                    return True
                except ProcessLookupError:
                    log.error("GSR process disappeared")
                    return False
            log.error(f"Backend '{self.backend}' does not support replay-buffer clips")
            return False

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self):
        self._stop_evt.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
