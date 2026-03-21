"""Multi-provider LLM client with retry logic, logging, and token tracking.

Supports Ollama, OpenAI-compatible APIs, and any /v1/chat/completions endpoint.
"""
import json
import logging
import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import Config

logger = logging.getLogger("novelswarm.llm")

_client = httpx.Client(timeout=180.0)

# Global token tracking
_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


def get_token_usage() -> dict:
    """Get cumulative token usage stats."""
    return dict(_token_usage)


def reset_token_usage():
    """Reset token tracking."""
    global _token_usage
    _token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


class LLMError(Exception):
    """Base error for LLM calls."""
    pass


class LLMRetryableError(LLMError):
    """Error that should be retried (timeout, rate limit, server error)."""
    pass


class LLMFatalError(LLMError):
    """Error that should NOT be retried (invalid model, auth failure)."""
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(LLMRetryableError),
    before_sleep=lambda retry_state: logger.warning(
        f"LLM call failed (attempt {retry_state.attempt_number}), retrying in "
        f"{retry_state.next_action.sleep:.1f}s: {retry_state.outcome.exception()}"
    ),
)
def chat(
    messages: list[dict],
    system: str = "",
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request to the configured LLM provider.
    
    Retries up to 3 times on transient failures (timeouts, 5xx errors).
    """
    global _token_usage
    model = model or Config.LLM_MODEL_NAME
    url = Config.LLM_BASE_URL.rstrip("/") + "/chat/completions"

    formatted_messages = []
    if system:
        formatted_messages.append({"role": "system", "content": system})
    formatted_messages.extend(messages)

    payload = {
        "model": model,
        "messages": formatted_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    # LOG THE RAW PROMPT SO THE USER CAN SEE IT
    logger.info(f"\n====================== LLM INVOCATION: {model} ======================")
    for m in formatted_messages:
        # Truncate slightly in logs if it's massively large, but keep it mostly readable
        log_content = m['content'] if len(m['content']) < 5000 else m['content'][:4900] + "\n...[TRUNCATED IN LOGS]..."
        logger.info(f"[{m['role'].upper()}]:\n{log_content}\n")
    logger.info("========================================================================\n")

    # ALSO PRINT TO TERMINAL FOR IMMEDIATE VISIBILITY
    print(f"\n{'='*80}")
    print(f"🤖 LLM CALL: {model}")
    print(f"{'='*80}")
    for m in formatted_messages:
        role_icon = "🔧" if m['role'] == 'system' else "👤" if m['role'] == 'user' else "🤖"
        content_preview = m['content'][:300] + "..." if len(m['content']) > 300 else m['content']
        print(f"\n{role_icon} [{m['role'].upper()}]:")
        print(content_preview)
    print(f"\n{'='*80}")
    print("⏳ Waiting for response...")
    print(f"{'='*80}\n")

    headers = {"Content-Type": "application/json"}
    if Config.LLM_API_KEY and Config.LLM_API_KEY != "ollama":
        headers["Authorization"] = f"Bearer {Config.LLM_API_KEY}"

    start = time.time()
    try:
        resp = _client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as e:
        logger.error(f"LLM timeout after {time.time()-start:.1f}s: {e}")
        raise LLMRetryableError(f"Timeout: {e}") from e
    except httpx.ConnectError as e:
        logger.error(f"LLM connection error: {e}")
        raise LLMRetryableError(f"Connection error: {e}") from e
    except Exception as e:
        logger.error(f"LLM unexpected error: {e}")
        raise LLMRetryableError(f"Unexpected: {e}") from e

    # Handle HTTP errors
    if resp.status_code >= 500:
        raise LLMRetryableError(f"Server error {resp.status_code}: {resp.text[:200]}")
    elif resp.status_code == 429:
        raise LLMRetryableError(f"Rate limited: {resp.text[:200]}")
    elif resp.status_code >= 400:
        raise LLMFatalError(f"Client error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    elapsed = time.time() - start

    # Track token usage
    usage = data.get("usage", {})
    _token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
    _token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
    _token_usage["total_tokens"] += usage.get("total_tokens", 0)
    _token_usage["calls"] += 1

    content = data["choices"][0]["message"]["content"]
    logger.debug(
        f"LLM call: model={model} tokens={usage.get('total_tokens', '?')} "
        f"time={elapsed:.1f}s len={len(content)}"
    )

    # PRINT RESPONSE TO TERMINAL
    print(f"\n{'='*80}")
    print(f"✅ LLM RESPONSE ({elapsed:.1f}s | {usage.get('total_tokens', '?')} tokens)")
    print(f"{'='*80}")
    response_preview = content[:500] + "..." if len(content) > 500 else content
    print(response_preview)
    print(f"\n{'='*80}\n")

    return content


def chat_json(
    messages: list[dict],
    system: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict | list:
    """Chat and parse JSON response. Falls back to string extraction if JSON mode fails."""
    try:
        raw = chat(messages, system=system, model=model, json_mode=True, max_tokens=max_tokens)
    except LLMFatalError:
        # Some models don't support json_mode, try without
        raw = chat(messages, system=system, model=model, json_mode=False, max_tokens=max_tokens)

    # Clean common LLM response artifacts
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed, attempting extraction: {e}")
        # Try to find JSON in the response
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = raw.find(start_char)
            end_idx = raw.rfind(end_char)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(raw[start_idx:end_idx + 1])
                except json.JSONDecodeError:
                    continue
        raise LLMError(f"Could not parse JSON from LLM response: {raw[:200]}")


def boost_chat(messages: list[dict], system: str = "", **kwargs) -> str:
    """Use the boost model for higher-quality extraction tasks."""
    return chat(messages, system=system, model=Config.LLM_BOOST_MODEL, **kwargs)
