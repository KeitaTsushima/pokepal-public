"""
OpenAI HTTP Client Utility
Shared HTTP client configuration for all OpenAI API clients
"""
import httpx


def create_openai_http_client() -> httpx.Client:
    """Create optimized HTTP client for OpenAI APIs (Chat, Whisper, etc.)"""
    return httpx.Client(
        http2=True,
        timeout=httpx.Timeout(connect=10, read=45, write=10, pool=5),
        headers={'User-Agent': 'PokePal-Voice/1.0'},
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )