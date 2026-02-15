"""
LLM Interface - Swappable AI providers
Supports: DeepSeek, Google Gemini, OpenAI-compatible APIs

SmartLLM: Gemini (free) as primary, DeepSeek (cheap) as fallback.
"""
import os
import json
import time
import requests
from core.event_bus import EventBus
from datetime import datetime
from typing import Dict, Any, Optional

# Persistent LLM call log
LLM_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "logs")
os.makedirs(LLM_LOG_DIR, exist_ok=True)


def _log_llm_call(record: Dict):
    """Append LLM call record to daily JSONL log."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LLM_LOG_DIR, f"llm_calls_{date_str}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


class CircuitBreaker:
    """
    Circuit breaker: after N consecutive failures, skip primary for cooldown period.
    States: CLOSED (normal) → OPEN (skip primary) → HALF_OPEN (test one request)
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, fail_threshold: int = 2, cooldown_seconds: int = 300):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = self.CLOSED
        self.fail_count = 0
        self.last_fail_time = 0
        self.last_error = None

    def should_skip(self) -> bool:
        """Check if primary should be skipped."""
        if self.state == self.CLOSED:
            return False
        if self.state == self.OPEN:
            # Check if cooldown expired → try one request (half-open)
            if time.time() - self.last_fail_time > self.cooldown_seconds:
                self.state = self.HALF_OPEN
                return False
            return True
        # HALF_OPEN: allow one test request
        return False

    def record_success(self):
        """Primary succeeded — reset breaker."""
        self.fail_count = 0
        self.state = self.CLOSED
        self.last_error = None

    def record_failure(self, error: Exception):
        """Primary failed — increment counter, maybe open breaker."""
        self.fail_count += 1
        self.last_fail_time = time.time()
        self.last_error = str(error)

        is_rate_limit = (
            hasattr(error, 'response') and
            getattr(error.response, 'status_code', 0) == 429
        )

        if is_rate_limit:
            # 429 = rate limit → open immediately, long cooldown
            self.state = self.OPEN
            self.cooldown_seconds = 600  # 10 min for rate limits
            return

        if self.fail_count >= self.fail_threshold:
            self.state = self.OPEN

    def status_dict(self) -> Dict:
        return {
            "state": self.state,
            "fail_count": self.fail_count,
            "last_error": self.last_error,
            "cooldown_remaining": max(0, self.cooldown_seconds - (time.time() - self.last_fail_time))
            if self.state == self.OPEN else 0,
        }


class LLMInterface:
    """Base interface for any LLM provider - easily extensible"""

    def __init__(self, config: Dict[str, Any], fallback_config: Dict[str, Any] = None):
        self.config = config
        self.provider = config.get("provider", "deepseek")
        self.fallback_config = fallback_config
        self._call_count = 0
        self._fallback_count = 0
        self._breaker = CircuitBreaker(fail_threshold=2, cooldown_seconds=300)

    def chat(self, prompt: str) -> str:
        """
        Send prompt to LLM and get response.
        Circuit breaker skips primary if it's rate-limited or failing.
        """
        self._call_count += 1
        t0 = time.time()
        used_fallback = False
        provider = self.config.get("provider", "?")
        model = self.config.get("model", "?")
        error_msg = None

        # Circuit breaker: skip primary if tripped
        skip_primary = self._breaker.should_skip()
        if skip_primary and self.fallback_config:
            self._fallback_count += 1
            used_fallback = True
            provider = self.fallback_config.get("provider", "?")
            model = self.fallback_config.get("model", "?")
            breaker_status = self._breaker.status_dict()
            print(f"  ⚡ Circuit breaker OPEN → {provider} "
                  f"(cooldown {breaker_status['cooldown_remaining']:.0f}s)")
            result = self._dispatch(prompt, self.fallback_config)
        else:
            try:
                result = self._dispatch(prompt, self.config)
                self._breaker.record_success()
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self._breaker.record_failure(e)
                if self.fallback_config:
                    self._fallback_count += 1
                    used_fallback = True
                    provider = self.fallback_config.get("provider", "?")
                    model = self.fallback_config.get("model", "?")
                    print(f"  ⚡ Fallback → {provider} (reason: {type(e).__name__})")
                    if self._breaker.state == CircuitBreaker.OPEN:
                        print(f"  🔒 Circuit breaker OPENED — skipping primary for "
                              f"{self._breaker.cooldown_seconds}s")
                    result = self._dispatch(prompt, self.fallback_config)
                else:
                    _log_llm_call({
                        "ts": datetime.now().isoformat(),
                        "provider": provider, "model": model,
                        "fallback": False, "success": False,
                        "error": error_msg,
                        "prompt_len": len(prompt), "response_len": 0,
                        "latency_ms": int((time.time() - t0) * 1000),
                    })
                    raise

        latency_ms = int((time.time() - t0) * 1000)
        _log_llm_call({
            "ts": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "fallback": used_fallback,
            "success": True,
            "error": error_msg,
            "prompt_len": len(prompt),
            "response_len": len(result),
            "latency_ms": latency_ms,
            "circuit_breaker": self._breaker.status_dict(),
        })

        EventBus.instance().emit("llm", provider, "response",
            {"prompt_len": len(prompt), "response_len": len(result)},
            latency_ms=latency_ms, status="ok")

        return result

    def get_breaker_status(self) -> Dict:
        """Get circuit breaker status for dashboard."""
        return self._breaker.status_dict()

    def _dispatch(self, prompt: str, config: Dict) -> str:
        """Route to correct provider"""
        provider = config.get("provider", "deepseek")
        if provider == "deepseek":
            return self._deepseek_chat(prompt, config)
        elif provider == "google":
            return self._gemini_chat(prompt, config)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_stats(self) -> Dict:
        """Usage stats for cost tracking"""
        return {
            "total_calls": self._call_count,
            "fallback_calls": self._fallback_count,
            "primary": self.config.get("provider"),
            "fallback": self.fallback_config.get("provider") if self.fallback_config else None,
        }

    def _deepseek_chat(self, prompt: str, config: Dict = None) -> str:
        """DeepSeek API (OpenAI-compatible)"""
        config = config or self.config
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": "You are an expert stock market analyst."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]

    def _gemini_chat(self, prompt: str, config: Dict = None) -> str:
        """Google Gemini API (free tier: 250 req/day)"""
        config = config or self.config
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config['model']}:generateContent?key={config['api_key']}"
        )
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7},
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]


# Extension point: Add new providers
# class CustomLLMProvider(LLMInterface):
#     def chat(self, prompt: str) -> str:
#         # Your custom implementation
#         pass
