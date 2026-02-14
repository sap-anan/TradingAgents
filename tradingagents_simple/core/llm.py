"""
LLM Interface - Swappable AI providers
Supports: DeepSeek, Google Gemini, OpenAI-compatible APIs
"""
import requests
from typing import Dict, Any


class LLMInterface:
    """Base interface for any LLM provider - easily extensible"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "deepseek")

    def chat(self, prompt: str) -> str:
        """
        Send prompt to LLM and get response
        Extension point: Add new providers here
        """
        if self.provider == "deepseek":
            return self._deepseek_chat(prompt)
        elif self.provider == "google":
            return self._gemini_chat(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _deepseek_chat(self, prompt: str) -> str:
        """DeepSeek API (OpenAI-compatible)"""
        url = f"{self.config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.config["model"],
            "messages": [
                {"role": "system", "content": "You are an expert stock market analyst."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]

    def _gemini_chat(self, prompt: str) -> str:
        """Google Gemini API"""
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=self.config["model"],
            google_api_key=self.config["api_key"],
        )

        response = llm.invoke(prompt)
        return response.content


# Extension point: Add new providers
# class CustomLLMProvider(LLMInterface):
#     def chat(self, prompt: str) -> str:
#         # Your custom implementation
#         pass
