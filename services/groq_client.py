# services/groq_client.py
import os
from dotenv import load_dotenv
from groq import AsyncGroq

# Load .env from the repo root so GROQ_API_KEY etc. are available in every
# entrypoint (CLI scripts, pytest smoke runs, and later the FastAPI app).
load_dotenv()

_client: AsyncGroq | None = None
_fallback_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set.")
        _client = AsyncGroq(api_key=api_key)
    return _client


def get_groq_fallback_client() -> AsyncGroq | None:
    """Secondary Groq client on the fallback API key.

    Reserved for rate-limit/availability degradation (consumed by the Phase 9
    Tier-2 rate limiter). Returns None when no fallback key is configured so
    callers can degrade gracefully.
    """
    global _fallback_client
    if _fallback_client is None:
        api_key = os.getenv("GROQ_API_KEY_FALLBACK")
        if not api_key:
            return None
        _fallback_client = AsyncGroq(api_key=api_key)
    return _fallback_client
