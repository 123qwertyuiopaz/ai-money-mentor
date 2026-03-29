"""
NVIDIA NIM API client — wraps the OpenAI-compatible endpoint.
All agents call through this single client so API key management
and retry logic live in one place.
"""
import time
import logging
from typing import Generator
from openai import OpenAI, APIError, RateLimitError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NIMClient:
    """Thin wrapper around the OpenAI SDK pointed at NVIDIA NIM."""

    def __init__(self):
        self._client = OpenAI(
            api_key=settings.nvidia_nim_api_key,
            base_url=settings.nvidia_nim_base_url,
        )
        self.model = settings.nvidia_nim_model

    # ── Core completion ────────────────────────────────────────────────────────

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> tuple[str, dict]:
        """
        Send a single-turn completion and return (text, usage_dict).
        `json_mode=True` instructs the model to respond only with valid JSON.
        """
        t0 = time.monotonic()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        kwargs: dict = dict(
            model=self.model,
            messages=messages,
            temperature=temperature or settings.nvidia_nim_temperature,
            max_tokens=max_tokens or settings.nvidia_nim_max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except RateLimitError:
            logger.warning("NIM rate limit hit — retrying after 2 s")
            time.sleep(2)
            response = self._client.chat.completions.create(**kwargs)
        except APIError as e:
            logger.error("NIM API error: %s", e)
            raise

        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "latency_ms": latency_ms,
        }

        text = response.choices[0].message.content or ""
        logger.debug("NIM call: %d ms | %d+%d tokens", latency_ms,
                     usage["prompt_tokens"], usage["completion_tokens"])
        return text, usage

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        """
        Streaming version — yields text chunks as they arrive.
        Useful for endpoints that return Server-Sent Events.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        with self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or settings.nvidia_nim_temperature,
            max_tokens=max_tokens or settings.nvidia_nim_max_tokens,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    # ── Multi-turn ─────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict]:
        """Multi-turn chat — caller supplies the full messages array."""
        t0 = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or settings.nvidia_nim_temperature,
                max_tokens=max_tokens or settings.nvidia_nim_max_tokens,
            )
        except APIError as e:
            logger.error("NIM API error in chat: %s", e)
            raise

        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "latency_ms": latency_ms,
        }
        return response.choices[0].message.content or "", usage


# Module-level singleton — all agents share one connection pool
nim = NIMClient()
