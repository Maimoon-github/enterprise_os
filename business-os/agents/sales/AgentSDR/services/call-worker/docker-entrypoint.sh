#!/bin/sh
set -e
echo "[entrypoint] starting PulseAudio"
# A virtual speaker: WhatsApp Web plays the lead's voice here, the extension taps it.
# A container restarted in place keeps the last PulseAudio's pid file and
# socket; the new daemon then refused to start and pactl failed "Connection
# refused" on every restart (29 Oct 2026). Clear them, and wait for it.
pulseaudio --kill 2>/dev/null || true
rm -rf /tmp/pulse-* "${XDG_RUNTIME_DIR:-/nonexistent}/pulse" /run/user/*/pulse "$HOME"/.config/pulse/*-runtime "$HOME"/.config/pulse/*.pid 2>/dev/null || true
pulse_ready=false
for i in 1 2 3 4 5; do
  pulseaudio -D --exit-idle-time=-1 --system=false --log-target=file:/tmp/pulseaudio.log 2>>/tmp/pulseaudio.log || true
  for j in 1 2 3 4 5; do
    if pactl info >/dev/null 2>&1; then pulse_ready=true; break; fi
    sleep 0.4
  done
  [ "$pulse_ready" = true ] && break
  echo "[entrypoint] PulseAudio not up yet (attempt $i)"
  pulseaudio --kill 2>/dev/null || true
  sleep 1
done
if [ "$pulse_ready" = true ]; then
  pactl load-module module-null-sink sink_name=agentsdr >/dev/null
  pactl set-default-sink agentsdr
else
  # Better a running worker without the virtual speaker than a restart loop.
  echo "[entrypoint] WARNING: PulseAudio did not start; continuing without the virtual speaker. Its log:"
  tail -n 20 /tmp/pulseaudio.log 2>/dev/null || true
fi
# A virtual screen, started directly: xvfb-run hung as the container's PID 1
# (it needs xauth, which --no-install-recommends leaves out, and waits on a
# signal from Xvfb) — the worker never started and logged nothing (23 Oct 2026).
echo "[entrypoint] starting Xvfb on :99"
rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99
for i in 1 2 3 4 5 6 7 8 9 10; do
  [ -e /tmp/.X11-unix/X99 ] && break
  sleep 0.5
done
[ -e /tmp/.X11-unix/X99 ] || { echo "[entrypoint] Xvfb did not start:"; cat /tmp/xvfb.log; exit 1; }
export HEADLESS=false
echo "[entrypoint] starting the worker"
exec node --import tsx src/main.ts
