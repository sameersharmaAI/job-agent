# ==============================================================================
# FILE: setup_project.sh
# PURPOSE: One-time project bootstrap (dirs, venv, sanity checks, .env seeds)
# USAGE: bash setup_project.sh  [optional PROJECT_BASE_DIR]
# Notes:
# - Does NOT start services. That's what start_services.sh is for.
# - Creates/updates .env with ENGINE_DIR, TOKENIZER_DIR, etc. (no secrets hardcoded)
# ==============================================================================

#!/bin/bash
set -euo pipefail

# --- 0. Config / Defaults ---
PROJECT_BASE_DIR="${1:-/mnt/ssd/job_agent}"
ENV_FILE="${PROJECT_BASE_DIR}/.env"
VENV_DIR="${PROJECT_BASE_DIR}/venv"

# Defaults that mirror your confirmed working setup
DEFAULT_ENGINE_DIR="/mnt/ssd/llm_models/tensorrt_llm_engines/Llama-2-7b-chat-hf-gptq"
DEFAULT_TOKENIZER_DIR="/mnt/ssd/llm_models/hf_models/Llama-2-7b-chat-hf"
DEFAULT_IMAGE="dustynv/tensorrt_llm:0.12-r36.4.0"
DEFAULT_CONTAINER_NAME="trt_llm_server"
DEFAULT_OPENAI_PORT="8000"
DEFAULT_FORCE_BUILD="off"

echo "🚀 Starting project setup at ${PROJECT_BASE_DIR}..."

# --- 1. Create Project Directories ---
echo "📁 Creating project directory structure..."
mkdir -p "${PROJECT_BASE_DIR}"
cd "${PROJECT_BASE_DIR}"

mkdir -p config data logs resumes/customized resumes/base scrapers agents tools scripts
echo "✅ Directories ready at: $(pwd)"

# Try showing tree if available (optional)
if command -v tree >/dev/null 2>&1; then
  tree -L 2 || true
else
  echo "(tip) Install 'tree' for nicer directory previews: sudo apt-get install -y tree"
fi

# --- 2. System Dependencies (safe/quick checks) ---
echo "🔎 Checking system dependencies..."

need_sudo=0
if [ "$EUID" -ne 0 ]; then need_sudo=1; fi

# Update APT (only once if we need to install something)
apt_updated=0
maybe_apt_update() {
  if [ $apt_updated -eq 0 ]; then
    echo "ℹ️  Running apt-get update..."
    if [ $need_sudo -eq 1 ]; then sudo apt-get update -y; else apt-get update -y; fi
    apt_updated=1
  fi
}

ensure_pkg() {
  local pkg="$1"
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    maybe_apt_update
    echo "⬇️  Installing $pkg ..."
    if [ $need_sudo -eq 1 ]; then sudo apt-get install -y "$pkg"; else apt-get install -y "$pkg"; fi
  else
    echo "✅ $pkg already installed."
  fi
}

# python3-venv for local tooling; libreoffice kept since it was in your original script
ensure_pkg python3-venv
ensure_pkg libreoffice || true

# Check Docker (required for TRT-LLM server)
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker not found. Please install Docker and re-run this script."
  echo "   https://docs.docker.com/engine/install/"
  exit 1
else
  echo "✅ Docker is installed: $(docker --version)"
fi

# Check NVIDIA Container Runtime (Jetson needs this)
if ! command -v nvidia-container-runtime >/dev/null 2>&1; then
  echo "⚠️  nvidia-container-runtime not found."
  echo "   Install NVIDIA Container Toolkit for Jetson: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
else
  echo "✅ NVIDIA container runtime present."
fi

# --- 3. Python Virtual Environment (for your app/client tools) ---
if [ ! -d "${VENV_DIR}" ]; then
  echo "🐍 Creating Python virtual environment at '${VENV_DIR}'..."
  python3 -m venv "${VENV_DIR}"
  echo "✅ venv created."
else
  echo "✅ venv already exists at '${VENV_DIR}'."
fi

# --- 4. .env Management (idempotent) ---
echo "🧩 Ensuring .env exists and contains required keys..."
touch "${ENV_FILE}"

ensure_line () {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    # Update existing line in-place
    sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    echo "${key}=${value}" >> "${ENV_FILE}"
  fi
}

# Seed core variables (no secrets hardcoded)
ensure_line "ENGINE_DIR" "${DEFAULT_ENGINE_DIR}"
ensure_line "TOKENIZER_DIR" "${DEFAULT_TOKENIZER_DIR}"
ensure_line "TLLM_IMAGE" "${DEFAULT_IMAGE}"
ensure_line "CONTAINER_NAME" "${DEFAULT_CONTAINER_NAME}"
ensure_line "OPENAI_PORT" "${DEFAULT_OPENAI_PORT}"
ensure_line "FORCE_BUILD" "${DEFAULT_FORCE_BUILD}"

# Add HUGGINGFACE_TOKEN only if absent; leave blank for you to fill securely
if ! grep -qE "^HUGGINGFACE_TOKEN=" "${ENV_FILE}"; then
  echo "HUGGINGFACE_TOKEN=" >> "${ENV_FILE}"
fi

# Helpful comments once (only append if not already present)
if ! grep -q "## TensorRT-LLM OpenAI server config" "${ENV_FILE}"; then
  cat <<'EOF' >> "${ENV_FILE}"

## TensorRT-LLM OpenAI server config
# ENGINE_DIR and TOKENIZER_DIR must match your built engine and tokenizer.
# Example (already set above):
# ENGINE_DIR=/mnt/ssd/llm_models/tensorrt_llm_engines/Llama-2-7b-chat-hf-gptq
# TOKENIZER_DIR=/mnt/ssd/llm_models/hf_models/Llama-2-7b-chat-hf
#
# Fill in your Hugging Face token (no quotes):
# HUGGINGFACE_TOKEN=hf_xxx
#
# The Docker image and container name used by start_services.sh:
# TLLM_IMAGE=dustynv/tensorrt_llm:0.12-r36.4.0
# CONTAINER_NAME=trt_llm_server
#
# OpenAI-compatible server port (host mode):
# OPENAI_PORT=8000
#
# Force engine rebuild control for the container app (off/on):
# FORCE_BUILD=off
EOF
fi

echo "✅ .env is ready at: ${ENV_FILE}"

# --- 5. .gitignore niceties (optional) ---
if [ ! -f "${PROJECT_BASE_DIR}/.gitignore" ]; then
  cat <<'EOF' > "${PROJECT_BASE_DIR}/.gitignore"
# Python
__pycache__/
*.pyc
venv/

# Logs / data
logs/
data/

# Secrets / env
.env

# Office exports
*.pdf
*.docx
*.odt
EOF
  echo "✅ Created .gitignore"
else
  echo "✅ .gitignore already exists."
fi

# --- 6. Final Instructions ---
echo "------------------------------------------------------------------"
echo "✅ Project Setup Complete!"
echo "------------------------------------------------------------------"
echo "Next steps:"
echo "1) Activate venv:         source ${VENV_DIR}/bin/activate"
echo "2) Install requirements:  pip install -r requirements.txt  (after you place it in ${PROJECT_BASE_DIR})"
echo "3) Edit '${ENV_FILE}' and set HUGGINGFACE_TOKEN (and adjust paths if needed)."
echo "4) We'll wire 'start_services.sh' to read .env and launch the working Docker:"
echo "   docker run -d --rm --name \${CONTAINER_NAME} --runtime nvidia --network host \\"
echo "     -e HUGGINGFACE_TOKEN=\${HUGGINGFACE_TOKEN} -e FORCE_BUILD=\${FORCE_BUILD} \\"
echo "     -v \${ENGINE_DIR}:/data/engine -v \${TOKENIZER_DIR}:/data/tokenizer \\"
echo "     \${TLLM_IMAGE} python3 /opt/TensorRT-LLM/examples/apps/openai_server.py /data/engine --tokenizer /data/tokenizer"
echo
echo "When you're ready, send me your 'config.py' next, then 'start_services.sh'."
