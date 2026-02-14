"""
LLM Interface - Swappable AI providers
Supports: DeepSeek, Google Gemini, OpenAI-compatible APIs

SmartLLM: Gemini (free) as primary, DeepSeek (cheap) as fallback.
"""
import requests
from typing import Dict, Any, Optional


class LLMInterface:
    """Base interface for any LLM provider - easily extensible"""

    def __init__(self, config: Dict[str, Any], fallback_config: Dict[str, Any] = None):
        self.config = config
        self.provider = config.get("provider", "deepseek")
        self.fallback_config = fallback_config
        self._call_count = 0
        self._fallback_count = 0

    def chat(self, prompt: str) -> str:
        """
        Send prompt to LLM and get response.
        If fallback_config is set, auto-switches on failure.
        """
        self._call_count += 1
        try:
            return self._dispatch(prompt, self.config)
        except Exception as e:
            if self.fallback_config:
                self._fallback_count += 1
                provider = self.fallback_config.get("provider", "?")
                print(f"  ⚡ Fallback → {provider} (reason: {type(e).__name__})")
                return self._dispatch(prompt, self.fallback_config)
            raise

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
