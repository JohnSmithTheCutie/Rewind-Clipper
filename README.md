# Rewind-Clipper
Clipping software with a webUI for Arch, Debian/Ubuntu, Fedora, openSUSE based distros

# rewind

instant replay buffer for Linux. keep the last N minutes of your screen always buffered — save a clip whenever something worth keeping happens.

no OBS. no manual recording. just run it, forget about it, and hit **save clip** when you need it.

---

## table of contents

- [how it works](#how-it-works)
- [requirements](#requirements)
- [installation](#installation)
- [first run](#first-run)
- [cli reference](#cli-reference)
- [web ui](#web-ui)
- [configuration](#configuration)
  - [display / monitor](#display--monitor)
  - [fps](#fps)
  - [buffer duration](#buffer-duration)
  - [output directory](#output-directory)
  - [audio](#audio)
  - [encoder](#encoder)
  - [backend](#backend)
  - [ui port](#ui-port)
- [run on login](#run-on-login)
- [file structure](#file-structure)
- [troubleshooting](#troubleshooting)
  - [wrong monitor](#wrong-monitor-being-recorded)
  - [clip save fails](#clip-save-fails-immediately)
  - [no audio in clips](#no-audio-in-clips)
  - [NVIDIA issues](#nvidia-specific-issues)
  - [AMD / Intel issues](#amd--intel-issues)
  - [wf-recorder issues](#wf-recorder-issues)
  - [reading logs](#reading-logs)
- [distro-specific notes](#distro-specific-notes)
- [uninstall](#uninstall)

---

## how it works

rewind is a thin wrapper around [`gpu-screen-recorder`](https://git.dec05eba.com/gpu-screen-recorder/about/) (or `wf-recorder` as a fallback).

1. `rewind start` spawns the recording backend with a **replay buffer** — a fixed-size rolling window of encoded video kept in memory
2. the backend records continuously but doesn't write anything to disk until you ask it to
3. when you click **save clip** (or run `rewind clip`), rewind sends `SIGUSR1` to the recorder process, which flushes the current buffer to an mp4 in your output folder
4. a lightweight web UI on `localhost:8855` lets you trigger clips, browse saved files, and change settings

nothing is written to disk during normal operation — only when you explicitly save.

---

## requirements

| requirement | minimum version | notes |
|---|---|---|
| Linux | any modern kernel | Wayland or X11 |
| Python | 3.8+ | stdlib only, no pip deps required |
| recording backend | see below | at least one required |

### recording backends

| backend | gpu support | wayland | x11 | replay buffer | install |
|---|---|---|---|---|---|
| `gpu-screen-recorder` | NVIDIA, AMD, Intel | ✓ | ✓ | ✓ native | see below |
| `wf-recorder` | any | ✓ | ✗ | limited | see below |

**gpu-screen-recorder is strongly recommended.** it uses hardware encoding (NVENC on NVIDIA, VA-API on AMD/Intel), has near-zero CPU overhead, and has first-class replay buffer support.

**installing gpu-screen-recorder:**

```bash
# Arch / CachyOS / Manjaro
yay -S gpu-screen-recorder
# or
paru -S gpu-screen-recorder

# from source (any distro)
# https://git.dec05eba.com/gpu-screen-recorder/about/
```

**installing wf-recorder (fallback):**

```bash
# Arch
sudo pacman -S wf-recorder

# Debian / Ubuntu
sudo apt install wf-recorder

# Fedora
sudo dnf install wf-recorder
```

---

## installation

```bash
git clone https://github.com/yourusername/rewind
cd rewind
chmod +x install.sh
./install.sh
```

the installer does the following automatically:

- detects which recording backend you have installed
- runs `--list-monitors` to find your first available monitor
- writes a default config to `~/.config/rewind/config.ini`
- copies `recorder.py`, `daemon.py`, `ui.py`, `config.py` to `~/.local/lib/rewind/`
- installs the `rewind` binary to `~/.local/bin/rewind`
- creates a systemd user service at `~/.config/systemd/user/rewind.service`

### add `~/.local/bin` to your PATH

the installer puts `rewind` in `~/.local/bin`. if that's not in your PATH already:

```bash
# fish
fish_add_path ~/.local/bin
source ~/.config/fish/config.fish

# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## first run

```bash
rewind start
```

this will:
- start the daemon in the foreground
- begin buffering your screen immediately
- open the web UI at `http://localhost:8855` in your browser automatically

to verify it's working:

```bash
rewind status
```

output should look like:

```
rewind is running
  backend : gpu-screen-recorder
  monitor : DP-2
  fps     : 60
  buffer  : 120s
  output  : /home/yourname/Videos
```

---

## cli reference

```
rewind start           start the daemon (opens ui automatically)
rewind stop            stop the daemon
rewind clip            save a clip right now without opening the ui
rewind status          show what's currently running
rewind monitors        list all available monitors and their connector names
rewind ui              open the web ui in your browser
rewind start --verbose start with debug logging
```

### `rewind monitors`

this is the most useful command for initial setup. run it to find the correct name for your monitor:

```bash
rewind monitors
```

example output:

```
monitors (gpu-screen-recorder):
  DP-2      DP-2  1920x1080
  HDMI-A-2  HDMI-A-2  1920x1080
```

the first column is what you put in `display =` in the config.

---

## web ui

the web UI lives at **http://localhost:8855** and opens automatically when you run `rewind start`.

it has three tabs:

| tab | what's there |
|---|---|
| **clips** | list of saved mp4s with size and timestamp. save clip button. open folder button. |
| **status** | live view of backend, monitor, fps, buffer size, output path |
| **settings** | change monitor, fps, buffer, output folder, audio toggles, encoder, backend |

settings changed in the UI are saved to `~/.config/rewind/config.ini` immediately, but the daemon needs a restart to pick them up.

---

## configuration

the config file lives at:

```
~/.config/rewind/config.ini
```

it is created automatically on first install. to edit it manually:

```bash
nano ~/.config/rewind/config.ini
```

after any change, restart the daemon:

```bash
rewind stop && rewind start
```

full config with every option:

```ini
[rewind]
display            = DP-2
fps                = 60
buffer_duration    = 120
output_dir         = /home/yourname/Videos
capture_audio      = true
capture_microphone = false
encoder            = auto
backend            = auto
ui_port            = 8855
```

---

### display / monitor

```ini
display = DP-2
```

the connector name of the monitor you want to record. this must exactly match what `rewind monitors` shows in the first column.

**how to find your monitor name:**

```bash
rewind monitors
```

common connector names:

| name | what it usually is |
|---|---|
| `DP-1`, `DP-2` | DisplayPort monitors |
| `HDMI-A-1`, `HDMI-A-2` | HDMI monitors |
| `eDP-1` | laptop built-in screen |

**important quirk:** gpu-screen-recorder's `--list-monitors` outputs names like `DP-2|1920x1080`. the `|1920x1080` part is metadata and must not be included in the config — only `DP-2`. rewind strips this automatically.

if `display` is left blank, rewind will use the first monitor it detects.

---

### fps

```ini
fps = 60
```

frames per second to record. higher fps = smoother clips but more VRAM used for the buffer.

| value | use case |
|---|---|
| `30` | lower-end systems, saves VRAM |
| `60` | default — good for most games |
| `120` | high refresh rate monitors |
| `144` | 144hz monitors |

this should match or divide evenly into your monitor's refresh rate. recording at 60fps on a 144hz display is fine and common.

---

### buffer duration

```ini
buffer_duration = 120
```

how many seconds of footage the replay buffer holds. when you save a clip, you get up to this many seconds of footage ending at the moment you clicked save.

| value | what you get |
|---|---|
| `30` | last 30 seconds |
| `60` | last 1 minute |
| `120` | last 2 minutes (default) |
| `300` | last 5 minutes |
| `600` | last 10 minutes |

**memory usage** scales with `fps × resolution × buffer_duration`. rough guide at 1080p60 with h264_nvenc: ~200–500MB VRAM per 2 minutes depending on scene complexity.

---

### output directory

```ini
output_dir = /home/yourname/Videos
```

where to write mp4 files when you save a clip. the directory is created automatically if it doesn't exist.

```ini
# subfolder
output_dir = /home/yourname/Videos/clips

# external drive
output_dir = /mnt/ssd/gaming/clips

# tilde works
output_dir = ~/Videos/rewind
```

clips are named with a timestamp, e.g. `rewind_20250322_191500.mp4`.

---

### audio

```ini
capture_audio      = true
capture_microphone = false
```

**`capture_audio`** captures your desktop audio (games, music, system sounds) using your default PipeWire/PulseAudio output.

```ini
# disable audio entirely
capture_audio = false
```

**`capture_microphone`** captures from your default microphone input simultaneously.

```ini
# enable mic recording
capture_microphone = true
```

**changing which audio device is used:**

rewind uses `default_output` and `default_input`, which follow your system defaults. to change the default device:

```bash
# list all sinks (outputs)
pactl list short sinks

# set a new default
pactl set-default-sink <sink-name>

# list all sources (inputs / microphones)
pactl list short sources

# set a new default microphone
pactl set-default-source <source-name>
```

or change it through your desktop environment's sound settings.

**note for wf-recorder users:** wf-recorder does not reliably support capturing desktop audio + mic simultaneously on most systems. if you need both, switch to gpu-screen-recorder.

---

### encoder

```ini
encoder = auto
```

the video encoder to use. `auto` lets the backend pick the best one for your hardware. you should only override this if `auto` is picking something that doesn't work.

**NVIDIA encoders:**

| value | notes |
|---|---|
| `h264_nvenc` | widely compatible, good quality, fast — safe fallback for NVIDIA |
| `hevc_nvenc` | better compression than h264, same speed |
| `av1_nvenc` | best compression, requires RTX 40xx or newer |

**AMD / Intel encoders (VA-API):**

| value | notes |
|---|---|
| `h264_vaapi` | hardware h264 via VA-API |
| `hevc_vaapi` | hardware hevc via VA-API |
| `av1_vaapi` | requires RDNA3 (RX 7000) or Intel Arc |

**to test which encoders your GPU supports:**

```bash
gpu-screen-recorder --list-capture-options
```

---

### backend

```ini
backend = auto
```

which screen recorder to use.

| value | notes |
|---|---|
| `auto` | use gpu-screen-recorder if installed, otherwise wf-recorder |
| `gpu-screen-recorder` | force gpu-screen-recorder |
| `wf-recorder` | force wf-recorder |

leave this as `auto` unless you have both installed and need to override.

---

### ui port

```ini
ui_port = 8855
```

the port the web UI listens on. change this if port 8855 is already in use on your machine.

```ini
ui_port = 9000
```

then access the UI at `http://localhost:9000`.

---

## run on login

to start rewind automatically when you log into your desktop:

```bash
systemctl --user enable --now rewind
```

**useful commands:**

```bash
# check if it's running
systemctl --user status rewind

# view live logs
journalctl --user -u rewind -f

# restart (e.g. after changing config)
systemctl --user restart rewind

# stop and disable autostart
systemctl --user disable --now rewind
```

the service file is at `~/.config/systemd/user/rewind.service`. if rewind isn't starting on login, check that `WAYLAND_DISPLAY` or `DISPLAY` is set correctly in the service environment.

---

## file structure

```
~/.local/bin/
  rewind                      the cli binary

~/.local/lib/rewind/
  recorder.py                 backend wrapper (gpu-screen-recorder / wf-recorder)
  daemon.py                   ipc socket, process watchdog, shutdown handling
  ui.py                       web ui http server + html/css/js
  config.py                   config read/write (stdlib only)

~/.config/rewind/
  config.ini                  your settings

~/.config/systemd/user/
  rewind.service              systemd user service

~/.local/share/rewind/
  rewind.log                  daemon log file
```

---

## troubleshooting

### wrong monitor being recorded

**symptom:** clips show the wrong screen.

**fix:**

```bash
rewind monitors
```

find the connector name for your correct display. open the config:

```bash
nano ~/.config/rewind/config.ini
```

set:

```ini
display = DP-2    # use whatever your correct monitor name is
```

restart:

```bash
rewind stop && rewind start
```

**why this happens:** the installer picks the first monitor returned by `--list-monitors`, which may not be your primary one. `rewind monitors` shows all available options.

---

### clip save fails immediately

**symptom:** you click save clip and it fails instantly or after a few seconds.

**step 1 — check the log:**

```bash
tail -30 ~/.local/share/rewind/rewind.log
```

look for lines with `ERROR`.

**step 2 — run the backend manually** to see the raw error:

```bash
# replace DP-2 with your monitor, adjust output dir as needed
gpu-screen-recorder -w DP-2 -f 60 -r 30 -c mp4 -o /tmp
```

let it run 5–10 seconds, press `Ctrl-C`, check if a file appeared in `/tmp`.

**step 3 — start with verbose logging:**

```bash
rewind stop
rewind start --verbose
```

watch the output when you try to save. the exact error from the backend will appear.

**common causes:**

| log message | cause | fix |
|---|---|---|
| `GSR process is not running` | backend crashed | check NVIDIA KMS modeset (see below) |
| `No segments available` | buffer empty | wait a few seconds after starting before saving |
| `Monitor not found` | wrong display name | run `rewind monitors`, update config |

---

### no audio in clips

**symptom:** clips save correctly but are silent.

**check your default audio sink:**

```bash
pactl info | grep "Default Sink"
```

**verify audio capture is enabled in config:**

```ini
capture_audio = true
```

**check PipeWire or PulseAudio is running:**

```bash
systemctl --user status pipewire
# or
systemctl --user status pulseaudio
```

**if using wf-recorder:** wf-recorder's audio support is unreliable on many systems. switch to gpu-screen-recorder for reliable audio capture.

---

### NVIDIA-specific issues

**symptom:** `GSR process is not running`, backend crashes, or clips fail on a specific monitor.

**check KMS modesetting is enabled:**

```bash
sudo cat /sys/module/nvidia_drm/parameters/modeset
```

it should print `Y`. if it prints `N`:

```bash
echo 'options nvidia-drm modeset=1 fbdev=1' | sudo tee /etc/modprobe.d/nvidia.conf

# Arch / CachyOS — regenerate initramfs
sudo mkinitcpio -P

# Ubuntu / Debian
sudo update-initramfs -u

sudo reboot
```

after rebooting, confirm with:

```bash
sudo cat /sys/module/nvidia_drm/parameters/modeset   # should print Y
```

**encoder not supported on your card:**

if `hevc_nvenc` or `av1_nvenc` fail, fall back:

```ini
encoder = h264_nvenc
```

---

### AMD / Intel issues

**check VA-API is working:**

```bash
vainfo
```

if this fails, install the driver for your GPU:

```bash
# AMD
sudo pacman -S libva-mesa-driver mesa-vdpau    # Arch
sudo apt install libva-mesa-driver             # Ubuntu

# Intel (newer)
sudo pacman -S intel-media-driver             # Arch
sudo apt install intel-media-va-driver        # Ubuntu

# Intel (older, pre-Broadwell)
sudo pacman -S libva-intel-driver
```

set the encoder in config:

```ini
encoder = h264_vaapi
```

---

### wf-recorder issues

**"no segments available to clip from"**

wf-recorder does not have a native replay buffer. this error means clips cannot be saved. switch to gpu-screen-recorder.

**wf-recorder not finding display:**

wf-recorder requires Wayland. check you're on Wayland:

```bash
echo $XDG_SESSION_TYPE    # should print: wayland
echo $WAYLAND_DISPLAY     # should print: wayland-0 (or similar)
```

if you're on X11, you need gpu-screen-recorder instead.

---

### reading logs

```bash
# view the full log
cat ~/.local/share/rewind/rewind.log

# follow in real time
tail -f ~/.local/share/rewind/rewind.log

# only show errors
grep ERROR ~/.local/share/rewind/rewind.log

# last 50 lines
tail -50 ~/.local/share/rewind/rewind.log
```

via systemd (if running as a service):

```bash
journalctl --user -u rewind -f              # live
journalctl --user -u rewind --since today   # today only
journalctl --user -u rewind -n 100          # last 100 lines
```

---

## distro-specific notes

### Arch / CachyOS / Manjaro

everything works out of the box. install gpu-screen-recorder from the AUR:

```bash
yay -S gpu-screen-recorder
```

### Debian / Ubuntu

gpu-screen-recorder is not in the official repos. use wf-recorder as a fallback:

```bash
sudo apt install wf-recorder python3
```

for gpu-screen-recorder on Debian/Ubuntu, build from source:
https://git.dec05eba.com/gpu-screen-recorder/about/

### Fedora

```bash
sudo dnf install wf-recorder python3
```

gpu-screen-recorder may be available in COPR. check the project page for the latest info.

### openSUSE

```bash
sudo zypper install wf-recorder python3
```

---

## uninstall

```bash
# stop and disable the service
systemctl --user disable --now rewind

# remove installed files
rm -rf ~/.local/lib/rewind
rm -f ~/.local/bin/rewind
rm -f ~/.config/systemd/user/rewind.service
systemctl --user daemon-reload

# remove config and logs (optional — skip if you want to keep your settings)
rm -rf ~/.config/rewind
rm -rf ~/.local/share/rewind
```

---

## license

MIT — do whatever you want with it.
