import os
from dotenv import load_dotenv

# Resolve PROJECT_BASE_DIR early so we can load the right .env
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.getenv("PROJECT_BASE_DIR", _THIS_DIR)
ENV_PATH = os.path.join(PROJECT_BASE_DIR, ".env")

# Load environment variables from .env (prefer project .env, else fallback)
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

class Config:
    """
    Centralized configuration for the Job Agent and the local TRT-LLM server.
    All defaults mirror your confirmed working setup, with env-var overrides.
    """

    # --- Personal / Credentials (keep secrets in .env)
    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
    HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

    YOUR_NAME = os.getenv("YOUR_NAME", "Unknown")
    YOUR_EMAIL = os.getenv("YOUR_EMAIL")
    YOUR_PHONE = os.getenv("YOUR_PHONE")
    YOUR_LINKEDIN_PROFILE = os.getenv("YOUR_LINKEDIN_PROFILE")
    YOUR_GITHUB_PROFILE = os.getenv("YOUR_GITHUB_PROFILE")
    DESIRED_EXPERIENCE_LEVELS = os.getenv("DESIRED_EXPERIENCE_LEVELS")
    POSTED_WITHIN_DAYS = int(os.getenv("POSTED_WITHIN_DAYS"))
    DEFAULT_JOB_LOCATION = os.getenv("DEFAULT_JOB_LOCATION")

    # --- OpenAI-compatible LLM endpoint (served by TRT-LLM container)
    OPENAI_PORT = int(os.getenv("OPENAI_PORT", "8000"))
    LLM_API_URL = os.getenv(
        "LLM_API_URL",
        f"http://localhost:{OPENAI_PORT}/v1/chat/completions"
    )

    # --- Paths
    PROJECT_BASE_DIR = os.getenv("PROJECT_BASE_DIR", PROJECT_BASE_DIR)
    LOGS_DIR = os.path.join(PROJECT_BASE_DIR, "logs")
    BASE_RESUME_DIR = os.path.join(PROJECT_BASE_DIR, "resumes", "base")

    BASE_RESUME_NAME = os.getenv("BASE_RESUME_NAME", "resume.docx")
    BASE_RESUME_PATH = os.path.join(BASE_RESUME_DIR, BASE_RESUME_NAME)

    # --- TensorRT-LLM engine/tokenizer paths (standardized)
    # Prefer ENGINE_DIR/TOKENIZER_DIR; fall back to legacy MODEL_ENGINE_DIR for compatibility.
    ENGINE_DIR = os.getenv(
        "ENGINE_DIR",
        os.getenv("MODEL_ENGINE_DIR", "/mnt/ssd/llm_models/tensorrt_llm_engines/Llama-2-7b-chat-hf-gptq")
    )
    TOKENIZER_DIR = os.getenv(
        "TOKENIZER_DIR",
        "/mnt/ssd/llm_models/hf_models/Llama-2-7b-chat-hf"
    )

    # --- Docker runtime settings for the TRT-LLM container
    TLLM_IMAGE = os.getenv("TLLM_IMAGE", "dustynv/tensorrt_llm:0.12-r36.4.0")
    CONTAINER_NAME = os.getenv("CONTAINER_NAME", "trt_llm_server")
    FORCE_BUILD = os.getenv("FORCE_BUILD", "off")  # 'off' mirrors your working run

    # --- Job search params (unchanged)
    JOB_SEARCH_KEYWORDS = [
        "Data Scientist", "Data Analyst", "Machine Learning Engineer",
        "Business Intelligence", "Data Visualization", "SQL Developer",
    ]
    POSTED_WITHIN_DAYS = int(os.getenv("POSTED_WITHIN_DAYS", "7"))

    # --- Directory helpers / validations
    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.LOGS_DIR, exist_ok=True)
        os.makedirs(Config.BASE_RESUME_DIR, exist_ok=True)

    @staticmethod
    def verify_paths():
        if not os.path.isdir(Config.ENGINE_DIR):
            raise FileNotFoundError(f"ENGINE_DIR does not exist: {Config.ENGINE_DIR}")
        if not os.path.isdir(Config.TOKENIZER_DIR):
            raise FileNotFoundError(f"TOKENIZER_DIR does not exist: {Config.TOKENIZER_DIR}")

    @staticmethod
    def summary():
        return {
            "PROJECT_BASE_DIR": Config.PROJECT_BASE_DIR,
            "LLM_API_URL": Config.LLM_API_URL,
            "ENGINE_DIR": Config.ENGINE_DIR,
            "TOKENIZER_DIR": Config.TOKENIZER_DIR,
            "TLLM_IMAGE": Config.TLLM_IMAGE,
            "CONTAINER_NAME": Config.CONTAINER_NAME,
            "OPENAI_PORT": Config.OPENAI_PORT,
            "FORCE_BUILD": Config.FORCE_BUILD,
            # new:
            "DESIRED_EXPERIENCE_LEVELS": Config.DESIRED_EXPERIENCE_LEVELS,
            "POSTED_WITHIN_DAYS": Config.POSTED_WITHIN_DAYS,
            "DEFAULT_JOB_LOCATION": Config.DEFAULT_JOB_LOCATION,
        }
# Initialize app directories immediately
APP_CONFIG = Config()
APP_CONFIG.ensure_dirs()

if __name__ == "__main__":
    APP_CONFIG.ensure_dirs()
    try:
        APP_CONFIG.verify_paths()
        print("✅ Path verification passed.")
    except Exception as e:
        print(f"❌ Path verification failed: {e}")
    print("Summary:", APP_CONFIG.summary())
    print(f"Logs directory: {APP_CONFIG.LOGS_DIR}")
    print(f"Base resume path: {APP_CONFIG.BASE_RESUME_PATH}")
