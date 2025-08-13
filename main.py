import os
import sys
import time
import json
import requests

from config import APP_CONFIG

# -----------------------------
# Helper: ping OpenAI-compatible server
# -----------------------------
def check_llm_server() -> bool:
    """
    Send a minimal OpenAI-compatible /v1/chat/completions request.
    Your TRT-LLM server typically ignores the 'model' value, but we pass one anyway.
    """
    url = APP_CONFIG.LLM_API_URL
    payload = {
        "model": "llama-2-7b-chat",  # name is informational for this server
        "messages": [{"role": "user", "content": "Ping"}],
        "max_tokens": 1,
        "temperature": 0
    }
    headers = {"Content-Type": "application/json"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            return True
        else:
            print(f"[LLM] HTTP {r.status_code} -> {r.text[:300]}")
            return False
    except requests.exceptions.ConnectionError:
        print("[LLM] Connection error (is the container running and on --network host?).")
        return False
    except requests.exceptions.Timeout:
        print("[LLM] Request timed out (server busy or not reachable).")
        return False
    except Exception as e:
        print(f"[LLM] Unexpected error: {e}")
        return False


def main():
    print("=======================================")
    print("    AI Job Application Agent Started   ")
    print("=======================================")

    # Verify engine/tokenizer paths (matches your Docker binds)
    try:
        APP_CONFIG.verify_paths()
    except Exception as e:
        print(f"❌ Path verification failed: {e}")
        print("→ Check ENGINE_DIR and TOKENIZER_DIR in your .env")
        sys.exit(1)

    # Show where we're pointing
    print("Config summary:", json.dumps(APP_CONFIG.summary(), indent=2))

    # Wait for the TRT-LLM server to come online (if you started it in another shell)
    retries = 10
    while retries > 0:
        if check_llm_server():
            print("✅ LLM server is online.")
            break
        print(f"LLM server not found at {APP_CONFIG.LLM_API_URL}. Retrying in 10s... ({retries} left)")
        time.sleep(10)
        retries -= 1

    if retries == 0 and not check_llm_server():
        print("❌ Could not connect to the LLM server.")
        print("→ Start it with:  ./start_services.sh start-llm")
        sys.exit(1)

    # Resume parsing demo
    from tools.resume_parser import get_resume_text  # import here so the script still runs without tools/ during setup
    resume_path = APP_CONFIG.BASE_RESUME_PATH

    if not os.path.isfile(resume_path):
        print(f"❌ Base resume not found at: {resume_path}")
        print("→ Place your base resume in 'resumes/base/' and/or set BASE_RESUME_NAME in .env")
        sys.exit(1)

    resume_text = get_resume_text(resume_path)
    if isinstance(resume_text, str) and resume_text.startswith("Error:"):
        print(resume_text)
        sys.exit(1)

    print("✅ Resume parsed successfully. First 500 characters:")
    print((resume_text or "")[:500] + "...")
    # TODO: Continue with your agent workflow here (crewai, scraping, etc.)


if __name__ == "__main__":
    # Ensure project directories exist (logs, resumes/base)
    APP_CONFIG.ensure_dirs()
    main()
