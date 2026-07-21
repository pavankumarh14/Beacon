"""
Provider-agnostic LLM client.
================================

The ONLY file to touch to switch LLM providers (OpenAI / Anthropic Claude /
Groq / DeepSeek / local). The rest of the code talks to an LLM exclusively via
`LLMClient.chat()` / `LLMClient.chat_json()`.

Zero third-party dependencies — standard library `urllib` only.

Configuration (environment variables)
--------------------------------------
* BEACON_LLM_PROVIDER   default: "openai"
* BEACON_LLM_API_KEY    your API key (falls back to OPENAI_API_KEY)
* BEACON_LLM_MODEL      default: "gpt-4o-mini"
* BEACON_LLM_BASE_URL   default: provider default

See the README "Using a different LLM" section.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional


PROVIDERS = {
    "openai": {"base_url": "https://api.openai.com/v1",
               "default_model": "gpt-4o-mini", "format": "openai"},
    "groq": {"base_url": "https://api.groq.com/openai/v1",
             "default_model": "llama-3.3-70b-versatile", "format": "openai"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1",
                 "default_model": "deepseek-chat", "format": "openai"},
    "ollama": {"base_url": "http://localhost:11434/v1",
               "default_model": "llama3.1", "format": "openai"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1",
                  "default_model": "claude-sonnet-4-6", "format": "anthropic"},
    # These providers expose OpenAI-compatible Chat Completions endpoints.
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "default_model": "gemini-3.5-flash", "format": "openai"},
    "xai": {"base_url": "https://api.x.ai/v1",
            "default_model": "grok-4.5", "format": "openai"},
    # Use this for any other OpenAI-compatible provider (Together, vLLM, etc.).
    # BEACON_LLM_BASE_URL is required when selecting it.
    "openai_compatible": {"base_url": "", "default_model": "", "format": "openai"},
}


class LLMError(RuntimeError):
    """Raised when the LLM call fails after retries."""


class LLMClient:
    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None,
                 model: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: int = 60):
        self.provider = (provider or os.getenv("BEACON_LLM_PROVIDER", "openai")).lower()
        if self.provider not in PROVIDERS:
            raise LLMError("Unknown provider %r. Known: %s. Add one in beacon/llm.py:PROVIDERS."
                           % (self.provider, ", ".join(PROVIDERS)))
        preset = PROVIDERS[self.provider]
        self.format = preset["format"]
        self.base_url = (base_url or os.getenv("BEACON_LLM_BASE_URL") or preset["base_url"]).rstrip("/")
        self.model = model or os.getenv("BEACON_LLM_MODEL") or preset["default_model"]
        self.api_key = (api_key or os.getenv("BEACON_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
                        or ("ollama" if self.provider == "ollama" else None))
        self.timeout = timeout
        if not self.api_key:
            raise LLMError("No API key found. Set BEACON_LLM_API_KEY (or OPENAI_API_KEY) "
                           "in your environment or .env file.")
        if not self.base_url:
            raise LLMError("No base URL found. Set BEACON_LLM_BASE_URL when using "
                           "BEACON_LLM_PROVIDER=openai_compatible.")
        if not self.model:
            raise LLMError("No model found. Set BEACON_LLM_MODEL when using "
                           "BEACON_LLM_PROVIDER=openai_compatible.")

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3,
             max_tokens: int = 600, json_mode: bool = False) -> str:
        if self.format == "anthropic":
            return self._chat_anthropic(messages, temperature, max_tokens)
        return self._chat_openai(messages, temperature, max_tokens, json_mode)

    def chat_json(self, messages: List[Dict[str, str]], temperature: float = 0.1,
                  max_tokens: int = 600) -> dict:
        raw = self.chat(messages, temperature, max_tokens, json_mode=True)
        return _parse_json_object(raw)

    def _chat_openai(self, messages, temperature, max_tokens, json_mode) -> str:
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post(self.base_url + "/chat/completions", payload,
                          {"Authorization": "Bearer " + self.api_key})
        return data["choices"][0]["message"]["content"]

    def _chat_anthropic(self, messages, temperature, max_tokens) -> str:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        payload = {"model": self.model, "max_tokens": max_tokens,
                   "temperature": temperature, "messages": convo}
        if system:
            payload["system"] = system
        data = self._post(self.base_url + "/messages", payload,
                          {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        return data["content"][0]["text"]

    def _post(self, url: str, payload: dict, extra_headers: Dict[str, str]) -> dict:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers.update(extra_headers)
        last_err = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "ignore")
                last_err = LLMError("HTTP %s from %s: %s" % (e.code, url, detail))
                if e.code not in (429, 500, 502, 503, 504):
                    raise last_err
            except urllib.error.URLError as e:
                last_err = LLMError("Network error calling %s: %s" % (url, e.reason))
            time.sleep(1.5 * (attempt + 1))
        raise last_err  # type: ignore[misc]


def _parse_json_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().lower().startswith("json"):
            raw = raw.lstrip()[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise LLMError("Could not parse JSON from LLM reply:\n%s" % raw)
