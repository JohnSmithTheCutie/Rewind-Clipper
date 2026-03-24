"""
ui.py — rewind web UI served on localhost:8855
"""

import json
import logging
import subprocess
import threading
import time
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("rewind.ui")

# ─────────────────────────────────────────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>rewind</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Outfit:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --carbon:   #0c0c0e;
  --carbon1:  #111114;
  --carbon2:  #18181d;
  --carbon3:  #1f1f26;
  --line:     #26262f;
  --line2:    #31313d;
  --purple:   #7c3aed;
  --purple2:  #9d5bf5;
  --purple3:  #c4a0ff;
  --glow:     rgba(124, 58, 237, 0.4);
  --glow2:    rgba(124, 58, 237, 0.15);
  --green:    #22c55e;
  --green-bg: rgba(34, 197, 94, 0.08);
  --red:      #ef4444;
  --ink:      #e8e8f0;
  --ink2:     #9898b0;
  --ink3:     #55555f;
  --mono: 'DM Mono', monospace;
  --body: 'Outfit', sans-serif;
}

html, body {
  height: 100%;
  background: var(--carbon);
  color: var(--ink);
  font-family: var(--body);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* subtle grain */
body::after {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E");
  pointer-events: none; z-index: 9999; opacity: .6;
}

.app { display: grid; grid-template-rows: 52px 1fr; height: 100vh; }

/* ── topbar ── */
.bar {
  display: flex; align-items: center; gap: 0;
  background: var(--carbon1);
  border-bottom: 1px solid var(--line);
  padding: 0 24px;
  position: relative; z-index: 10;
}
.wordmark {
  font-family: var(--mono);
  font-size: 13px; font-weight: 500;
  letter-spacing: 3px; text-transform: lowercase;
  color: var(--ink2);
  margin-right: 32px;
  user-select: none;
}
.wordmark strong { color: var(--purple3); font-weight: 500; }

.tabs { display: flex; }
.tab {
  height: 52px; padding: 0 18px;
  display: flex; align-items: center;
  font-size: 12px; font-weight: 500;
  letter-spacing: 0.5px;
  color: var(--ink3);
  background: none; border: none;
  border-bottom: 1.5px solid transparent;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.tab:hover { color: var(--ink2); }
.tab.on { color: var(--ink); border-bottom-color: var(--purple2); }

.bar-right {
  margin-left: auto;
  display: flex; align-items: center; gap: 10px;
}
.badge {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 1.5px; text-transform: uppercase;
  color: var(--ink3);
}
.pip {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 0 2px var(--green-bg), 0 0 8px var(--green);
  animation: breathe 3s ease-in-out infinite;
}
.pip.dead { background: var(--ink3); box-shadow: none; animation: none; }
@keyframes breathe { 0%,100%{opacity:1} 50%{opacity:.35} }

/* ── content ── */
.scroll { overflow-y: auto; height: 100%; }
.pane { display: none; padding: 28px 28px; max-width: 880px; margin: 0 auto; }
.pane.on { display: block; }

/* ── clips tab ── */
.clips-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 24px;
}
.clips-head h1 {
  font-size: 22px; font-weight: 600; letter-spacing: -0.3px;
  color: var(--ink);
}
.clips-head p {
  font-size: 12px; color: var(--ink3); font-family: var(--mono);
  margin-top: 3px;
}

/* THE button */
.btn-save {
  position: relative;
  background: var(--carbon2);
  border: 1px solid var(--purple);
  color: var(--purple3);
  padding: 11px 28px;
  font-family: var(--body); font-size: 13px; font-weight: 600;
  letter-spacing: 0.5px;
  border-radius: 5px;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
  /* the underglow */
  box-shadow:
    0 0 0 0 transparent,
    0 4px 24px var(--glow2),
    0 1px 0 rgba(255,255,255,0.04) inset;
}
.btn-save::before {
  /* glow ring that expands on hover */
  content: '';
  position: absolute; inset: -1px;
  border-radius: 6px;
  background: transparent;
  box-shadow: 0 0 0 0 var(--glow);
  transition: box-shadow 0.25s;
}
.btn-save:hover {
  background: rgba(124,58,237,0.1);
  border-color: var(--purple2);
  color: #fff;
  box-shadow:
    0 0 0 0 transparent,
    0 6px 32px var(--glow),
    0 1px 0 rgba(255,255,255,0.06) inset;
}
.btn-save:hover::before { box-shadow: 0 0 16px 2px var(--glow); }
.btn-save:active { transform: translateY(1px); }
.btn-save:disabled { opacity: 0.35; cursor: not-allowed; transform: none; box-shadow: none; }

.clip-list { display: grid; gap: 6px; }

.clip-row {
  display: flex; align-items: center; gap: 14px;
  background: var(--carbon1);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px 16px;
  transition: border-color 0.15s;
}
.clip-row:hover { border-color: var(--line2); }

.clip-thumb {
  width: 32px; height: 32px; border-radius: 4px;
  background: var(--carbon3);
  border: 1px solid var(--line2);
  display: flex; align-items: center; justify-content: center;
  color: var(--purple2); font-size: 11px;
  flex-shrink: 0;
}
.clip-body { flex: 1; min-width: 0; }
.clip-name {
  font-size: 13px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--ink);
}
.clip-meta {
  font-family: var(--mono); font-size: 10px;
  color: var(--ink3); margin-top: 2px;
}
.btn-ghost {
  background: transparent;
  border: 1px solid var(--line2);
  color: var(--ink3);
  padding: 4px 12px;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.5px;
  border-radius: 4px; cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
  white-space: nowrap; flex-shrink: 0;
}
.btn-ghost:hover { border-color: var(--purple); color: var(--purple3); }

.empty {
  text-align: center; padding: 64px 0;
  color: var(--ink3);
}
.empty .e-icon { font-size: 32px; margin-bottom: 12px; opacity: 0.4; }
.empty p { font-family: var(--mono); font-size: 12px; line-height: 2; }

/* ── status tab ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.stat-cell {
  background: var(--carbon1);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 16px 18px;
}
.stat-cell .key {
  font-family: var(--mono); font-size: 9px; font-weight: 500;
  letter-spacing: 2px; text-transform: uppercase;
  color: var(--ink3); margin-bottom: 6px;
}
.stat-cell .val {
  font-size: 18px; font-weight: 600; color: var(--ink);
}
.val.ok  { color: var(--green); }
.val.hi  { color: var(--purple3); }
.val.err { color: var(--red); }
.wide { grid-column: 1 / -1; }
.wide .val { font-size: 12px; font-family: var(--mono); color: var(--ink2); }

/* ── settings tab ── */
.set-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.set-panel {
  background: var(--carbon1);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 20px 20px;
}
.set-panel h3 {
  font-family: var(--mono); font-size: 9px; font-weight: 500;
  letter-spacing: 2px; text-transform: uppercase;
  color: var(--ink3); margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}
.field { margin-bottom: 12px; }
.field label {
  display: block;
  font-family: var(--mono); font-size: 9px;
  letter-spacing: 1.5px; text-transform: uppercase;
  color: var(--ink3); margin-bottom: 5px;
}
.field select,
.field input[type=text],
.field input[type=number] {
  width: 100%;
  background: var(--carbon);
  border: 1px solid var(--line2);
  color: var(--ink);
  padding: 8px 10px;
  font-family: var(--mono); font-size: 12px;
  border-radius: 4px; outline: none;
  transition: border-color 0.15s;
  appearance: none;
}
.field select:focus,
.field input:focus {
  border-color: var(--purple);
  box-shadow: 0 0 0 3px rgba(124,58,237,0.12);
}
.tog-row {
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}
.tog-row:last-of-type { border: none; }
.tog-row label { font-size: 13px; color: var(--ink2); }
.tog {
  width: 36px; height: 20px; border-radius: 10px;
  background: var(--carbon3); border: 1px solid var(--line2);
  cursor: pointer; position: relative; flex-shrink: 0;
  transition: background 0.2s, border-color 0.2s;
}
.tog.on { background: var(--purple); border-color: var(--purple); }
.tog::after {
  content: ''; position: absolute;
  width: 14px; height: 14px; border-radius: 50%;
  background: #fff; top: 2px; left: 2px;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}
.tog.on::after { transform: translateX(16px); }
.set-footer { grid-column: 1/-1; display: flex; justify-content: flex-end; }

.btn-submit {
  position: relative;
  background: var(--carbon2);
  border: 1px solid var(--purple);
  color: var(--purple3);
  padding: 9px 24px;
  font-family: var(--body); font-size: 12px; font-weight: 600;
  letter-spacing: 0.5px;
  border-radius: 5px; cursor: pointer;
  box-shadow: 0 4px 20px var(--glow2);
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.btn-submit:hover {
  background: rgba(124,58,237,0.12);
  color: #fff;
  box-shadow: 0 6px 28px var(--glow);
}

/* ── toast ── */
.toast {
  position: fixed; bottom: 20px; right: 20px;
  background: var(--carbon2);
  border: 1px solid var(--line2);
  color: var(--ink2);
  padding: 10px 16px;
  border-radius: 5px;
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.3px;
  opacity: 0; transform: translateY(6px); pointer-events: none;
  transition: opacity 0.2s, transform 0.2s;
  z-index: 1000;
}
.toast.show { opacity: 1; transform: none; }
.toast.ok  { border-color: var(--green); color: var(--green); }
.toast.err { border-color: var(--red);   color: var(--red);   }
</style>
</head>
<body>
<div class="app">

  <div class="bar">
    <div class="wordmark">re<strong>wind</strong></div>
    <div class="tabs">
      <button class="tab on" onclick="nav('clips', this)">clips</button>
      <button class="tab"    onclick="nav('status', this)">status</button>
      <button class="tab"    onclick="nav('settings', this)">settings</button>
    </div>
    <div class="bar-right">
      <div class="badge">
        <div class="pip" id="pip"></div>
        <span id="pipTxt">recording</span>
      </div>
    </div>
  </div>

  <div class="scroll">

    <!-- clips -->
    <div class="pane on" id="pane-clips">
      <div class="clips-head">
        <div>
          <h1>clips</h1>
          <p id="clipSubtitle">last 2 minutes always buffered</p>
        </div>
        <button class="btn-save" id="saveBtn" onclick="doSave()">save clip</button>
      </div>
      <div class="clip-list" id="clipList">
        <div class="empty">
          <div class="e-icon">◎</div>
          <p>nothing saved yet<br>hit save clip to grab the last 2 min</p>
        </div>
      </div>
    </div>

    <!-- status -->
    <div class="pane" id="pane-status">
      <div class="stat-grid">
        <div class="stat-cell"><div class="key">status</div><div class="val ok" id="stStatus">—</div></div>
        <div class="stat-cell"><div class="key">monitor</div><div class="val hi" id="stMon">—</div></div>
        <div class="stat-cell"><div class="key">fps</div><div class="val" id="stFps">—</div></div>
        <div class="stat-cell"><div class="key">buffer</div><div class="val" id="stBuf">—</div></div>
        <div class="stat-cell"><div class="key">backend</div><div class="val" id="stBack">—</div></div>
        <div class="stat-cell wide"><div class="key">output</div><div class="val" id="stOut">—</div></div>
      </div>
    </div>

    <!-- settings -->
    <div class="pane" id="pane-settings">
      <div class="set-grid">
        <div class="set-panel">
          <h3>recording</h3>
          <div class="field">
            <label>monitor</label>
            <select id="cMon"></select>
          </div>
          <div class="field">
            <label>fps</label>
            <select id="cFps">
              <option value="30">30</option>
              <option value="60" selected>60</option>
              <option value="120">120</option>
              <option value="144">144</option>
            </select>
          </div>
          <div class="field">
            <label>buffer (seconds)</label>
            <input type="number" id="cBuf" value="120" min="10" max="600">
          </div>
          <div class="field">
            <label>output folder</label>
            <input type="text" id="cOut" value="">
          </div>
        </div>
        <div class="set-panel">
          <h3>audio</h3>
          <div class="tog-row">
            <label>desktop audio</label>
            <div class="tog on" id="tAud" onclick="this.classList.toggle('on')"></div>
          </div>
          <div class="tog-row">
            <label>microphone</label>
            <div class="tog" id="tMic" onclick="this.classList.toggle('on')"></div>
          </div>
          <div class="field" style="margin-top:16px">
            <label>encoder</label>
            <select id="cEnc">
              <option value="auto">auto</option>
              <option value="h264_nvenc">h264_nvenc  (nvidia)</option>
              <option value="hevc_nvenc">hevc_nvenc  (nvidia)</option>
              <option value="av1_nvenc">av1_nvenc   (nvidia)</option>
              <option value="h264_vaapi">h264_vaapi  (amd/intel)</option>
            </select>
          </div>
          <div class="field">
            <label>backend</label>
            <select id="cBack">
              <option value="auto">auto</option>
              <option value="gpu-screen-recorder">gpu-screen-recorder</option>
              <option value="wf-recorder">wf-recorder</option>
            </select>
          </div>
        </div>
        <div class="set-footer">
          <button class="btn-submit" onclick="doSaveSettings()">save settings</button>
        </div>
      </div>
    </div>

  </div>
</div>

<div class="toast" id="toast"></div>

<script>
function nav(name, btn) {
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  document.getElementById('pane-' + name).classList.add('on');
  btn.classList.add('on');
  if (name === 'clips')    loadClips();
  if (name === 'status')   loadStatus();
  if (name === 'settings') { loadStatus(); loadMonitors(); }
}

function toast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3000);
}

async function doSave() {
  const btn = document.getElementById('saveBtn');
  btn.disabled = true;
  btn.textContent = 'saving...';
  try {
    const d = await fetch('/api/clip', { method: 'POST' }).then(r => r.json());
    if (d.ok) {
      toast('clip saved');
      setTimeout(loadClips, 2500);
    } else {
      toast(d.error || 'failed', 'err');
    }
  } catch {
    toast('cannot reach rewind', 'err');
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = 'save clip'; }, 2500);
}

let _cfg = {};

async function loadStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    const running = d.recording;
    document.getElementById('pip').className    = 'pip' + (running ? '' : ' dead');
    document.getElementById('pipTxt').textContent = running ? 'recording' : 'stopped';
    _cfg = d.config || {};
    const backend = d.backend || '—';

    document.getElementById('stStatus').textContent = running ? 'recording' : 'stopped';
    document.getElementById('stStatus').className   = 'val ' + (running ? 'ok' : 'err');
    document.getElementById('stMon').textContent  = _cfg.display || 'auto';
    document.getElementById('stFps').textContent  = _cfg.fps ? _cfg.fps + ' fps' : '—';
    document.getElementById('stBuf').textContent  = _cfg.buffer_duration ? _cfg.buffer_duration + 's' : '—';
    document.getElementById('stBack').textContent = backend;
    document.getElementById('stOut').textContent  = _cfg.output_dir || '—';

    // sync settings fields
    if (_cfg.fps)             document.getElementById('cFps').value  = _cfg.fps;
    if (_cfg.buffer_duration) document.getElementById('cBuf').value  = _cfg.buffer_duration;
    if (_cfg.output_dir)      document.getElementById('cOut').value  = _cfg.output_dir;
    if (_cfg.encoder)         document.getElementById('cEnc').value  = _cfg.encoder;
    if (_cfg.backend)         document.getElementById('cBack').value = _cfg.backend;
    if (typeof _cfg.capture_audio === 'boolean')
      document.getElementById('tAud').className = 'tog' + (_cfg.capture_audio ? ' on' : '');
    if (typeof _cfg.capture_microphone === 'boolean')
      document.getElementById('tMic').className = 'tog' + (_cfg.capture_microphone ? ' on' : '');
  } catch {}
}

async function loadClips() {
  try {
    const d = await fetch('/api/clips').then(r => r.json());
    const el = document.getElementById('clipList');
    if (!d.clips?.length) {
      el.innerHTML = `<div class="empty"><div class="e-icon">◎</div><p>nothing saved yet<br>hit save clip to grab the last 2 min</p></div>`;
      return;
    }
    el.innerHTML = d.clips.map(c => `
      <div class="clip-row">
        <div class="clip-thumb">▶</div>
        <div class="clip-body">
          <div class="clip-name">${c.name}</div>
          <div class="clip-meta">${c.size} · ${c.mtime}</div>
        </div>
        <button class="btn-ghost" onclick="openFolder()">open folder</button>
      </div>`).join('');
  } catch {}
}

async function loadMonitors() {
  try {
    const d = await fetch('/api/monitors').then(r => r.json());
    const sel = document.getElementById('cMon');
    sel.innerHTML = (d.monitors || []).map(m =>
      `<option value="${m.id}">${m.id}</option>`).join('');
    if (_cfg.display) sel.value = _cfg.display;
  } catch {}
}

async function doSaveSettings() {
  const body = {
    display:            document.getElementById('cMon').value,
    fps:                +document.getElementById('cFps').value,
    buffer_duration:    +document.getElementById('cBuf').value,
    output_dir:         document.getElementById('cOut').value.trim(),
    encoder:            document.getElementById('cEnc').value,
    backend:            document.getElementById('cBack').value,
    capture_audio:      document.getElementById('tAud').classList.contains('on'),
    capture_microphone: document.getElementById('tMic').classList.contains('on'),
  };
  try {
    const d = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());
    if (d.ok) toast('saved — restart rewind to apply');
    else toast(d.error || 'error', 'err');
  } catch { toast('failed', 'err'); }
}

async function openFolder() {
  await fetch('/api/open-folder', { method: 'POST' });
}

// poll
loadStatus();
loadClips();
setInterval(loadStatus, 5000);
setInterval(() => {
  if (document.getElementById('pane-clips').classList.contains('on')) loadClips();
}, 9000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    recorder = None
    cfg = None

    def log_message(self, *a): pass

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/index.html'):
            self._resp(200, 'text/html', PAGE.encode())
        elif p == '/api/status':
            self._json({
                'ok': True,
                'recording': self.recorder.is_running() if self.recorder else False,
                'backend':   getattr(self.recorder, 'backend', None),
                'config':    self.cfg or {},
            })
        elif p == '/api/monitors':
            from recorder import list_monitors
            backend = (self.cfg or {}).get('backend', 'auto')
            if backend == 'auto':
                try:
                    from recorder import detect_backend
                    backend = detect_backend()
                except RuntimeError:
                    backend = None
            self._json({'ok': True, 'monitors': list_monitors(backend)})
        elif p == '/api/clips':
            self._json({'ok': True, 'clips': self._list_clips()})
        else:
            self._resp(404, 'text/plain', b'not found')

    def do_POST(self):
        p = urlparse(self.path).path
        if p == '/api/clip':
            if not self.recorder:
                self._json({'ok': False, 'error': 'no recorder'})
                return
            ok = self.recorder.save_clip()
            self._json({'ok': ok, 'error': None if ok else 'recorder not running'})

        elif p == '/api/settings':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            try:
                from config import save
                save(body)
                if self.cfg is not None:
                    self.cfg.update(body)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})

        elif p == '/api/open-folder':
            out = (self.cfg or {}).get('output_dir', str(Path.home() / 'Videos'))
            try:
                subprocess.Popen(['xdg-open', out],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            self._json({'ok': True})

        else:
            self._resp(404, 'text/plain', b'not found')

    def _list_clips(self) -> list:
        out = Path((self.cfg or {}).get('output_dir', str(Path.home() / 'Videos')))
        clips = []
        try:
            files = sorted(out.glob('*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files[:30]:
                st   = f.stat()
                mb   = st.st_size / 1024 / 1024
                when = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%b %d  %H:%M')
                clips.append({'name': f.name, 'size': f'{mb:.1f} MB', 'mtime': when})
        except Exception:
            pass
        return clips

    def _json(self, d, status=200):
        body = json.dumps(d).encode()
        self._resp(status, 'application/json', body)

    def _resp(self, status, ct, body):
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


def start_ui(port: int, recorder, cfg: dict):
    Handler.recorder = recorder
    Handler.cfg = cfg
    server = HTTPServer(('127.0.0.1', port), Handler)
    log.info(f'ui → http://127.0.0.1:{port}/')

    def _open():
        time.sleep(1.5)
        try:
            subprocess.Popen(['xdg-open', f'http://127.0.0.1:{port}/'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()
    server.serve_forever()
