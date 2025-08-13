#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# FILE: start_services.sh
# PURPOSE: Manage LLM container and the Python agent (start/stop/status/restart)
# USAGE: ./start_services.sh start-llm | stop-llm | status-llm | restart-llm | start-agent
# ==============================================================================

# --- Locate project & .env ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_BASE_DIR="${PROJECT_BASE_DIR:-${SCRIPT_DIR}}"
ENV_FILE="${PROJECT_BASE_DIR}/.env"

if [ -f "${ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
else
  echo "⚠️  ${ENV_FILE} not found. Continuing with current environment."
fi

# --- Vars (standard) ---
# Prefer standardized names; fall back to legacy MODEL_ENGINE_DIR for compatibility.
ENGINE_DIR="${ENGINE_DIR:-${MODEL_ENGINE_DIR:-/mnt/ssd/llm_models/tensorrt_llm_engines/Llama-2-7b-chat-hf-gptq}}"
TOKENIZER_DIR="${TOKENIZER_DIR:-/mnt/ssd/llm_models/hf_models/Llama-2-7b-chat-hf}"

TLLM_IMAGE="${TLLM_IMAGE:-dustynv/tensorrt_llm:0.12-r36.4.0}"
CONTAINER_NAME="${CONTAINER_NAME:-trt_llm_server}"
FORCE_BUILD="${FORCE_BUILD:-off}"
HUGGINGFACE_TOKEN="${HUGGINGFACE_TOKEN:-}"
OPENAI_PORT="${OPENAI_PORT:-8000}"

# Optional: if you want to reuse HF cache, set in .env:
# HUGGINGFACE_CACHE_DIR=/mnt/ssd/llm_models/hf_cache
HUGGINGFACE_CACHE_DIR="${HUGGINGFACE_CACHE_DIR:-}"

# --- Helpers ---
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "❌ Required command not found: $1"; exit 1; }
}

check_paths() {
  if [ ! -d "${ENGINE_DIR}" ]; then
    echo "❌ ENGINE_DIR does not exist: ${ENGINE_DIR}"
    exit 1
  fi
  if [ ! -d "${TOKENIZER_DIR}" ]; then
    echo "❌ TOKENIZER_DIR does not exist: ${TOKENIZER_DIR}"
    exit 1
  fi
}

container_exists() { docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; }
container_running() { docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; }

print_summary() {
  cat <<EOF
🔧 Launch config:
  CONTAINER_NAME : ${CONTAINER_NAME}
  TLLM_IMAGE     : ${TLLM_IMAGE}
  ENGINE_DIR     : ${ENGINE_DIR}
  TOKENIZER_DIR  : ${TOKENIZER_DIR}
  FORCE_BUILD    : ${FORCE_BUILD}
  OPENAI_PORT    : ${OPENAI_PORT} (host networking)
EOF
  if [ -n "${HUGGINGFACE_CACHE_DIR}" ]; then
    echo "  HF Cache       : ${HUGGINGFACE_CACHE_DIR}"
  fi
}

start_llm() {
  require_cmd docker
  check_paths

  if [ -z "${HUGGINGFACE_TOKEN}" ]; then
    echo "❌ HUGGINGFACE_TOKEN not set. Add it to ${ENV_FILE}."
    exit 1
  fi

  if container_running; then
    echo "✅ '${CONTAINER_NAME}' is already running."
    return 0
  fi

  if container_exists; then
    echo "ℹ️  Removing existing stopped container '${CONTAINER_NAME}'..."
    docker rm -f "${CONTAINER_NAME}" >/dev/null || true
  fi

  print_summary
  echo "🚀 Starting LLM container '${CONTAINER_NAME}' (detached)..."
  set -x
  docker run -d --rm \
    --name "${CONTAINER_NAME}" \
    --runtime nvidia \
    --network host \
    -e HUGGINGFACE_TOKEN="${HUGGINGFACE_TOKEN}" \
    -e FORCE_BUILD="${FORCE_BUILD}" \
    -v "${ENGINE_DIR}:/data/engine" \
    -v "${TOKENIZER_DIR}:/data/tokenizer" \
    $( [ -n "${HUGGINGFACE_CACHE_DIR}" ] && printf "%s" "-v ${HUGGINGFACE_CACHE_DIR}:/root/.cache/huggingface" ) \
    "${TLLM_IMAGE}" \
    python3 /opt/TensorRT-LLM/examples/apps/openai_server.py /data/engine --tokenizer /data/tokenizer
  set +x

  echo "✅ Launched. Logs: ./start_services.sh status-llm"
}

stop_llm() {
  require_cmd docker
  if container_exists; then
    echo "🛑 Stopping '${CONTAINER_NAME}'..."
    docker stop "${CONTAINER_NAME}" || true
    echo "✅ Stopped."
  else
    echo "ℹ️  Container '${CONTAINER_NAME}' not found."
  fi
}

status_llm() {
  require_cmd docker
  if container_exists; then
    echo "📜 Following logs for '${CONTAINER_NAME}' (Ctrl+C to exit)..."
    docker logs -f "${CONTAINER_NAME}"
  else
    echo "ℹ️  Container '${CONTAINER_NAME}' not running."
  fi
}

restart_llm() {
  stop_llm
  start_llm
}

start_agent() {
  local proj="${PROJECT_BASE_DIR:-${SCRIPT_DIR}}"
  if [ ! -f "${proj}/venv/bin/activate" ]; then
    echo "❌ Virtualenv not found in ${proj}/venv. Run setup_project.sh first."
    exit 1
  fi
  echo "🐍 Activating venv and starting agent..."
  # shellcheck disable=SC1091
  source "${proj}/venv/bin/activate"
  python "${proj}/main.py"
}

case "${1:-}" in
  start-llm)    start_llm ;;
  stop-llm)     stop_llm ;;
  status-llm)   status_llm ;;
  restart-llm)  restart_llm ;;
  start-agent)  start_agent ;;
  help|--help|-h|"")
    cat <<EOF
Usage: $0 {start-llm|stop-llm|status-llm|restart-llm|start-agent}

Commands:
  start-llm     Start TensorRT-LLM OpenAI-compatible server (detached)
  stop-llm      Stop the LLM container
  status-llm    Follow the LLM container logs
  restart-llm   Stop then start the LLM container
  start-agent   Activate venv and run main.py (foreground)
EOF
    ;;
esac
