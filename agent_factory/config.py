import os
import re
from pathlib import Path

# Derive workspace from repo root (parent of this file's package directory).
# Override with AGENT_WORKSPACE env var for CI / alternate installs.
WORKSPACE_DIR = Path(os.getenv("AGENT_WORKSPACE", str(Path(__file__).resolve().parents[1])))
OUTPUT_DIR    = WORKSPACE_DIR / "output"
LOGS_DIR      = WORKSPACE_DIR / "logs"
# No mkdir at import time — directories are created on first use.


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-._")
    return s[:50]


def resolve_run_name(name: str) -> str:
    """Sanitizes a project name and avoids overwriting an existing run (auto-suffix)."""
    base = _slug(name) if name else ""
    if not base:
        from datetime import datetime
        base = "project_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate, n = base, 2
    while (OUTPUT_DIR / candidate).exists():
        candidate, n = f"{base}-{n}", n + 1
    return candidate

# Default models — override via .env
# Examples:
#   OpenAI:  gpt-4o-mini, gpt-4o
#   Claude:  anthropic/claude-haiku-4-5-20251001, anthropic/claude-sonnet-4-6
#   Ollama:  ollama/mistral:7b, ollama/qwen2.5-coder:7b, ollama/qwen2.5-coder:14b
#   Gemini:  gemini/gemini-2.0-flash
DEFAULT_FAST_MODEL     = os.getenv("LLM_FAST_MODEL",     "gpt-4o-mini")
DEFAULT_REASONING_MODEL = os.getenv("LLM_REASONING_MODEL", "gpt-4o")
DEFAULT_ANALYSIS_MODEL  = os.getenv("LLM_ANALYSIS_MODEL",  DEFAULT_FAST_MODEL)

# Iterations configuration
MAX_AUDIT_ITERATIONS = 10

# Load .env into os.environ (without overwriting existing vars)
ENV_PATH = WORKSPACE_DIR / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

# Re-read model defaults after .env load
DEFAULT_FAST_MODEL      = os.getenv("LLM_FAST_MODEL",      DEFAULT_FAST_MODEL)
DEFAULT_REASONING_MODEL = os.getenv("LLM_REASONING_MODEL", DEFAULT_REASONING_MODEL)
DEFAULT_ANALYSIS_MODEL  = os.getenv("LLM_ANALYSIS_MODEL",  DEFAULT_FAST_MODEL)

_PROVIDER_ENV = {
    "openai":     ["OPENAI_API_KEY"],
    "anthropic":  ["ANTHROPIC_API_KEY"],
    "gemini":     ["GEMINI_API_KEY"],
    "vertex_ai":  ["VERTEXAI_PROJECT"],
    "azure":      ["AZURE_API_KEY", "AZURE_API_BASE"],
    "cohere":     ["COHERE_API_KEY"],
    "mistral":    ["MISTRAL_API_KEY"],
    "groq":       ["GROQ_API_KEY"],
    "deepseek":   ["DEEPSEEK_API_KEY"],
}


def _provider_for_model(model: str) -> str:
    model_lower = model.lower()
    if model_lower.startswith("ollama/") or model_lower.startswith("ollama_chat/"):
        return "ollama"
    if model_lower.startswith("anthropic/") or "claude" in model_lower:
        return "anthropic"
    if model_lower.startswith("gemini/"):
        return "gemini"
    if model_lower.startswith("gpt-") or model_lower.startswith("openai/"):
        return "openai"
    if model_lower.startswith("groq/"):
        return "groq"
    if model_lower.startswith("mistral/"):
        return "mistral"
    if model_lower.startswith("deepseek/"):
        return "deepseek"

    try:
        from litellm import get_llm_provider
        _, provider, _, _ = get_llm_provider(model)
        return provider or "unknown"
    except Exception:
        return "unknown"


def validate_llm_setup(model: str) -> tuple[bool, str]:
    """Checks that the environment has credentials for the given model."""
    provider = _provider_for_model(model)

    if provider == "ollama":
        return True, ""

    required = _PROVIDER_ENV.get(provider, [])
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        vars_str = ", ".join(missing)
        return (
            False,
            f"Model '{model}' (provider: {provider}) requires: {vars_str}. "
            f"Add them to .env or export them in your shell.",
        )
    return True, ""


def validate_default_models() -> tuple[bool, str]:
    """Validates credentials for all three default models used by the orchestrator."""
    errors = []
    for model in {DEFAULT_FAST_MODEL, DEFAULT_REASONING_MODEL, DEFAULT_ANALYSIS_MODEL}:
        ok, error = validate_llm_setup(model)
        if not ok:
            errors.append(error)
    if errors:
        return False, "\n".join(errors)
    return True, ""
