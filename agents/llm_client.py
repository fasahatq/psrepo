"""
LLM Client — single entry point for all LLM calls in the Perfect Store pipeline.

Backend is controlled by the LLM_BACKEND environment variable:

  LLM_BACKEND=anthropic  (default)
      Uses Claude via the Anthropic API.
      Requires ANTHROPIC_API_KEY in .env.

  LLM_BACKEND=azure
      Uses Azure OpenAI Service via the OpenAI Python SDK (AzureOpenAI client).
      Requires AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and
      AZURE_OPENAI_DEPLOYMENT in .env.
      API version set via AZURE_OPENAI_API_VERSION (default: 2025-01-01-preview).

  LLM_BACKEND=local
      Uses a locally-running Ollama model — no data leaves the machine.
      Requires Ollama to be running: https://ollama.com
      Model is set via LOCAL_LLM_MODEL (default: gemma3:12b).
      Endpoint is set via LOCAL_LLM_URL (default: http://localhost:11434/v1).

  LLM_BACKEND=gemini
      Uses Google Gemini via the Gemini API (google-genai SDK).
      Requires GEMINI_API_KEY in .env.
      Model is set via GEMINI_MODEL (default: gemini-1.5-pro).

  LLM_BACKEND=vertex
      Uses Google Vertex AI (Gemini) via Application Default Credentials.
      Requires VERTEX_PROJECT and optionally VERTEX_LOCATION / VERTEX_MODEL.

Usage:
    from agents.llm_client import call_llm
    text = call_llm(prompt, api_key, model, system_prompt=system_prompt)
"""

import os
import time
import hashlib
import threading
import logging

logger = logging.getLogger("perfect_store.llm_client")


# ── Gemini model resolution ──────────────────────────────────────────────────
# If the configured model is unavailable (quota exhausted, not yet GA, region
# restrictions, etc.) we walk down this chain and use the first accessible one.
# Extend the list here if more fallback tiers are needed.
GEMINI_FALLBACK_CHAIN = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

# preferred_model_name -> resolved_model_name (populated once per process)
_gemini_working_model: dict = {}
_gemini_model_lock = threading.Lock()


def _resolve_working_gemini_model(client, preferred: str) -> str:
    """
    Verify `preferred` is accessible; if not, walk down GEMINI_FALLBACK_CHAIN
    and return the first model that responds to a free metadata probe
    (client.models.get — no tokens consumed).

    The resolved name is cached so the probe only runs once per process.
    """
    with _gemini_model_lock:
        if preferred in _gemini_working_model:
            return _gemini_working_model[preferred]

        # Build probe order: preferred first, then every fallback after it
        try:
            start = GEMINI_FALLBACK_CHAIN.index(preferred) + 1
            probe_chain = [preferred] + GEMINI_FALLBACK_CHAIN[start:]
        except ValueError:
            probe_chain = [preferred]   # not in known chain — try as-is only

        chosen = preferred
        for candidate in probe_chain:
            try:
                client.models.get(model=candidate)
                chosen = candidate
                if candidate != preferred:
                    logger.warning(
                        f"Gemini model '{preferred}' unavailable — "
                        f"automatically switched to '{candidate}'"
                    )
                else:
                    logger.info(f"Gemini model available: {candidate}")
                break
            except Exception as probe_err:
                logger.warning(
                    f"Gemini model '{candidate}' not accessible ({probe_err})"
                )
        else:
            # Every candidate failed; proceed with preferred and let the real
            # API call surface a meaningful error.
            logger.error(
                f"All Gemini model candidates failed availability probe. "
                f"Proceeding with '{preferred}' — the generate call may fail."
            )

        _gemini_working_model[preferred] = chosen
        return chosen


# ── Gemini context-cache registry ────────────────────────────────────────────
# Gemini context caching is an explicit server-side resource.  We create one
# cache per unique (model, system_prompt) pair and reuse it for every call
# within the same process lifetime, saving ~80-90 % of input-token costs.
#
# Keys   : first 16 hex chars of sha256("{model}:{system_prompt}")
# Values : cache.name string (e.g. "cachedContents/abc123"), or None if
#          creation failed (below min-token threshold or API error).
#          A None entry means "don't retry — fall back to system_instruction".
_gemini_cache_registry: dict = {}
_gemini_cache_lock = threading.Lock()


def _get_or_create_gemini_cache(client, model_name: str, system_prompt: str):
    """
    Return a Gemini context cache name for this (model, system_prompt) pair.

    Creates the cache on the first call and stores the name in the module-level
    registry.  All subsequent calls for the same pair return the cached name
    immediately (no API round-trip).

    Returns None if creation fails so the caller falls back to passing
    system_instruction directly on every request.
    """
    from google.genai import types

    key = hashlib.sha256(
        f"{model_name}:{system_prompt}".encode()
    ).hexdigest()[:16]

    with _gemini_cache_lock:
        if key in _gemini_cache_registry:
            return _gemini_cache_registry[key]

        try:
            cache = client.caches.create(
                model=model_name,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_prompt,
                    ttl="3600s",   # 1-hour TTL; more than enough for one pipeline run
                ),
            )
            logger.info(
                f"Gemini context cache created — name={cache.name}  model={model_name}"
            )
            _gemini_cache_registry[key] = cache.name
            return cache.name
        except Exception as e:
            logger.warning(
                f"Gemini context cache creation skipped ({e}) — "
                f"falling back to uncached system_instruction for this prompt"
            )
            _gemini_cache_registry[key] = None   # don't retry
            return None


# Keywords that indicate a transient server-side error worth retrying.
# Permanent errors (auth failures, bad requests, context-length exceeded) won't
# match these and will propagate immediately.
_RETRYABLE_KEYWORDS = (
    "503", "unavailable", "rate_limit", "429", "resource_exhausted",
    "too_many_requests", "overloaded", "try again", "temporarily",
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in _RETRYABLE_KEYWORDS)


def call_llm(prompt: str, api_key: str, model: str,
             max_tokens: int = 2000,
             system_prompt: str = None) -> str:
    """
    Route an LLM call to the configured backend with automatic retry on
    transient errors (503 UNAVAILABLE, 429 rate-limit).

    Retry schedule (configurable via env vars):
      LLM_MAX_RETRIES      — total retries after first failure (default: 3)
      LLM_RETRY_BASE_DELAY — base delay in seconds; doubles each retry (default: 5)
      Attempt delays: 5 s → 10 s → 20 s

    Args:
        prompt        : user-turn prompt string
        api_key       : Anthropic API key — ignored in local/gemini/vertex mode
        model         : model name — ignored in local mode
        max_tokens    : maximum tokens to generate
        system_prompt : optional system-level context injected before the user turn.
                        For Anthropic this maps to the `system` parameter.
                        For Gemini/Vertex it is passed as system_instruction.
                        For local (Ollama) it is prepended as a system message.
    """
    backend     = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    base_delay  = float(os.getenv("LLM_RETRY_BASE_DELAY", "5"))

    for attempt in range(max_retries + 1):
        try:
            if backend == "local":
                return _call_local(prompt, max_tokens, system_prompt)
            elif backend == "azure":
                return _call_azure_openai(prompt, max_tokens, system_prompt)
            elif backend == "gemini":
                return _call_gemini(prompt, max_tokens, system_prompt)
            elif backend == "vertex":
                return _call_vertex(prompt, max_tokens, system_prompt)
            else:
                return _call_anthropic(prompt, api_key, model, max_tokens, system_prompt)

        except Exception as exc:
            is_last = attempt >= max_retries
            if not is_last and _is_retryable(exc):
                delay = base_delay * (2 ** attempt)   # 5 s, 10 s, 20 s
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}, "
                    f"retryable): {exc}. Retrying in {delay:.0f}s..."
                )
                time.sleep(delay)
            else:
                raise   # permanent error or retries exhausted — bubble up


# ── Anthropic (cloud) ────────────────────────────────────────────────────────

def _call_anthropic(prompt: str, api_key: str, model: str,
                    max_tokens: int, system_prompt: str = None) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system_prompt:
        # cache_control: ephemeral caches this block across all calls that share
        # the same system prompt text, saving ~80-90% of input-token costs when
        # project.md + agent context is re-sent on every pipeline LLM call.
        kwargs["system"] = [
            {"type": "text", "text": system_prompt,
             "cache_control": {"type": "ephemeral"}}
        ]

    response = client.messages.create(**kwargs)
    logger.debug(f"Anthropic call complete — model={model}")
    return response.content[0].text


# ── Ollama / local (OpenAI-compatible API) ───────────────────────────────────

def _call_local(prompt: str, max_tokens: int, system_prompt: str = None) -> str:
    """
    Call a locally-running Ollama model via its OpenAI-compatible REST API.
    Ollama must be running (`ollama serve`) and the model must be pulled:
        ollama pull gemma3:12b
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for local LLM mode.\n"
            "Install it with:  pip install openai"
        )

    base_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
    local_model = os.getenv("LOCAL_LLM_MODEL", "gemma3:12b")

    logger.info(f"Local LLM call — model={local_model}  endpoint={base_url}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    client = OpenAI(
        base_url=base_url,
        api_key="local",          # Ollama ignores this but the client requires it
    )
    response = client.chat.completions.create(
        model=local_model,
        max_tokens=max_tokens,
        messages=messages,
        temperature=0.3,
    )

    text = response.choices[0].message.content
    logger.debug(f"Local LLM call complete — {len(text)} chars returned")
    return text


# ── Azure OpenAI ─────────────────────────────────────────────────────────────

def _call_azure_openai(prompt: str, max_tokens: int, system_prompt: str = None) -> str:
    """
    Call Azure OpenAI Service via the OpenAI Python SDK (AzureOpenAI client).

    Required env vars:
      AZURE_OPENAI_ENDPOINT   — e.g. https://<resource>.openai.azure.com/
      AZURE_OPENAI_API_KEY    — Azure OpenAI resource key
      AZURE_OPENAI_DEPLOYMENT — deployment/model name (e.g. gpt-4o)
    Optional:
      AZURE_OPENAI_API_VERSION — defaults to 2025-01-01-preview
    """
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for Azure OpenAI mode.\n"
            "Install it with:  pip install openai"
        )

    endpoint   = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key    = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT env var is required for LLM_BACKEND=azure")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY env var is required for LLM_BACKEND=azure")

    logger.info(f"Azure OpenAI call — deployment={deployment}  endpoint={endpoint}")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=deployment,
        max_completion_tokens=max_tokens,
        messages=messages,
        temperature=0.3,
    )

    text = response.choices[0].message.content
    logger.debug(f"Azure OpenAI call complete — {len(text)} chars returned")
    return text


# ── Gemini API (google-genai SDK, API key) ───────────────────────────────────

def _call_gemini(prompt: str, max_tokens: int, system_prompt: str = None) -> str:
    """
    Call Gemini via the Google AI Gemini API using an API key.
    Requires: pip install google-genai
    Auth:     GEMINI_API_KEY in .env
    Model:    GEMINI_MODEL in .env (default: gemini-2.0-flash)
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "The 'google-genai' package is required for Gemini API mode.\n"
            "Install it with:  pip install google-genai"
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY env var is required for LLM_BACKEND=gemini")

    preferred_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)

    # Resolve the model once — probes availability and falls back to
    # gemini-2.5-flash (then gemini-2.0-flash) if the preferred model is down.
    model_name = _resolve_working_gemini_model(client, preferred_model)
    logger.info(f"Gemini API call — model={model_name}")

    # Thinking models (gemini-2.5+) include thinking tokens in max_output_tokens.
    # Without an explicit thinking_budget, thinking consumes the entire budget
    # and content.parts=None (finish_reason=MAX_TOKENS) with no actual output.
    # Cap thinking at 2048 tokens and add that to the requested output budget.
    thinking_config = None
    total_tokens = max_tokens
    if "2.5" in model_name or "3." in model_name:
        thinking_budget = 2048
        total_tokens = max_tokens + thinking_budget
        thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)

    config_kwargs = dict(
        max_output_tokens=total_tokens,
        temperature=0.3,
        thinking_config=thinking_config,
    )
    if system_prompt:
        cache_name = _get_or_create_gemini_cache(client, model_name, system_prompt)
        if cache_name:
            # system_instruction is embedded in the cache — must not pass it again
            config_kwargs["cached_content"] = cache_name
        else:
            config_kwargs["system_instruction"] = system_prompt

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    # response.text can be None if parts is None; extract text defensively.
    text = response.text
    if text is None:
        parts = []
        for candidate in (response.candidates or []):
            content = getattr(candidate, "content", None)
            for part in (content.parts or [] if content else []):
                if getattr(part, "thought", False):
                    continue
                if part.text:
                    parts.append(part.text)
        text = "\n".join(parts)

    if not text:
        finish = (response.candidates[0].finish_reason
                  if response.candidates else "unknown")
        raise ValueError(f"Gemini returned an empty response (finish_reason={finish})")

    logger.debug(f"Gemini API call complete — {len(text)} chars returned")
    return text


# ── Vertex AI / Gemini (Google Cloud) ───────────────────────────────────────

def _call_vertex(prompt: str, max_tokens: int, system_prompt: str = None) -> str:
    """
    Call a model on Google Cloud Vertex AI using Application Default Credentials.

    Supports two model families, detected automatically from VERTEX_MODEL:
      • claude-*   → AnthropicVertex client  (pip install 'anthropic[vertex]')
      • gemini-*   → google-cloud-aiplatform  (pip install google-cloud-aiplatform)

    Auth: gcloud auth application-default login  (or a service account)
    Env:  VERTEX_PROJECT, VERTEX_LOCATION (Gemini) / VERTEX_CLAUDE_LOCATION (Claude)
    """
    project = os.getenv("VERTEX_PROJECT")
    if not project:
        raise ValueError("VERTEX_PROJECT env var is required for LLM_BACKEND=vertex")

    model_name = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

    if model_name.startswith("claude"):
        return _call_vertex_claude(prompt, max_tokens, system_prompt, project, model_name)
    else:
        return _call_vertex_gemini(prompt, max_tokens, system_prompt, project, model_name)


def _call_vertex_claude(prompt: str, max_tokens: int, system_prompt: str,
                        project: str, model_name: str) -> str:
    """
    Call a Claude model hosted on Google Cloud Vertex AI.

    Uses the AnthropicVertex client which shares the same Messages API as the
    direct Anthropic client — including prompt caching via cache_control.

    Requires: pip install 'anthropic[vertex]'
    Auth:     gcloud auth application-default login  (or GOOGLE_APPLICATION_CREDENTIALS)
    Region:   VERTEX_CLAUDE_LOCATION env var (default: us-east5 — primary Claude region)
    """
    try:
        from anthropic import AnthropicVertex
    except ImportError:
        raise ImportError(
            "The 'anthropic[vertex]' package is required for Claude on Vertex AI.\n"
            "Install it with:  pip install 'anthropic[vertex]'"
        )

    # Claude models on Vertex AI are available in specific regions.
    # us-east5 (Columbus) is the primary region for Claude 3+ and Claude 4.
    # Override with VERTEX_CLAUDE_LOCATION if your project uses a different region.
    location = os.getenv("VERTEX_CLAUDE_LOCATION", "us-east5")

    logger.info(
        f"Vertex AI (Claude) call — model={model_name}  "
        f"project={project}  region={location}"
    )

    client = AnthropicVertex(region=location, project_id=project)

    kwargs = dict(
        model=model_name,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system_prompt:
        # cache_control: ephemeral is supported on Claude via Vertex AI —
        # same 80-90% input-token cost saving as the direct Anthropic backend.
        kwargs["system"] = [
            {"type": "text", "text": system_prompt,
             "cache_control": {"type": "ephemeral"}}
        ]

    response = client.messages.create(**kwargs)
    logger.debug(f"Vertex AI (Claude) call complete — model={model_name}")
    return response.content[0].text


def _call_vertex_gemini(prompt: str, max_tokens: int, system_prompt: str,
                        project: str, model_name: str) -> str:
    """Call a Gemini model on Vertex AI via the google-genai SDK."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "The 'google-genai' package is required for Gemini on Vertex AI.\n"
            "Install it with:  pip install google-genai"
        )

    location = os.getenv("VERTEX_LOCATION", "us-central1")
    logger.info(
        f"Vertex AI (Gemini) call — model={model_name}  "
        f"project={project}  location={location}"
    )

    client = genai.Client(vertexai=True, project=project, location=location)

    # Thinking models (gemini-2.5+) need an explicit budget so thinking tokens
    # don't silently consume the entire max_output_tokens quota.
    thinking_config = None
    total_tokens = max_tokens
    if "2.5" in model_name or "3." in model_name:
        thinking_budget = 2048
        total_tokens = max_tokens + thinking_budget
        thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)

    config_kwargs = dict(
        max_output_tokens=total_tokens,
        temperature=0.3,
        thinking_config=thinking_config,
    )
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    text = response.text
    if text is None:
        parts = []
        for candidate in (response.candidates or []):
            content = getattr(candidate, "content", None)
            for part in (content.parts or [] if content else []):
                if getattr(part, "thought", False):
                    continue
                if part.text:
                    parts.append(part.text)
        text = "\n".join(parts)

    if not text:
        finish = (response.candidates[0].finish_reason
                  if response.candidates else "unknown")
        raise ValueError(f"Vertex AI Gemini returned an empty response (finish_reason={finish})")

    logger.debug(f"Vertex AI (Gemini) call complete — {len(text)} chars returned")
    return text
