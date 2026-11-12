#!/bin/bash
set -euo pipefail

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
SPOOL="$ROOT/data/distributed_spool"
PID_FILE="$ROOT/.streamlit_login_pid"
HOST_FILE="$ROOT/.streamlit_login_host"
PORT_FILE="$ROOT/.streamlit_login_port"
OUT_LOG="$ROOT/logs/streamlit-login.out"
ERR_LOG="$ROOT/logs/streamlit-login.err"

PORT="${STREAMLIT_PORT:-8501}"

is_running() {
    [ -f "$PID_FILE" ] || return 1

    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"

    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

start_ui() {
    if is_running; then
        echo "Streamlit already running: PID $(cat "$PID_FILE")"
        return 0
    fi

    rm -f "$PID_FILE"

    cd "$ROOT"
    mkdir -p logs

    source "$ROOT/.venv/bin/activate"

    if [ -f "$ROOT/.env.cluster" ]; then
        set -a
        source "$ROOT/.env.cluster"
        set +a
    fi

    export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
    export PYTHONUNBUFFERED=1
    export CONFIG="$ROOT/config.agentic_js.yml"
    export DISTRIBUTED_SPOOL_ROOT="$SPOOL"
    export UI_COMMAND_SPOOL="$SPOOL"
    export UI_READ_ONLY=1
    export DB_PATH="$(
        tr -d '[:space:]' \
          < "$ROOT/.current_agentic_js_eval_db"
    )"

    if ss -ltn |
       awk '{print $4}' |
       grep -Eq "(^|:)$PORT$"
    then
        echo "Port $PORT is already in use on $(hostname)"
        exit 1
    fi

    : > "$OUT_LOG"
    : > "$ERR_LOG"

    nohup "$ROOT/.venv/bin/streamlit" run \
      "$ROOT/ui/app.py" \
      --server.address=127.0.0.1 \
      --server.port="$PORT" \
      --server.headless=true \
      --server.fileWatcherType=none \
      --server.runOnSave=false \
      --browser.gatherUsageStats=false \
      >"$OUT_LOG" \
      2>"$ERR_LOG" \
      </dev/null &

    local pid="$!"

    printf '%s\n' "$pid" > "$PID_FILE"
    printf '%s\n' "$(hostname -s)" > "$HOST_FILE"
    printf '%s\n' "$PORT" > "$PORT_FILE"

    for attempt in $(seq 1 90); do
        if curl \
          -fsS \
          "http://127.0.0.1:${PORT}/_stcore/health" \
          >/dev/null
        then
            echo "Streamlit running on login node"
            echo "PID: $pid"
            echo "Host: $(hostname -s)"
            echo "Port: $PORT"
            return 0
        fi

        if ! kill -0 "$pid" 2>/dev/null; then
            echo "Streamlit exited during startup"
            cat "$ERR_LOG"
            exit 1
        fi

        sleep 2
    done

    echo "Streamlit health check timed out"
    cat "$ERR_LOG"
    exit 1
}

stop_ui() {
    if ! is_running; then
        echo "Streamlit is not running"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid
    pid="$(cat "$PID_FILE")"

    echo "Stopping Streamlit PID $pid"
    kill -TERM "$pid" 2>/dev/null || true

    for attempt in $(seq 1 30); do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo "Streamlit stopped"
            return 0
        fi

        sleep 1
    done

    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"

    echo "Streamlit force-stopped"
}

status_ui() {
    if is_running; then
        local port
        port="$(
          cat "$PORT_FILE" 2>/dev/null ||
          echo 8501
        )"

        echo "running"
        echo "pid=$(cat "$PID_FILE")"
        echo "host=$(cat "$HOST_FILE" 2>/dev/null || hostname -s)"
        echo "port=$port"

        curl \
          -fsS \
          "http://127.0.0.1:${port}/_stcore/health"

        echo
    else
        echo "stopped"
        return 1
    fi
}

case "${1:-start}" in
    start)
        start_ui
        ;;
    stop)
        stop_ui
        ;;
    restart)
        stop_ui
        start_ui
        ;;
    status)
        status_ui
        ;;
    logs)
        tail -n 100 "$OUT_LOG"
        echo
        tail -n 100 "$ERR_LOG"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 2
        ;;
esac
