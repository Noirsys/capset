#!/usr/bin/env bash
# run.sh — the cap set engine (v2): start | stop | status | restart
#   bash run.sh start     # installs numpy + ortools into .venv (first time), stops the old v1 loop, starts the engine
#                         #   as a user service (capset-engine) that restarts itself; dashboard on port 8170
#   bash run.sh status    # is it running? what has it found?
#   bash run.sh stop
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
VENV="$HERE/.venv"
PY="$VENV/bin/python"
have_user_systemd() { command -v systemd-run >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; }

case "${1:-start}" in
  start|restart)
    if [ ! -x "$PY" ]; then python3 -m venv "$VENV" 2>/dev/null || python3 -m venv --without-pip "$VENV"; fi
    if ! "$PY" -c "import numpy, ortools" 2>/dev/null; then
      if ! "$PY" -m pip --version >/dev/null 2>&1; then
        # no pip in this venv (python3-venv not installed system-wide): bootstrap it without root
        curl -sS -m 120 https://bootstrap.pypa.io/get-pip.py | "$PY" - -q || { echo "could not bootstrap pip"; exit 1; }
      fi
      "$PY" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
      "$PY" -m pip install -q -r requirements.txt
    fi
    "$PY" -c "import numpy, ortools; print('deps ok: numpy', numpy.__version__, 'ortools', ortools.__version__)"
    # the v1 loop (discovery_superloop.py) is superseded; stop it gently so it writes its checkpoint, then firmly
    if pgrep -f discovery_superloop.py >/dev/null 2>&1; then
      pkill -INT -f discovery_superloop.py || true; sleep 6; pkill -f discovery_superloop.py || true
      echo "stopped the v1 loop (its checkpoint stays in ../asdf_discovery/)"
    fi
    mkdir -p state records
    if have_user_systemd; then
      systemctl --user stop capset-engine >/dev/null 2>&1 || true
      systemctl --user reset-failed capset-engine >/dev/null 2>&1 || true
      systemd-run --user --unit=capset-engine --description="cap set record engine" \
        --property=Restart=always --property=RestartSec=15 --property=WorkingDirectory="$HERE" \
        --setenv=PYTHONUNBUFFERED=1 "$PY" "$HERE/engine.py"
      sleep 2; systemctl --user --no-pager --lines=3 status capset-engine || true
    else
      if [ -f .pid ] && kill -0 "$(cat .pid)" 2>/dev/null; then kill "$(cat .pid)"; sleep 2; fi
      setsid nohup "$PY" engine.py > engine.out 2>&1 < /dev/null &
      echo $! > .pid
      echo "started (pid $!)"
    fi
    echo "dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8170/"
    ;;
  stop)
    if have_user_systemd; then systemctl --user stop capset-engine; else [ -f .pid ] && kill "$(cat .pid)" && rm -f .pid; fi
    echo "stopped";;
  status)
    if have_user_systemd; then systemctl --user --no-pager --lines=5 status capset-engine || true; fi
    [ -x "$PY" ] && "$PY" engine.py --status | head -60;;
  *) sed -n '2,7p' "$0"; exit 2;;
esac
