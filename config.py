"""
config.py — ~/.config/rewind/config.ini

Pure stdlib (configparser). No third-party deps.
Created automatically on first run with sensible defaults.
"""

import configparser
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "rewind" / "config.ini"

DEFAULTS = {
    "display":            "",       # blank = auto-detect first monitor
    "fps":                "60",
    "buffer_duration":    "120",    # seconds of replay buffer
    "output_dir":         str(Path.home() / "Videos"),
    "capture_audio":      "true",
    "capture_microphone": "false",
    "encoder":            "auto",   # auto, h264_nvenc, hevc_nvenc, av1_nvenc
    "backend":            "auto",   # auto, gpu-screen-recorder, wf-recorder
    "ui_port":            "8855",
}


def _cp() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp["rewind"] = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        cp.read(CONFIG_PATH)
    return cp


def load() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    s = _cp()["rewind"]
    return {
        "display":            s.get("display", "").strip() or None,
        "fps":                s.getint("fps", 60),
        "buffer_duration":    s.getint("buffer_duration", 120),
        "output_dir":         s.get("output_dir", str(Path.home() / "Videos")).strip(),
        "capture_audio":      s.getboolean("capture_audio", True),
        "capture_microphone": s.getboolean("capture_microphone", False),
        "encoder":            s.get("encoder", "auto").strip(),
        "backend":            s.get("backend", "auto").strip(),
        "ui_port":            s.getint("ui_port", 8855),
    }


def save(updates: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cp = _cp()
    for k, v in updates.items():
        cp["rewind"][k] = "" if v is None else str(v)
    with open(CONFIG_PATH, "w") as f:
        cp.write(f)


def ensure_defaults():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        save({})
